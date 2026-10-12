"""Orchestrator for F5 (Q8_0) on the laptop's 5 small models, in this order:

  1. F5    (5 models x 3 suites = 15 runs) -> results_v2/F5/
            D's config + Q8_0 file only (max_tokens 256, no grammar)
  2. R_F5  (5 models x 3 suites = 15 runs) -> results_v2/R_F5/
            R's config + Q8_0 file only (max_tokens 1024, generic_json)

Models (fast to slow by D's own timings): gemma2_2b, phi3_mini, phi4_mini,
gemma3_4b, phi35_mini. 30 runs, 900 records each, resumable, logged, backed
up to OneDrive every 8 completed runs. The 8B models' F5/R_F5 run on Kaggle
(kaggle/) into the SAME results_v2/F5 and results_v2/R_F5 folders under their
own model directories.

Pre-flight: refuses to start if any Q8_0 file is missing or has the wrong
size (see docs/model_manifest.md section 7) -- never falls back to Q4_K_M.
Never touches results/, results_smoke/ or any other results_v2/<protocol>/.
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

SMALL_MODELS = ["gemma2_2b", "phi3_mini", "phi4_mini", "gemma3_4b", "phi35_mini"]
PHASES: list[tuple[str, list[str]]] = [("F5", SMALL_MODELS), ("R_F5", SMALL_MODELS)]
# bytes, from each file's HF tree entry (docs/model_manifest.md section 7)
EXPECTED_SIZES = {
    "gemma2_2b": 2784495456, "gemma3_4b": 4130226592, "phi3_mini": 4061221376,
    "phi35_mini": 4061222688, "phi4_mini": 4084611456,
}

LOG_PATH = REPO_ROOT / "results_v2" / "real_run_f5_small_progress.log"
BACKUP_DIR = Path(r"C:\Users\Ibo\OneDrive\upgradecanary_backups")
BACKUP_EVERY = 8
REPORT_PATH = REPO_ROOT / "analysis" / "plan" / "F5_small_report.md"


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


def all_runs() -> list[tuple[str, str, str]]:
    return [(p, m, s) for p, models in PHASES for m in models for s in SUITES]


def preflight() -> list[str]:
    """Problems that must be fixed before any run (empty list = OK)."""
    from scripts.real_run_one import Q8_0_MODEL_PATHS

    problems = []
    for m in SMALL_MODELS:
        path = REPO_ROOT / Q8_0_MODEL_PATHS[m]
        if not path.exists():
            problems.append(f"{m}: missing {path}")
        elif path.stat().st_size != EXPECTED_SIZES[m]:
            problems.append(f"{m}: {path} is {path.stat().st_size} bytes, expected {EXPECTED_SIZES[m]}")
    return problems


def backup(cumulative_done: int) -> None:
    import tempfile

    free_gb = shutil.disk_usage(REPO_ROOT).free / (1024 ** 3)
    source_gb = sum(f.stat().st_size for f in (REPO_ROOT / "results_v2").rglob("*") if f.is_file()) / (1024 ** 3)
    log(f"Disk free: {free_gb:.1f} GB; results_v2/ source size: {source_gb:.2f} GB")
    if free_gb < source_gb * 2 + 1:
        log("ABORTING BACKUP: not enough free space for a safe zip.")
        return
    name = f"results_v2_backup_{datetime.now().strftime('%Y-%m-%d')}_F5small_run{cumulative_done}"
    staging = Path(tempfile.mkdtemp(prefix="upgradecanary_backup_"))
    try:
        archive = shutil.make_archive(str(staging / name), "zip", root_dir=str(REPO_ROOT / "results_v2"))
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(archive, BACKUP_DIR / f"{name}.zip")
        log(f"Backup copied to {BACKUP_DIR / (name + '.zip')}")
    except Exception as exc:  # noqa: BLE001
        log(f"BACKUP FAILED (continuing anyway): {type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> int:
    problems = preflight()
    if problems:
        log("PRE-FLIGHT FAILED, not starting:\n  " + "\n  ".join(problems))
        return 2
    runs = all_runs()
    total = len(runs)
    done = sum(1 for p, m, s in runs if is_done(p, m, s))
    log(f"F5-small orchestrator starting. {done}/{total} runs already complete.")

    for protocol, model_key, suite in runs:
        if is_done(protocol, model_key, suite):
            log(f"[{protocol}/{model_key}/{suite}] already complete, skipping.")
            continue
        log(f"[{protocol}/{model_key}/{suite}] launching ({done}/{total} done so far)...")
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "real_run_one.py"), model_key, suite, protocol],
            cwd=str(REPO_ROOT),
        )
        elapsed = time.perf_counter() - t0
        s = status_for(protocol, model_key, suite)
        if proc.returncode == 0 and s and s.get("completed"):
            done += 1
            log(f"[{protocol}/{model_key}/{suite}] OK: {s.get('num_records')} records, {elapsed:.0f}s. Progress: {done}/{total}.")
            if done % BACKUP_EVERY == 0:
                backup(done)
        else:
            err = (s or {}).get("error") or (s or {}).get("num_records")
            log(f"[{protocol}/{model_key}/{suite}] FAILED (exit {proc.returncode}, status={err}). Will retry on next launch.")

    pending = [f"{p}/{m}/{s}" for p, m, s in runs if not is_done(p, m, s)]
    if pending:
        log(f"Stopped for now. {len(pending)} runs still pending: {pending}")
        return 1
    log(f"All {total} runs complete. Writing final report.")
    write_final_report(runs)
    log(f"Final report written to {REPORT_PATH}")
    return 0


def write_final_report(runs: list[tuple[str, str, str]]) -> None:
    def load_jsonl(p: Path) -> list[dict]:
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

    rows, total_s, errors = [], 0.0, []
    for protocol, model_key, suite in runs:
        s = status_for(protocol, model_key, suite) or {}
        total_s += s.get("elapsed_seconds", 0) or 0
        row = {"protocol": protocol, "model": model_key, "suite": suite, "status": s}
        if not s.get("completed"):
            errors.append(f"{protocol}/{model_key}/{suite}: {s.get('error', 'unknown')}")
        else:
            run_dir = Path(s["run_dir"])
            raw, parsed = load_jsonl(run_dir / "raw_outputs.jsonl"), load_jsonl(run_dir / "parsed_results.jsonl")
            tc = [p for p in parsed if p["condition"] in ("baseline", "schema_drift")]
            row["parse_rate"] = sum(1 for p in tc if p["metrics"]["parse_ok"]) / len(tc) if tc else None
            row["truncation_rate"] = sum(1 for r in raw if r.get("truncated")) / len(raw) if raw else None
        rows.append(row)

    def fmt(x):
        return f"{x:.3f}" if isinstance(x, float) else "N/A"

    lines = [
        "# F5 / R_F5 (Q8_0) run report, small models (laptop)",
        "",
        "gemma2_2b, gemma3_4b, phi3_mini, phi35_mini, phi4_mini; 3 suites; F5 = D's config + Q8_0 file, "
        "R_F5 = R's config + Q8_0 file. Record-keeping only: no verdicts, no comparison to D/R.",
        "",
        f"**Runs completed: {sum(1 for r in rows if r['status'].get('completed'))}/{len(runs)}**",
        f"**Total elapsed time: {total_s / 3600:.1f} hours**",
        f"**Errors: {len(errors)}**",
        "",
        "| Protocol | Model | Suite | Records | Parse rate | Truncation rate | Seconds |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        s = r["status"]
        lines.append(f"| {r['protocol']} | {r['model']} | {r['suite']} | {s.get('num_records', '?')} | "
                     f"{fmt(r.get('parse_rate'))} | {fmt(r.get('truncation_rate'))} | {s.get('elapsed_seconds', 0):.0f} |")
    if errors:
        lines += ["", "## Errors", ""] + [f"- {e}" for e in errors]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
