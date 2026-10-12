"""Orchestrator for F11 (legacy chat wrapping) + R_F6 + R_F3 (nuisance
factors under R, 2026-10-12), run in this fixed order:

  1. F11   (6 models x 3 suites = 18 runs) -> results_v2/F11/
            mistral_v01, mistral_v02, mistral_v03, qwen2, qwen25, qwen3
            (Qwen3 last; not pre-split -- see DEVIATIONS.md, D's own
            Qwen3 timings all ran single/unsplit comfortably under 2h
            and nothing about the wrapping mechanism should change
            generation cost).
  2. R_F6  (3 models x 3 suites = 9 runs) -> results_v2/R_F6/
            llama3, llama31, gemma3_4b (the only held-out models whose
            sampling actually changes; the other 7 held-out models map
            to R's folder instead, see configs/analysis_official_folders.yaml)
  3. R_F3  (5 models x 3 suites = 15 runs) -> results_v2/R_F3/
            llama31, phi4_mini, granite30, granite31, granite32 (the
            only held-out models with a real native tool template; the
            other 5 map to R's folder)

42 runs total, 900 records each, resumable, logged, backed up to
OneDrive every 8 completed runs (cumulative across all 3 phases). Never
touches results/, results_smoke/, or any other results_v2/<protocol>/
tree.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.real_run_models import SUITES  # noqa: E402

PHASES: list[tuple[str, list[str]]] = [
    ("F11", ["mistral_v01", "mistral_v02", "mistral_v03", "qwen2", "qwen25", "qwen3"]),
    ("R_F6", ["llama3", "llama31", "gemma3_4b"]),
    ("R_F3", ["llama31", "phi4_mini", "granite30", "granite31", "granite32"]),
]

LOG_PATH = REPO_ROOT / "results_v2" / "real_run_batch_rf6_rf3_f11_progress.log"
BACKUP_DIR = Path(r"C:\Users\Ibo\OneDrive\upgradecanary_backups")
BACKUP_EVERY = 8
REPORT_PATH = REPO_ROOT / "analysis" / "plan" / "batch_RF6_RF3_F11_report.md"


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def status_for(protocol: str, model_key: str, suite: str) -> dict | None:
    p = REPO_ROOT / "results_v2" / protocol / model_key / suite / "_status.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def is_done(protocol: str, model_key: str, suite: str) -> bool:
    s = status_for(protocol, model_key, suite)
    return bool(s and s.get("completed"))


def free_space_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / (1024 ** 3)


def backup(cumulative_done: int) -> None:
    import tempfile

    free_gb = free_space_gb(REPO_ROOT)
    source_size_gb = sum(f.stat().st_size for f in (REPO_ROOT / "results_v2").rglob("*") if f.is_file()) / (1024 ** 3)
    log(f"Disk free: {free_gb:.1f} GB; results_v2/ source size: {source_size_gb:.2f} GB")
    if free_gb < source_size_gb * 2 + 1:
        log("ABORTING BACKUP: not enough free space for a safe zip.")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    archive_name = f"results_v2_backup_{date_str}_RF6RF3F11_run{cumulative_done}"
    log(f"Backing up results_v2/ -> {archive_name}.zip ...")
    staging_dir = Path(tempfile.mkdtemp(prefix="upgradecanary_backup_"))
    try:
        archive_path = shutil.make_archive(str(staging_dir / archive_name), "zip", root_dir=str(REPO_ROOT / "results_v2"))
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        dest = BACKUP_DIR / f"{archive_name}.zip"
        shutil.copy(archive_path, dest)
        log(f"Backup copied to {dest} ({Path(archive_path).stat().st_size / (1024**2):.1f} MB)")
    except Exception as exc:
        log(f"BACKUP FAILED (continuing anyway): {type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def all_runs() -> list[tuple[str, str, str]]:
    runs = []
    for protocol, models in PHASES:
        for model_key in models:
            for suite in SUITES:
                runs.append((protocol, model_key, suite))
    return runs


def main() -> None:
    runs = all_runs()
    total = len(runs)
    cumulative_done = sum(1 for p, m, s in runs if is_done(p, m, s))
    log(f"F11/R_F6/R_F3 orchestrator starting. {cumulative_done}/{total} runs already complete.")

    for protocol, model_key, suite in runs:
        if is_done(protocol, model_key, suite):
            log(f"[{protocol}/{model_key}/{suite}] already complete, skipping.")
            continue
        log(f"[{protocol}/{model_key}/{suite}] launching (single run, {cumulative_done}/{total} done so far)...")
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "real_run_one.py"), model_key, suite, protocol],
            cwd=str(REPO_ROOT),
        )
        elapsed = time.perf_counter() - t0
        s = status_for(protocol, model_key, suite)
        if proc.returncode == 0 and s and s.get("completed"):
            cumulative_done += 1
            log(f"[{protocol}/{model_key}/{suite}] OK: {s.get('num_records')} records, {elapsed:.0f}s. Progress: {cumulative_done}/{total}.")
            if cumulative_done % BACKUP_EVERY == 0:
                backup(cumulative_done)
        else:
            err = (s or {}).get("error") or (s or {}).get("num_records")
            log(f"[{protocol}/{model_key}/{suite}] FAILED (exit {proc.returncode}, status={err}). Will retry on next launch.")

    still_pending = [f"{p}/{m}/{s}" for p, m, s in runs if not is_done(p, m, s)]
    if still_pending:
        log(f"Stopped for now. {len(still_pending)} runs still pending: {still_pending}")
        return

    log("All 42 runs complete. Writing final report.")
    write_final_report(runs)
    log(f"Final report written to {REPORT_PATH}")


def write_final_report(runs: list[tuple[str, str, str]]) -> None:
    def load_jsonl(p):
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    rows = []
    total_seconds = 0.0
    errors = []
    for protocol, model_key, suite in runs:
        s = status_for(protocol, model_key, suite) or {}
        total_seconds += s.get("elapsed_seconds", 0) or 0
        row = {"protocol": protocol, "model": model_key, "suite": suite, "status": s}
        if not s.get("completed"):
            errors.append(f"{protocol}/{model_key}/{suite}: {s.get('error', 'unknown')}")
        else:
            run_dir = Path(s["run_dir"])
            raw = load_jsonl(run_dir / "raw_outputs.jsonl")
            parsed = load_jsonl(run_dir / "parsed_results.jsonl")
            tool_call = [p for p in parsed if p["condition"] in ("baseline", "schema_drift")]
            row["parse_rate"] = sum(1 for p in tool_call if p["metrics"]["parse_ok"]) / len(tool_call) if tool_call else None
            row["truncation_rate"] = sum(1 for r in raw if r.get("truncated")) / len(raw) if raw else None
            greedy_base = [p for p in parsed if p["condition"] == "baseline" and p["trial_index"] == 0]
            row["greedy_baseline_acc"] = sum(p["metrics"]["score"] for p in greedy_base) / len(greedy_base) if greedy_base else None
        rows.append(row)

    lines = [
        "# F11 / R_F6 / R_F3 run report (2026-10-12)",
        "",
        "Three factors, each sharing a base protocol's config with one "
        "change (see DEVIATIONS.md for full definitions): F11 (D's "
        "config + this project's own legacy hand-typed chat wrapper, 6 "
        "models), R_F6 (R's config + F6's recommended sampling, 3 "
        "held-out models whose sampling actually changes), R_F3 (R's "
        "config + native tool template for the prompt, output still "
        "grammar-constrained, 5 held-out models with a real native "
        "template). 100 tasks each, baseline/schema_drift/"
        "fault_reporting, 1 greedy + 2 sampled trials. No verdicts, no "
        "comparison to D/R here -- record-keeping only, per instruction.",
        "",
        f"**Runs completed: {sum(1 for r in rows if r['status'].get('completed'))}/42**",
        f"**Total elapsed time: {total_seconds/3600:.1f} hours**",
        f"**Errors: {len(errors)}**",
        "",
        "| Protocol | Model | Suite | Records | Parse rate | Truncation rate | Greedy baseline acc | Seconds |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        s = r["status"]
        def fmt(x):
            return f"{x:.3f}" if isinstance(x, float) else "N/A"
        lines.append(
            f"| {r['protocol']} | {r['model']} | {r['suite']} | {s.get('num_records','?')} | {fmt(r.get('parse_rate'))} | "
            f"{fmt(r.get('truncation_rate'))} | {fmt(r.get('greedy_baseline_acc'))} | {s.get('elapsed_seconds', 0):.0f} |"
        )
    if errors:
        lines += ["", "## Errors", ""] + [f"- {e}" for e in errors]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
