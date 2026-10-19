"""Single laptop orchestrator for Phase 2 (PLAN_PHASE2.md v4 section 6).

    python -m scripts.phase2.run_laptop --dry-run            # show the queue, hours, what is already done
    python -m scripts.phase2.run_laptop                      # run it (resumable; completed runs are skipped)

Queue order (priority): W1 laptop (D and R first, then F1, F2, F3, F4, F5, F6) > W2 (R) > W2b > W2 (D),
and W3 last, only if its conditions hold (see ``w3_gate``). Every run is its own process
(``scripts.phase2.run_one``); a run counts as done only if its _status.json says the record count is
exactly right. An interrupted run is moved aside and redone. Results are backed up to OneDrive (zips
staged outside results folders) every ``--backup-every`` completed runs and at the end. No run is started
after the GPU deadline (10 Dec 2026).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.phase2.plan import GPU_DEADLINE, LAPTOP_PRIORITY, MANIFEST_DIR, W3_DEADLINE, load_manifest  # noqa: E402
from scripts.phase2.run_one import is_done  # noqa: E402

BACKUP_DIR = Path(r"C:\Users\Ibo\OneDrive\upgradecanary_backups")
LOG_NAME = "phase2_laptop_progress.log"
SPLIT_CHECK_R = Path("results_v3/W0_determinism/split_test/R_result.json")
PREREQ_FOR_W3 = ["W1_laptop", "W1_kaggle", "W2_R", "W2_D", "W2b"]


def log(root: Path, msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    p = root / "results_v3" / LOG_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def manifests_for_queue(names: list[str], directory: Path = MANIFEST_DIR) -> dict[str, dict]:
    return {n: load_manifest(n, directory) for n in names}


def w3_gate(today: date, manifests_dir: Path = MANIFEST_DIR, root: Path = REPO_ROOT) -> tuple[bool, str]:
    """W3 runs only if W1, W2 and W2b are complete by 20 Nov 2026 (a calendar condition, never a result
    condition), the R split-equivalence check has passed, and the added-task files exist."""
    if today > date.fromisoformat(W3_DEADLINE):
        return False, f"after {W3_DEADLINE}: W3 is skipped and reported as not run"
    for name in PREREQ_FOR_W3:
        m = load_manifest(name, manifests_dir)
        todo = [e["id"] for e in m["runs"] if not is_done(e, root)]
        if todo:
            return False, f"{name} not complete ({len(todo)} runs left, e.g. {todo[0]})"
    chk = root / SPLIT_CHECK_R
    try:
        ok = bool(json.loads(chk.read_text(encoding="utf-8")).get("all_identical"))
    except Exception:
        ok = False
    if not ok:
        return False, f"split-equivalence check for R has not passed ({SPLIT_CHECK_R})"
    w3 = load_manifest("W3", manifests_dir)
    missing = sorted({e["data"] for e in w3["runs"] if not (root / e["data"]).exists()})
    if missing:
        return False, f"added-task files missing: {missing}"
    return True, "ok"


def build_queue(names: list[str], directory: Path = MANIFEST_DIR, root: Path = REPO_ROOT) -> list[tuple[str, dict]]:
    out = []
    for n in names:
        m = load_manifest(n, directory)
        runs = sorted((e for e in m["runs"] if e["hardware"] == "laptop"), key=lambda e: e["order"])
        out += [(n, e) for e in runs]
    return out


def backup(root: Path, backup_dir: Path, done_count: int) -> Path | None:
    src = root / "results_v3"
    if not src.exists():
        return None
    free_gb = shutil.disk_usage(root).free / 1024 ** 3
    size_gb = sum(f.stat().st_size for f in src.rglob("*") if f.is_file()) / 1024 ** 3
    if free_gb < size_gb * 2 + 1:
        log(root, f"BACKUP SKIPPED: only {free_gb:.1f} GB free for a {size_gb:.2f} GB archive")
        return None
    name = f"results_v3_backup_{datetime.now().strftime('%Y-%m-%d')}_laptop_run{done_count}"
    staging = Path(tempfile.mkdtemp(prefix="upgradecanary_backup_"))     # outside every results folder
    try:
        archive = shutil.make_archive(str(staging / name), "zip", root_dir=str(src))
        backup_dir.mkdir(parents=True, exist_ok=True)
        dest = backup_dir / f"{name}.zip"
        shutil.copy(archive, dest)
        log(root, f"backup -> {dest} ({Path(archive).stat().st_size / 1024 ** 2:.1f} MB)")
        return dest
    except Exception as exc:  # noqa: BLE001
        log(root, f"BACKUP FAILED (continuing): {type(exc).__name__}: {exc}")
        return None
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help="restrict to these manifests (default: all, in priority order)")
    ap.add_argument("--include-w3", action="store_true", help="queue W3 if its conditions hold")
    ap.add_argument("--max-runs", type=int, default=None)
    ap.add_argument("--backup-every", type=int, default=8)
    ap.add_argument("--today", default=None, help="override today's date (YYYY-MM-DD), for testing")
    ap.add_argument("--manifests", default=str(MANIFEST_DIR))
    ap.add_argument("--root", default=str(REPO_ROOT))
    ap.add_argument("--backup-dir", default=str(BACKUP_DIR))
    args = ap.parse_args(argv)
    root, mdir = Path(args.root), Path(args.manifests)
    today = date.fromisoformat(args.today) if args.today else date.today()

    names = [n for n in LAPTOP_PRIORITY if args.only is None or n in args.only]
    if "W3" in names:
        if not args.include_w3:
            names.remove("W3")
        else:
            ok, why = w3_gate(today, mdir, root)
            log(root, f"W3 gate: {why}")
            if not ok:
                names.remove("W3")
    queue = build_queue(names, mdir, root)
    todo = [(n, e) for n, e in queue if not is_done(e, root)]
    done = len(queue) - len(todo)
    hours = sum(e["estimated_hours"] for _, e in todo)
    log(root, f"queue: {len(queue)} laptop runs ({done} already complete), {len(todo)} to do, ~{hours:.1f} h")

    if args.dry_run:
        cum = 0.0
        for i, (n, e) in enumerate(todo, start=1):
            cum += e["estimated_hours"]
            print(f"{i:4d}  {n:10s} {e['id']:42s} {e['estimated_hours']:6.2f} h  cumulative {cum:7.1f} h")
        return 0

    deadline = date.fromisoformat(GPU_DEADLINE)
    n_ok = 0
    for n, e in todo:
        if args.max_runs is not None and n_ok >= args.max_runs:
            break
        if (today if args.today else date.today()) > deadline:
            log(root, f"GPU deadline {GPU_DEADLINE} passed: no new runs are started")
            break
        log(root, f"[{e['id']}] launching ({n}, ~{e['estimated_hours']:.2f} h)")
        t0 = time.perf_counter()
        proc = subprocess.run([sys.executable, "-m", "scripts.phase2.run_one", n, e["id"]], cwd=str(root))
        el = time.perf_counter() - t0
        if proc.returncode == 0 and is_done(e, root):
            n_ok += 1
            log(root, f"[{e['id']}] OK in {el / 3600:.2f} h (estimate {e['estimated_hours']:.2f} h)")
            if n_ok % args.backup_every == 0:
                backup(root, Path(args.backup_dir), done + n_ok)
        else:
            log(root, f"[{e['id']}] FAILED (exit {proc.returncode}); will be redone on the next launch")
    if n_ok:
        backup(root, Path(args.backup_dir), done + n_ok)
    left = [e["id"] for _, e in queue if not is_done(e, root)]
    log(root, f"stopped: {n_ok} runs completed this launch, {len(left)} left")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
