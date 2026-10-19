"""One Phase 2 worker per GPU. The worker on GPU ``g`` runs lane ``g`` of the chosen batch of W1_kaggle.json:
for each bundle (one model file) it downloads and verifies the GGUF, runs that bundle's runs one after another
(each in its own process, p2_run_one.py), zips every finished run, and deletes the model.

Resumable: a run whose results_v3/<folder>/<model>/<suite>/_status.json says completed with the right record
count is skipped; an interrupted attempt is moved to results_v3/_failed_attempts/ before the run is redone.
No new run is started after --deadline-epoch, nor one that is expected to end after --hard-limit-epoch.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import kaggle_worker as kw  # noqa: E402  (Log, download_and_verify, remove_model_files: shared with Phase 1)
from p2_sources import files_for  # noqa: E402

MANIFEST = "W1_kaggle"


def load_manifest(repo: Path, name: str = MANIFEST) -> dict:
    return json.loads((repo / "configs" / "phase2" / f"{name}.json").read_text(encoding="utf-8"))


def is_done(repo: Path, entry: dict) -> bool:
    try:
        s = json.loads((repo / entry["output_dir"] / "_status.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(s.get("completed") and s.get("record_count_ok") and s.get("expected_records") == entry["expected_records"])


def quarantine_partial(repo: Path, entry: dict, log) -> None:
    d = repo / entry["output_dir"]
    if d.exists() and any(d.iterdir()) and not is_done(repo, entry):
        dest = repo / "results_v3" / "_failed_attempts" / f"{entry['folder']}__{entry['model']}__{entry['suite']}__{int(time.time())}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(d), str(dest))
        log(f"moved incomplete earlier attempt to {dest}")


def zip_name(entry: dict) -> str:
    return f"p2__{entry['folder']}__{entry['model']}__{entry['suite']}.zip"


def make_run_zip(repo: Path, entry: dict, export_dir: Path) -> Path:
    """results_v3/<folder>/<model>/<suite>/** + its generated config, so 'unzip at the repo root' gives the layout."""
    export_dir.mkdir(parents=True, exist_ok=True)
    src = repo / entry["output_dir"]
    tmp = export_dir / f".tmp__{zip_name(entry)}"
    final = export_dir / zip_name(entry)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(repo).as_posix())
        cfg = repo / "results_v3" / "_generated_configs" / f"{entry['folder']}__{entry['model']}__{entry['suite']}.yaml"
        if cfg.exists():
            zf.write(cfg, cfg.relative_to(repo).as_posix())
    tmp.replace(final)
    return final


def pick_lane(batch: dict, gpu: int) -> dict | None:
    return batch["lanes"][gpu] if gpu < len(batch["lanes"]) else None


def run_lane(repo: Path, models_dir: Path, state_dir: Path, export_dir: Path, batch_id: str, gpu: str,
             deadline: float = float("inf"), hard_limit: float = float("inf"), commit: str | None = None,
             downloader: Callable = kw.download_and_verify,
             runner: Callable[[list[str]], int] | None = None, clock: Callable[[], float] = time.time) -> dict:
    log = kw.Log(state_dir / f"p2_worker_gpu{gpu}.log", f"gpu{gpu}")
    manifest = load_manifest(repo)
    by_id = {e["id"]: e for e in manifest["runs"]}
    batch = next(b for b in manifest["batches"] if b["id"] == batch_id)
    lane = pick_lane(batch, int(gpu))
    result = {"batch": batch_id, "gpu": gpu, "ok": [], "failed": [], "skipped_done": [], "skipped_time": []}
    if lane is None:
        log(f"batch {batch_id} has no lane for GPU {gpu}")
        return result
    if runner is None:
        def runner(cmd: list[str]) -> int:
            return subprocess.run(cmd, cwd=str(repo), env=dict(os.environ)).returncode
    progress = export_dir / f"progress_gpu{gpu}.jsonl"
    export_dir.mkdir(parents=True, exist_ok=True)
    for bundle in lane["bundles"]:
        todo = [by_id[r] for r in bundle["runs"] if not is_done(repo, by_id[r])]
        result["skipped_done"] += [r for r in bundle["runs"] if r not in {e["id"] for e in todo}]
        if not todo:
            log(f"[{bundle['model']}/{bundle['quant']}] all runs already complete")
            continue
        files = files_for(bundle["model"], bundle["quant"])
        try:
            try:
                records = [downloader(f, models_dir, log) for f in files]
            except Exception as exc:  # noqa: BLE001
                log(f"[{bundle['model']}/{bundle['quant']}] MODEL UNAVAILABLE, skipping bundle: {exc}")
                result["failed"] += [e["id"] for e in todo]
                continue
            sources = {"quant": bundle["quant"], "files": records, "repo_commit": commit}
            src_json = state_dir / f"sources__{bundle['model']}__{bundle['quant']}.json"
            src_json.write_text(json.dumps(sources, indent=2, sort_keys=True), encoding="utf-8")
            gguf = str(models_dir / files[0].filename)
            for e in todo:
                if clock() > deadline or clock() + 1.25 * e["estimated_hours"] * 3600 > hard_limit:
                    log(f"[{e['id']}] time budget reached; not started")
                    result["skipped_time"].append(e["id"])
                    continue
                quarantine_partial(repo, e, log)
                t0 = clock()
                log(f"[{e['id']}] launching (~{e['estimated_hours']:.2f} h)")
                rc = runner([sys.executable, str(HERE / "p2_run_one.py"), "--repo", str(repo), "--run-id", e["id"],
                             "--gguf", gguf, "--sources-json", str(src_json)])
                if rc == 0 and is_done(repo, e):
                    z = make_run_zip(repo, e, export_dir)
                    result["ok"].append(e["id"])
                    log(f"[{e['id']}] OK in {(clock() - t0) / 3600:.2f} h -> {z.name}")
                    with open(progress, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"id": e["id"], "gpu": gpu, "elapsed_seconds": clock() - t0, "zip": z.name,
                                             "estimated_hours": e["estimated_hours"]}) + "\n")
                else:
                    result["failed"].append(e["id"])
                    log(f"[{e['id']}] FAILED (exit {rc}); will be redone on the next launch")
        finally:
            kw.remove_model_files(models_dir, files)
    log(f"lane done: {len(result['ok'])} ok, {len(result['failed'])} failed, {len(result['skipped_time'])} not started (time)")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--models-dir", required=True)
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--export-dir", required=True)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--deadline-epoch", type=float, default=float("inf"))
    ap.add_argument("--hard-limit-epoch", type=float, default=float("inf"))
    ap.add_argument("--repo-commit", default=None)
    args = ap.parse_args(argv)
    gpu = os.environ.get("CUDA_VISIBLE_DEVICES")
    if gpu is None or "," in gpu:
        print("CUDA_VISIBLE_DEVICES must name exactly one GPU for a worker", file=sys.stderr)
        return 2
    models_dir = Path(args.models_dir)
    if "/kaggle/working" in models_dir.resolve().as_posix():
        print(f"refusing: --models-dir {models_dir} is inside /kaggle/working", file=sys.stderr)
        return 2
    res = run_lane(Path(args.repo), models_dir, Path(args.state_dir), Path(args.export_dir), args.batch, gpu,
                   args.deadline_epoch, args.hard_limit_epoch, args.repo_commit)
    return 0 if not res["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
