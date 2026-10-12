"""One worker per GPU. Started by the notebook with CUDA_VISIBLE_DEVICES set
to this worker's GPU, so each process sees exactly one T4.

A worker repeatedly: claims a bundle (one model file + all runs that use it),
downloads + hash-verifies the GGUF straight from Hugging Face, runs each
(protocol, suite) as its own subprocess (kaggle_run_one.py), zips every
finished run into the export dir, then deletes the GGUF.

Resumable: a run counts as done when its results_v2/<protocol>/<model>/<suite>/
_status.json says completed. Claims are per-session (cleared at launch).
A worker stops taking new runs once --deadline-epoch has passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kaggle_plan as plan  # noqa: E402


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Log:
    def __init__(self, path: Path, tag: str) -> None:
        self.path, self.tag = path, tag
        path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, msg: str) -> None:
        line = f"[{now()}] [{self.tag}] {msg}"
        print(line, flush=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def is_done(repo: Path, protocol: str, model: str, suite: str) -> bool:
    p = repo / plan.run_rel_dir(protocol, model, suite) / "_status.json"
    try:
        s = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(s.get("completed") and s.get("record_count_ok"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_and_verify(f: plan.GGUFFile, models_dir: Path, log: Log) -> dict:
    """Download one GGUF (resumable curl), verify size + SHA-256 against the
    hash the HF repo itself publishes. Returns the source record."""
    models_dir.mkdir(parents=True, exist_ok=True)
    dest = models_dir / f.filename
    part = models_dir / (f.filename + ".part")
    free = shutil.disk_usage(models_dir).free
    if free < f.size * 1.1 + 2 * 1024 ** 3:
        raise RuntimeError(f"not enough disk in {models_dir}: {free/1e9:.1f} GB free, need {f.size/1e9:.1f} GB")
    for attempt in (1, 2):
        if not dest.exists():
            log(f"downloading {f.url} ({f.size/1e9:.2f} GB), attempt {attempt}")
            for _ in range(5):
                rc = subprocess.run(["curl", "-L", "--fail", "-C", "-", "--retry", "5", "--retry-delay", "5",
                                     "--connect-timeout", "30", "-sS", "-o", str(part), f.url]).returncode
                if rc == 0:
                    break
                time.sleep(10)
            else:
                raise RuntimeError(f"download failed for {f.url}")
            part.rename(dest)
        size = dest.stat().st_size
        digest = sha256_file(dest)
        if size == f.size and digest == f.sha256:
            log(f"verified {f.filename}: sha256 {digest}")
            return {"repo": f.repo, "filename": f.filename, "url": f.url, "size_bytes": size,
                    "sha256_expected": f.sha256, "sha256_actual": digest,
                    "downloaded_utc": now()}
        log(f"HASH/SIZE MISMATCH for {f.filename}: size {size} (want {f.size}), sha256 {digest} (want {f.sha256}); "
            "deleting and retrying" if attempt == 1 else "giving up")
        dest.unlink(missing_ok=True)
    raise RuntimeError(f"{f.filename}: SHA-256 does not match the Hugging Face repo's published hash")


def make_run_zip(repo: Path, protocol: str, model: str, suite: str, export_dir: Path) -> Path:
    """Zip one finished run as results_v2/<protocol>/<model>/<suite>/** (+ its
    generated config), so 'unzip at the repo root' reproduces the laptop layout."""
    export_dir.mkdir(parents=True, exist_ok=True)
    rel = plan.run_rel_dir(protocol, model, suite)
    src = repo / rel
    tmp = export_dir / f".tmp__{protocol}__{model}__{suite}.zip"
    final = export_dir / f"kaggle__{protocol}__{model}__{suite}.zip"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(repo).as_posix())
        cfg = repo / "results_v2" / "_generated_configs" / f"{protocol}__{model}__{suite}.yaml"
        if cfg.exists():
            zf.write(cfg, cfg.relative_to(repo).as_posix())
    tmp.replace(final)
    return final


def quarantine_partial(repo: Path, protocol: str, model: str, suite: str, log: Log) -> None:
    """A failed/partial earlier attempt must not sit next to the retry (the
    analysis loader treats >1 run dir per suite as ambiguous)."""
    d = repo / plan.run_rel_dir(protocol, model, suite)
    if d.exists() and not is_done(repo, protocol, model, suite):
        dest = repo / "results_v2" / "_failed_attempts" / f"{protocol}__{model}__{suite}__{int(time.time())}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(d), str(dest))
        log(f"moved incomplete earlier attempt to {dest}")


def claim(state_dir: Path, name: str, gpu: str) -> bool:
    d = state_dir / "claims" / name
    try:
        d.mkdir(parents=True)
    except FileExistsError:
        return False
    (d / "owner.json").write_text(json.dumps({"gpu": gpu, "utc": now()}), encoding="utf-8")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--models-dir", required=True)
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--export-dir", required=True)
    ap.add_argument("--phases", nargs="+", default=["hwcheck", "F5", "R_F5"])
    ap.add_argument("--deadline-epoch", type=float, default=float("inf"),
                    help="do not START a new run after this unix time")
    ap.add_argument("--repo-commit", default=None)
    args = ap.parse_args(argv)

    gpu = os.environ.get("CUDA_VISIBLE_DEVICES")
    if gpu is None or "," in gpu:
        print("CUDA_VISIBLE_DEVICES must name exactly one GPU for a worker", file=sys.stderr)
        return 2
    repo, models_dir = Path(args.repo), Path(args.models_dir)
    state_dir, export_dir = Path(args.state_dir), Path(args.export_dir)
    log = Log(state_dir / f"worker_gpu{gpu}.log", f"gpu{gpu}")
    progress = export_dir / f"progress_gpu{gpu}.jsonl"
    export_dir.mkdir(parents=True, exist_ok=True)

    bundles = plan.build_bundles(tuple(args.phases))
    log(f"worker start; {len(bundles)} bundles, phases={args.phases}")
    n_ok = n_fail = 0
    for b in bundles:
        todo = [(p, s) for (p, s) in b.jobs if not is_done(repo, p, b.model_key, s)]
        if not todo:
            log(f"[{b.name}] all {len(b.jobs)} runs already complete, skipping")
            continue
        if time.time() > args.deadline_epoch:
            log("deadline passed; not starting new bundles")
            break
        if not claim(state_dir, b.name, gpu):
            continue
        log(f"[{b.name}] claimed; {len(todo)} runs to do")
        try:
            records = [download_and_verify(f, models_dir, log) for f in b.files]
        except Exception as exc:  # noqa: BLE001
            log(f"[{b.name}] MODEL UNAVAILABLE, skipping bundle: {exc}")
            n_fail += len(todo)
            continue
        sources = {"quant": b.quant, "files": records, "repo_commit": args.repo_commit}
        src_json = state_dir / f"sources__{b.name}.json"
        src_json.write_text(json.dumps(sources, indent=2, sort_keys=True), encoding="utf-8")
        gguf = str(models_dir / b.files[0].filename)

        for protocol, suite in todo:
            if time.time() > args.deadline_epoch:
                log(f"[{b.name}] deadline passed; stopping before {protocol}/{suite}")
                break
            quarantine_partial(repo, protocol, b.model_key, suite, log)
            t0 = time.perf_counter()
            log(f"[{protocol}/{b.model_key}/{suite}] launching")
            proc = subprocess.run(
                [sys.executable, str(HERE / "kaggle_run_one.py"), "--repo", str(repo), "--protocol", protocol,
                 "--model", b.model_key, "--suite", suite, "--gguf", gguf, "--sources-json", str(src_json)],
                cwd=str(repo), env=dict(os.environ),
            )
            elapsed = time.perf_counter() - t0
            if proc.returncode == 0 and is_done(repo, protocol, b.model_key, suite):
                z = make_run_zip(repo, protocol, b.model_key, suite, export_dir)
                n_ok += 1
                log(f"[{protocol}/{b.model_key}/{suite}] OK in {elapsed:.0f}s -> {z.name}")
                with open(progress, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"utc": now(), "protocol": protocol, "model": b.model_key, "suite": suite,
                                         "gpu": gpu, "elapsed_seconds": elapsed, "zip": z.name}) + "\n")
            else:
                n_fail += 1
                log(f"[{protocol}/{b.model_key}/{suite}] FAILED (exit {proc.returncode}); will be retried on next launch")
        for f in b.files:  # free disk for the next bundle
            (models_dir / f.filename).unlink(missing_ok=True)
    log(f"worker done: {n_ok} runs ok, {n_fail} failed/skipped this session")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
