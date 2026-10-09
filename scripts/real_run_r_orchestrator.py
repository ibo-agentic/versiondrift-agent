"""Orchestrator for R (robust protocol, PLAN.md section 7, 2026-10-09): all
16 models x 3 suites = 48 full runs (900 records each), fast-to-slow order
(Qwen3 last), resumable, logged, backed up to OneDrive every 8 completed
runs. Writes to results_v2/R/, never results/, results_smoke/, or any
other results_v2/<protocol>/ tree.

R = D + max_tokens=1024 (section 7 item 1) + generic_json constrained
decoding (item 2) -- confirmed field-by-field in DEVIATIONS.md,
2026-10-09. Items 3-6 are reporting/gating rules, not generation config.

Qwen3's grammar also structurally blocks its <think> block, same
mechanism as F4_json -- its results carry the same "grammar + thinking
blocked" label. All 3 of its suites are pre-split ahead of time (not
reactive): the quick test's linear extrapolation put all 3 suites at
60-90 minutes, nominally under the 2-hour ceiling, but F4's full-scale
run showed real timing can diverge from quick-test extrapolation on the
slow side (the ~2.6% repetition-loop rate was invisible at quick-test
scale), and R's larger 1024-token budget means any looping record burns
through up to 4x more tokens before truncating. See DEVIATIONS.md.
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

from scripts.real_run_models import MODEL_ORDER, SUITES  # noqa: E402

PROTOCOL = "R"
PRESPLIT = {("qwen3", "synthetic"), ("qwen3", "bfcl_simple"), ("qwen3", "bfcl_multiple")}

LOG_PATH = REPO_ROOT / "results_v2" / "real_run_r_progress.log"
BACKUP_DIR = Path(r"C:\Users\Ibo\OneDrive\upgradecanary_backups")
BACKUP_EVERY = 8
REPORT_PATH = REPO_ROOT / "analysis" / "plan" / "R_report.md"


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def status_for(model_key: str, suite: str) -> dict | None:
    p = REPO_ROOT / "results_v2" / PROTOCOL / model_key / suite / "_status.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def is_done(model_key: str, suite: str) -> bool:
    s = status_for(model_key, suite)
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
    archive_name = f"results_v2_backup_{date_str}_R_run{cumulative_done}"
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


def all_r_runs() -> list[tuple[str, str]]:
    runs = []
    for model_key, _ in MODEL_ORDER:
        for suite in SUITES:
            runs.append((model_key, suite))
    return runs


def main() -> None:
    runs = all_r_runs()
    total = len(runs)
    cumulative_done = sum(1 for m, s in runs if is_done(m, s))
    log(f"R orchestrator starting. {cumulative_done}/{total} runs already complete.")

    for model_key, suite in runs:
        if is_done(model_key, suite):
            log(f"[{model_key}/{suite}] already complete, skipping.")
            continue
        presplit = (model_key, suite) in PRESPLIT
        script = "split_run.py" if presplit else "real_run_one.py"
        args = [model_key, suite, PROTOCOL]
        log(f"[{model_key}/{suite}] launching ({'pre-split' if presplit else 'single run'}, "
            f"{cumulative_done}/{total} done so far)...")
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / script)] + args,
            cwd=str(REPO_ROOT),
        )
        elapsed = time.perf_counter() - t0
        s = status_for(model_key, suite)
        if proc.returncode == 0 and s and s.get("completed"):
            cumulative_done += 1
            log(f"[{model_key}/{suite}] OK: {s.get('num_records')} records, {elapsed:.0f}s. Progress: {cumulative_done}/{total}.")
            if cumulative_done % BACKUP_EVERY == 0:
                backup(cumulative_done)
        else:
            err = (s or {}).get("error") or (s or {}).get("num_records")
            log(f"[{model_key}/{suite}] FAILED (exit {proc.returncode}, status={err}). Will retry on next launch.")

    still_pending = [f"{m}/{s}" for m, s in runs if not is_done(m, s)]
    if still_pending:
        log(f"Stopped for now. {len(still_pending)} runs still pending: {still_pending}")
        return

    log("All 48 R runs complete. Writing final report.")
    write_final_report(runs)
    log(f"Final report written to {REPORT_PATH}")


def write_final_report(runs: list[tuple[str, str]]) -> None:
    def load_jsonl(p):
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    rows = []
    total_seconds = 0.0
    errors = []
    for model_key, suite in runs:
        s = status_for(model_key, suite) or {}
        total_seconds += s.get("elapsed_seconds", 0) or 0
        row = {"model": model_key, "suite": suite, "status": s}
        if not s.get("completed"):
            errors.append(f"{model_key}/{suite}: {s.get('error', 'unknown')}")
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
        "# R (robust protocol) run report (2026-10-09)",
        "",
        "All 16 models x 3 suites, 100 tasks each, baseline/schema_drift/"
        "fault_reporting, 1 greedy + 2 sampled trials. R = D + "
        "max_tokens=1024 + constrained_decoding: generic_json (PLAN.md "
        "section 7 items 1-2); everything else unchanged from D. "
        "fault_reporting is NOT grammar-constrained (its envelope shape "
        "differs from the generic_json schema). Qwen3's grammar also "
        "structurally blocks its <think> block -- its results carry a "
        "separate label below. No verdicts, no comparison to D here -- "
        "record-keeping only, per instruction.",
        "",
        f"**Runs completed: {sum(1 for r in rows if r['status'].get('completed'))}/48**",
        f"**Total elapsed time: {total_seconds/3600:.1f} hours**",
        f"**Errors: {len(errors)}**",
        "",
        "| Model | Suite | Records | Parse rate | Truncation rate | Greedy baseline acc | Seconds |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        s = r["status"]
        def fmt(x):
            return f"{x:.3f}" if isinstance(x, float) else "N/A"
        label = " [grammar + thinking blocked]" if r["model"] == "qwen3" else ""
        lines.append(
            f"| {r['model']}{label} | {r['suite']} | {s.get('num_records','?')} | {fmt(r.get('parse_rate'))} | "
            f"{fmt(r.get('truncation_rate'))} | {fmt(r.get('greedy_baseline_acc'))} | {s.get('elapsed_seconds', 0):.0f} |"
        )
    if errors:
        lines += ["", "## Errors", ""] + [f"- {e}" for e in errors]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
