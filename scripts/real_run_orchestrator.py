"""Orchestrator for PLAN v1's real D-protocol runs (2026-10-05): all 16
models x 3 suites = 48 full runs (100 tasks, baseline/schema_drift/
fault_reporting, 1 greedy + 2 sampled trials each). One model/suite at a
time, in its own subprocess (scripts/real_run_one.py) for crash/VRAM
isolation. Resumable: a (model, suite) pair whose _status.json already
shows completed=True is skipped, so relaunching this script after any
interruption (including the ~2h background-task ceiling) only does the
remaining runs. Logs to results_v2/real_run_progress.log in addition to
stdout. Backs up results_v2/ to OneDrive every 8 newly-completed runs.
Writes the final short report (no verdict analysis) once all 48 are done.
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

from scripts.real_run_models import all_runs  # noqa: E402

LOG_PATH = REPO_ROOT / "results_v2" / "real_run_progress.log"
BACKUP_DIR = Path(r"C:\Users\Ibo\OneDrive\upgradecanary_backups")
BACKUP_EVERY = 8
REPORT_PATH = REPO_ROOT / "analysis" / "plan" / "real_run_D_report.md"


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def status_for(model_key: str, suite: str) -> dict | None:
    p = REPO_ROOT / "results_v2" / "D" / model_key / suite / "_status.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def is_done(model_key: str, suite: str) -> bool:
    s = status_for(model_key, suite)
    return bool(s and s.get("completed"))


def backup(cumulative_done: int) -> None:
    import tempfile

    date_str = datetime.now().strftime("%Y-%m-%d")
    zip_base = REPO_ROOT / "results_v2"
    archive_name = f"results_v2_backup_{date_str}_run{cumulative_done}"
    log(f"Backing up results_v2/ -> {archive_name}.zip ...")
    # 2026-10-05 bug found live: writing the archive INTO a subdirectory
    # of results_v2/ while also zipping results_v2/ as root_dir caused
    # runaway self-inclusion (the growing zip got swept into itself) --
    # it reached 47 GB and filled the disk to 100% before failing, which
    # then crashed the next run too. Fixed: stage the archive in a system
    # temp directory, fully outside the tree being zipped.
    staging_dir = Path(tempfile.mkdtemp(prefix="upgradecanary_backup_"))
    try:
        archive_path = shutil.make_archive(str(staging_dir / archive_name), "zip", root_dir=str(zip_base))
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        dest = BACKUP_DIR / f"{archive_name}.zip"
        shutil.copy(archive_path, dest)
        log(f"Backup copied to {dest}")
    except Exception as exc:
        log(f"BACKUP FAILED (continuing anyway): {type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def main() -> None:
    runs = all_runs()
    total = len(runs)
    cumulative_done = sum(1 for model_key, _, suite, _ in runs if is_done(model_key, suite))
    log(f"Orchestrator starting. {cumulative_done}/{total} runs already complete.")

    for model_key, gguf_path, suite, data_path in runs:
        if is_done(model_key, suite):
            log(f"[{model_key}/{suite}] already complete, skipping.")
            continue
        log(f"[{model_key}/{suite}] launching ({cumulative_done}/{total} done so far)...")
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "real_run_one.py"), model_key, suite],
            cwd=str(REPO_ROOT),
        )
        elapsed = time.perf_counter() - t0
        s = status_for(model_key, suite)
        if proc.returncode == 0 and s and s.get("completed"):
            cumulative_done += 1
            log(
                f"[{model_key}/{suite}] OK: {s.get('num_records')} records, "
                f"{elapsed:.0f}s. Progress: {cumulative_done}/{total}."
            )
            if cumulative_done % BACKUP_EVERY == 0:
                backup(cumulative_done)
        else:
            err = (s or {}).get("error") or (s or {}).get("num_records")
            log(f"[{model_key}/{suite}] FAILED (exit {proc.returncode}, status={err}). Will retry on next launch.")

    still_pending = [f"{m}/{s}" for m, _, s, _ in runs if not is_done(m, s)]
    if still_pending:
        log(f"Stopped for now. {len(still_pending)} runs still pending: {still_pending}")
        return

    log("All 48 runs complete. Writing final report.")
    write_final_report(runs)
    log(f"Final report written to {REPORT_PATH}")


def write_final_report(runs: list[tuple[str, str, str, str]]) -> None:
    rows = []
    total_seconds = 0.0
    errors = []
    for model_key, _, suite, _ in runs:
        s = status_for(model_key, suite) or {}
        rows.append(s)
        total_seconds += s.get("elapsed_seconds", 0) or 0
        if not s.get("completed"):
            errors.append(f"{model_key}/{suite}: {s.get('error', 'unknown')}")

    lines = [
        "# PLAN v1 real D-protocol runs: completion report (2026-10-05)",
        "",
        "All 48 runs (16 models x 3 suites), 100 tasks each, "
        "baseline/schema_drift/fault_reporting, 1 greedy + 2 sampled trials. "
        "No verdict analysis here -- record-keeping only, per instruction.",
        "",
        f"**Runs completed: {sum(1 for r in rows if r.get('completed'))}/48**",
        f"**Total elapsed time across all runs: {total_seconds/3600:.1f} hours**",
        f"**Errors: {len(errors)}**",
        "",
        "| Model | Suite | Records | Expected | Seconds | run_dir |",
        "|---|---|---|---|---|---|",
    ]
    for s in rows:
        lines.append(
            f"| {s.get('model_key','?')} | {s.get('suite','?')} | {s.get('num_records','?')} | "
            f"{s.get('expected_records','?')} | {s.get('elapsed_seconds', 0):.0f} | {s.get('run_dir','?')} |"
        )
    if errors:
        lines += ["", "## Errors", ""] + [f"- {e}" for e in errors]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
