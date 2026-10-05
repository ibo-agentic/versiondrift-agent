"""Orchestrator for F2 (Qwen3 thinking off, 2026-10-05): qwen3 x 3 suites,
full size (900 records each). One run at a time, resumable, logged.
Backs up results_v2/ to OneDrive at the end (checking disk space first --
this protocol's backup function was already fixed for the run-into-itself
bug found during the D-protocol runs; see scripts/real_run_orchestrator.py).
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

from scripts.real_run_models import EXPECTED_RECORDS_PER_RUN, MODEL_ORDER, SUITES  # noqa: E402

PROTOCOL = "F2"
MODEL_KEY = "qwen3"
GGUF_PATH = dict(MODEL_ORDER)[MODEL_KEY]
LOG_PATH = REPO_ROOT / "results_v2" / "real_run_f2_progress.log"
BACKUP_DIR = Path(r"C:\Users\Ibo\OneDrive\upgradecanary_backups")
REPORT_PATH = REPO_ROOT / "analysis" / "plan" / "F2_report.md"


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def status_for(suite: str) -> dict | None:
    p = REPO_ROOT / "results_v2" / PROTOCOL / MODEL_KEY / suite / "_status.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def is_done(suite: str) -> bool:
    s = status_for(suite)
    return bool(s and s.get("completed"))


def free_space_gb(path: Path) -> float:
    usage = shutil.disk_usage(path)
    return usage.free / (1024 ** 3)


def backup() -> None:
    import tempfile

    free_gb = free_space_gb(REPO_ROOT)
    log(f"Disk free before backup: {free_gb:.1f} GB")
    source_size_gb = sum(f.stat().st_size for f in (REPO_ROOT / "results_v2").rglob("*") if f.is_file()) / (1024 ** 3)
    log(f"results_v2/ source size: {source_size_gb:.2f} GB")
    if free_gb < source_size_gb * 2 + 1:
        log(f"ABORTING BACKUP: not enough free space ({free_gb:.1f} GB) for a safe zip of "
            f"{source_size_gb:.2f} GB of source data.")
        return

    date_str = datetime.now().strftime("%Y-%m-%d")
    archive_name = f"results_v2_backup_{date_str}_F2"
    log(f"Backing up results_v2/ -> {archive_name}.zip ...")
    # Staged in a system temp dir, fully OUTSIDE results_v2/ -- the exact
    # fix applied after the D-protocol run-into-itself bug (47GB runaway
    # file); never repeat that mistake.
    staging_dir = Path(tempfile.mkdtemp(prefix="upgradecanary_backup_"))
    try:
        archive_path = shutil.make_archive(
            str(staging_dir / archive_name), "zip", root_dir=str(REPO_ROOT / "results_v2")
        )
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        dest = BACKUP_DIR / f"{archive_name}.zip"
        shutil.copy(archive_path, dest)
        log(f"Backup copied to {dest} ({Path(archive_path).stat().st_size / (1024**2):.1f} MB)")
    except Exception as exc:
        log(f"BACKUP FAILED (continuing anyway): {type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def main() -> None:
    suites = list(SUITES.keys())
    log(f"F2 orchestrator starting. Model={MODEL_KEY}, suites={suites}.")

    for suite in suites:
        if is_done(suite):
            log(f"[{suite}] already complete, skipping.")
            continue
        log(f"[{suite}] launching...")
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "real_run_one.py"), MODEL_KEY, suite, PROTOCOL],
            cwd=str(REPO_ROOT),
        )
        elapsed = time.perf_counter() - t0
        s = status_for(suite)
        if proc.returncode == 0 and s and s.get("completed"):
            log(f"[{suite}] OK: {s.get('num_records')} records, {elapsed:.0f}s.")
        else:
            err = (s or {}).get("error") or (s or {}).get("num_records")
            log(f"[{suite}] FAILED (exit {proc.returncode}, status={err}). Will retry on next launch.")

    still_pending = [s for s in suites if not is_done(s)]
    if still_pending:
        log(f"Stopped for now. Pending: {still_pending}")
        return

    log("All F2 qwen3 runs complete.")
    backup()
    write_report(suites)
    log(f"Report written to {REPORT_PATH}")


def write_report(suites: list[str]) -> None:
    import sys as _sys
    _sys.path.insert(0, str(REPO_ROOT))
    from upgradecanary.evaluator import expected_fault_report
    from upgradecanary.perturbations.runtime_faults import Fault

    def load_jsonl(p):
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    rows = []
    total_seconds = 0.0
    errors = []
    for suite in suites:
        s = status_for(suite) or {}
        total_seconds += s.get("elapsed_seconds", 0) or 0
        if not s.get("completed"):
            errors.append(f"{suite}: {s.get('error', 'unknown')}")
            rows.append({"suite": suite, "status": s})
            continue
        run_dir = Path(s["run_dir"])
        raw = load_jsonl(run_dir / "raw_outputs.jsonl")
        parsed = load_jsonl(run_dir / "parsed_results.jsonl")
        tool_call = [p for p in parsed if p["condition"] in ("baseline", "schema_drift")]
        parse_rate = sum(1 for p in tool_call if p["metrics"]["parse_ok"]) / len(tool_call) if tool_call else None
        trunc_rate = sum(1 for r in raw if r.get("truncated")) / len(raw) if raw else None
        greedy_base = [p for p in parsed if p["condition"] == "baseline" and p["trial_index"] == 0]
        greedy_acc = sum(p["metrics"]["score"] for p in greedy_base) / len(greedy_base) if greedy_base else None
        rows.append({
            "suite": suite, "status": s, "parse_rate": parse_rate,
            "truncation_rate": trunc_rate, "greedy_baseline_acc": greedy_acc,
        })

    lines = [
        "# F2 (Qwen3 thinking off) run report (2026-10-05)",
        "",
        "Qwen3 only, all 3 suites, full size (900 records each). "
        "No verdicts, no comparison to D yet -- record-keeping only, per instruction.",
        "",
        f"**Runs completed: {sum(1 for r in rows if r['status'].get('completed'))}/3**",
        f"**Total elapsed time: {total_seconds/60:.1f} minutes**",
        f"**Errors: {len(errors)}**",
        "",
        "| Suite | Records | Parse rate | Truncation rate | Greedy baseline acc | Seconds |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        s = r["status"]
        def fmt(x):
            return f"{x:.3f}" if isinstance(x, float) else "N/A"
        lines.append(
            f"| {r['suite']} | {s.get('num_records','?')} | {fmt(r.get('parse_rate'))} | "
            f"{fmt(r.get('truncation_rate'))} | {fmt(r.get('greedy_baseline_acc'))} | "
            f"{s.get('elapsed_seconds', 0):.0f} |"
        )
    if errors:
        lines += ["", "## Errors", ""] + [f"- {e}" for e in errors]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
