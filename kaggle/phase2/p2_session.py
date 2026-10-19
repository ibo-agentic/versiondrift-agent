"""Notebook-side helpers for the Phase 2 Kaggle runner (kept out of the .ipynb so they are testable):
choose a batch, restore finished runs from earlier sessions, launch the two per-GPU workers, status table."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import p2_worker  # noqa: E402


def pick_batch(repo: Path, batch: str = "next") -> dict:
    """The named batch, or (``next``) the first batch with a run that is not complete yet."""
    m = p2_worker.load_manifest(repo)
    by_id = {e["id"]: e for e in m["runs"]}
    if batch != "next":
        return next(b for b in m["batches"] if b["id"] == batch)
    for b in m["batches"]:
        if any(not p2_worker.is_done(repo, by_id[r]) for lane in b["lanes"] for r in lane["runs"]):
            return b
    raise SystemExit("every batch is complete")


def status_table(repo: Path, batch: dict) -> str:
    m = p2_worker.load_manifest(repo)
    by_id = {e["id"]: e for e in m["runs"]}
    rows, done = [], 0
    for i, lane in enumerate(batch["lanes"]):
        for r in lane["runs"]:
            d = p2_worker.is_done(repo, by_id[r])
            done += d
            rows.append(f"{'OK ' if d else '-- '} lane{i} {r:40s} ~{by_id[r]['estimated_hours']:.2f} h")
    return f"batch {batch['id']}: {done}/{len(rows)} runs complete\n" + "\n".join(rows)


def restore_from_inputs(repo: Path, export_dir: Path, input_root: str | Path = "/kaggle/input") -> list[str]:
    """Bring back runs finished in earlier sessions (p2__*.zip attached as an Input). Each zip passes the same
    verification as the laptop import and never overwrites a run that is already complete."""
    sys.path.insert(0, str(repo))
    from scripts.phase2.import_kaggle import verify_run_zip

    m = p2_worker.load_manifest(repo)
    entries = {e["id"]: e for e in m["runs"]}
    out = []
    root = Path(input_root)
    for z in (sorted(root.rglob("p2__*.zip")) if root.exists() else []):
        entry, problems = verify_run_zip(z, entries)
        if problems:
            out.append(f"SKIP {z.name}: {'; '.join(problems[:2])}")
        elif p2_worker.is_done(repo, entry):
            out.append(f"already have {entry['id']}")
        else:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(repo)
            export_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(z, export_dir / z.name)
            out.append(f"RESTORED {entry['id']} from {z.name}")
    return out


def launch_workers(repo: Path, models_dir: Path, state_dir: Path, export_dir: Path, batch_id: str, deadline_epoch: float,
                   repo_commit: str | None, hard_limit_epoch: float | None = None, python: str | None = None,
                   extra_env: dict | None = None, gpus=("0", "1")) -> list[subprocess.Popen]:
    state_dir.mkdir(parents=True, exist_ok=True)
    procs = []
    for g in gpus:
        env = dict(os.environ, **(extra_env or {}), CUDA_VISIBLE_DEVICES=g)
        out = open(state_dir / f"p2_stdout_gpu{g}.log", "a", encoding="utf-8")
        cmd = [python or sys.executable, str(HERE / "p2_worker.py"), "--repo", str(repo), "--models-dir", str(models_dir),
               "--state-dir", str(state_dir), "--export-dir", str(export_dir), "--batch", batch_id,
               "--deadline-epoch", str(deadline_epoch)]
        if hard_limit_epoch:
            cmd += ["--hard-limit-epoch", str(hard_limit_epoch)]
        if repo_commit:
            cmd += ["--repo-commit", repo_commit]
        procs.append(subprocess.Popen(cmd, env=env, stdout=out, stderr=subprocess.STDOUT, cwd=str(repo)))
    return procs


def monitor(procs: list[subprocess.Popen], state_dir: Path, every: int = 120) -> None:
    while any(p.poll() is None for p in procs):
        time.sleep(every)
        for g in ("0", "1"):
            lf = state_dir / f"p2_worker_gpu{g}.log"
            if lf.exists():
                tail = lf.read_text(encoding="utf-8").splitlines()[-2:]
                print(f"--- gpu{g}: " + " | ".join(t[-160:] for t in tail), flush=True)
    print("workers exited:", [p.returncode for p in procs])
