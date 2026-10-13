"""Notebook-side helpers (kept out of the .ipynb so they are reviewable,
testable and diffable): locate/copy the repo, restore finished runs from
earlier sessions, launch the two per-GPU workers, print a status table.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kaggle_plan as plan  # noqa: E402
import kaggle_verify  # noqa: E402
import kaggle_worker  # noqa: E402


# --------------------------------------------------------------------- repo
def find_repo_in_inputs(input_root: str | Path = "/kaggle/input") -> Path | None:
    """Return a directory under input_root that holds the project (has
    upgradecanary/runner.py), extracting a repo zip into /kaggle/working first
    if the dataset kept it as a zip."""
    root = Path(input_root)
    if not root.exists():
        return None
    for p in sorted(root.rglob("runner.py")):
        if p.parent.name == "upgradecanary" and len(p.relative_to(root).parts) <= 6:
            return p.parent.parent
    for z in sorted(root.rglob("*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                if any(n.endswith("upgradecanary/runner.py") for n in zf.namelist()):
                    out = Path("/kaggle/working/_repo_unzip")
                    shutil.rmtree(out, ignore_errors=True)
                    zf.extractall(out)
                    return find_repo_in_inputs(out)
        except zipfile.BadZipFile:
            continue
    return None


def copy_repo(src: Path, dest: Path) -> Path:
    if dest.exists():
        # Keep results from this same session if the cell is re-run.
        for item in src.iterdir():
            target = dest / item.name
            if item.name == "results_v2":
                continue
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)
    else:
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    return dest


def read_commit(repo: Path) -> str | None:
    f = repo / "REPO_COMMIT.txt"
    return f.read_text(encoding="utf-8").strip() if f.exists() else None


# ------------------------------------------------------------------ restore
def _zip_run_dir(run_root: Path, protocol: str, model: str, suite: str, dest_zip: Path) -> None:
    """Pack an already-extracted run folder (from a dataset that Kaggle
    auto-extracted) into the same zip shape the workers produce."""
    src = run_root / protocol / model / suite
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.write(p, ("results_v2/" + p.relative_to(run_root).as_posix()))
        cfg = run_root / "_generated_configs" / f"{protocol}__{model}__{suite}.yaml"
        if cfg.exists():
            zf.write(cfg, f"results_v2/_generated_configs/{cfg.name}")


def restore_from_inputs(repo: Path, export_dir: Path, input_root: str | Path = "/kaggle/input",
                        extra_zip_dirs: tuple[str, ...] = ()) -> list[str]:
    """Bring back runs finished in earlier sessions. Looks (read-only) under
    /kaggle/input for kaggle__*.zip files and for extracted
    results_v2/<protocol>/<model>/<suite>/ folders. Every candidate must pass
    the same verification the laptop import uses. Never overwrites a run that
    is already complete in this session. Returns a log of what happened."""
    out: list[str] = []
    cands: list[tuple[str, Path | None, tuple[str, str, str] | None, Path | None]] = []
    roots = [Path(input_root)] + [Path(d) for d in extra_zip_dirs]
    for root in roots:
        if not root.exists():
            continue
        for z in sorted(root.rglob("kaggle__*.zip")):
            cands.append(("zip", z, None, None))
        for st in sorted(root.rglob("_status.json")):
            parts = st.parent.parts
            if len(parts) >= 4 and "results_v2" in parts:
                i = len(parts) - 1 - parts[::-1].index("results_v2")
                rel = parts[i + 1:]
                if len(rel) == 3 and rel[0] in plan.PROTOCOLS:
                    cands.append(("dir", None, tuple(rel), Path(*parts[: i + 1])))
    seen: set[tuple[str, str, str]] = set()
    tmp = Path(tempfile.mkdtemp(prefix="restore_"))
    try:
        for kind, z, triple, run_root in cands:
            zpath = z
            if kind == "dir":
                zpath = tmp / ("dir__" + "__".join(triple) + ".zip")
                try:
                    _zip_run_dir(run_root, *triple, zpath)  # type: ignore[arg-type]
                except Exception as exc:  # noqa: BLE001
                    out.append(f"SKIP {run_root}/{'/'.join(triple)}: cannot pack ({exc})")
                    continue
            res = kaggle_verify.verify_run_zip(zpath)
            label = str(z or "/".join(triple))  # type: ignore[arg-type]
            if not res.ok:
                out.append(f"SKIP {label}: {'; '.join(res.problems[:3])}")
                continue
            key = (res.info["protocol"], res.info["model"], res.info["suite"])
            if key in seen or kaggle_worker.is_done(repo, *key):
                out.append(f"already have {'/'.join(key)}")
                seen.add(key)
                continue
            seen.add(key)
            with zipfile.ZipFile(zpath) as zf:
                zf.extractall(repo)
            export_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(zpath, export_dir / f"kaggle__{key[0]}__{key[1]}__{key[2]}.zip")
            out.append(f"RESTORED {'/'.join(key)} from {label}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


# ------------------------------------------------------------------- launch
def launch_workers(repo: Path, models_dir: Path, state_dir: Path, export_dir: Path, phases, deadline_epoch: float,
                   repo_commit: str | None, gpus=("0", "1"),
                   hard_limit_epoch: float | None = None, python: str | None = None,
                   extra_env: dict | None = None) -> list[subprocess.Popen]:
    shutil.rmtree(state_dir / "claims", ignore_errors=True)  # claims are per session
    state_dir.mkdir(parents=True, exist_ok=True)
    procs = []
    for g in gpus:
        env = dict(os.environ, **(extra_env or {}), CUDA_VISIBLE_DEVICES=g)
        out = open(state_dir / f"stdout_gpu{g}.log", "a", encoding="utf-8")
        cmd = [python or sys.executable, str(HERE / "kaggle_worker.py"), "--repo", str(repo), "--models-dir", str(models_dir),
               "--state-dir", str(state_dir), "--export-dir", str(export_dir), "--phases", *phases,
               "--deadline-epoch", str(deadline_epoch)]
        if hard_limit_epoch:
            cmd += ["--hard-limit-epoch", str(hard_limit_epoch)]
        if repo_commit:
            cmd += ["--repo-commit", repo_commit]
        procs.append(subprocess.Popen(cmd, env=env, stdout=out, stderr=subprocess.STDOUT, cwd=str(repo)))
    return procs


def status_table(repo: Path, phases) -> str:
    rows = []
    done = 0
    for protocol, model, suite in plan.all_jobs(tuple(phases)):
        d = kaggle_worker.is_done(repo, protocol, model, suite)
        done += d
        rows.append(f"{'OK ' if d else '-- '} {protocol:15s} {model:12s} {suite}")
    return f"{done}/{len(rows)} runs complete\n" + "\n".join(rows)


def monitor(procs: list[subprocess.Popen], state_dir: Path, every: int = 120) -> None:
    """Block until all workers exit, printing the tail of each worker log."""
    while any(p.poll() is None for p in procs):
        time.sleep(every)
        for g in ("0", "1"):
            lf = state_dir / f"worker_gpu{g}.log"
            if lf.exists():
                tail = lf.read_text(encoding="utf-8").splitlines()[-2:]
                print(f"--- gpu{g}: " + " | ".join(t[-160:] for t in tail), flush=True)
    print("workers exited:", [p.returncode for p in procs])
