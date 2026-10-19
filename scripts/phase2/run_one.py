"""Run ONE Phase 2 laptop run from a manifest entry, in its own process (same crash/VRAM isolation as
scripts/real_run_one.py).

    python -m scripts.phase2.run_one W1_laptop D/gemma2_2b/synthetic [--force]

Writes results_v3/<folder>/<model>/<suite>/<run_id>/... and results_v3/<folder>/<model>/<suite>/_status.json
(completed only when the record count is exactly tasks x 3 conditions x trials). An earlier incomplete
attempt is moved to results_v3/_failed_attempts/ first (the analysis loader refuses two run folders per
suite). Exit 0 = done (or already done), 1 = failed.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "analysis" / "audit"))

from scripts.phase2.build import build_run_config, write_config  # noqa: E402
from scripts.phase2.plan import load_manifest  # noqa: E402


def status_path(entry: dict, root: Path = REPO_ROOT) -> Path:
    return root / entry["output_dir"] / "_status.json"


def is_done(entry: dict, root: Path = REPO_ROOT) -> bool:
    try:
        s = json.loads(status_path(entry, root).read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(s.get("completed") and s.get("record_count_ok") and s.get("expected_records") == entry["expected_records"])


def quarantine_incomplete(entry: dict, root: Path = REPO_ROOT) -> Path | None:
    d = root / entry["output_dir"]
    if d.exists() and any(d.iterdir()) and not is_done(entry, root):
        dest = root / "results_v3" / "_failed_attempts" / f"{entry['folder']}__{entry['model']}__{entry['suite']}__{int(time.time())}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(d), str(dest))
        return dest
    return None


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def run_entry(manifest_name: str, entry: dict, root: Path = REPO_ROOT, force: bool = False) -> int:
    tag = entry["id"]
    if is_done(entry, root) and not force:
        print(f"[{tag}] already complete, skipping", flush=True)
        return 0
    if entry["data_status"] != "ok":
        print(f"[{tag}] task file {entry['data']} is not available yet (data_status={entry['data_status']})", flush=True)
        return 1
    if not (root / entry["data"]).exists():
        print(f"[{tag}] task file {entry['data']} does not exist", flush=True)
        return 1
    moved = quarantine_incomplete(entry, root)
    if moved:
        print(f"[{tag}] moved incomplete earlier attempt to {moved}", flush=True)
    import os
    os.chdir(root)                                              # runner resolves data/output paths against cwd
    import _dll_preload  # noqa: E402

    _dll_preload.preload()
    cfg = build_run_config(entry)
    cfg_path = write_config(cfg, root / "results_v3" / "_generated_configs" /
                            f"{entry['folder']}__{entry['model']}__{entry['suite']}.yaml")
    sp = status_path(entry, root)
    print(f"[{tag}] config -> {cfg_path}; trials {entry['trial_seeds']} temps {entry['temperatures']}", flush=True)
    t0 = time.perf_counter()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        from upgradecanary.runner import run

        summary = run(str(cfg_path))
    except Exception as exc:  # noqa: BLE001
        _write_json(sp, {"id": tag, "completed": False, "error": f"{type(exc).__name__}: {exc}",
                         "traceback": traceback.format_exc()})
        print(f"[{tag}] FAILED: {exc}", flush=True)
        return 1
    elapsed = time.perf_counter() - t0
    run_id = summary.get("run_id")
    run_dir = root / cfg["output_dir"] / run_id if run_id else None
    n = summary.get("num_records")
    ok = n == entry["expected_records"]
    if run_dir and (run_dir / "run_manifest.json").exists():          # add (never replace) one key
        mp = run_dir / "run_manifest.json"
        m = json.loads(mp.read_text(encoding="utf-8"))
        m["phase2"] = {"manifest": manifest_name, "id": tag, "plan": "PLAN_PHASE2.md v4",
                       "trial_first_index": entry["trial_first_index"], "reuse": entry["reuse"],
                       "estimated_hours": entry["estimated_hours"], "started_utc": started}
        _write_json(mp, m)
    _write_json(sp, {"id": tag, "model_key": entry["model"], "suite": entry["suite"], "protocol": entry["folder"],
                     "completed": bool(ok), "run_id": run_id, "run_dir": str(run_dir) if run_dir else None,
                     "num_records": n, "expected_records": entry["expected_records"], "record_count_ok": ok,
                     "elapsed_seconds": elapsed})
    print(f"[{tag}] {'done' if ok else 'RECORD COUNT MISMATCH'}: {n} records (expected {entry['expected_records']}) "
          f"in {elapsed:.0f}s", flush=True)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest")
    ap.add_argument("run_id")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    m = load_manifest(args.manifest)
    entry = next((e for e in m["runs"] if e["id"] == args.run_id), None)
    if entry is None:
        print(f"no run {args.run_id!r} in manifest {args.manifest}", file=sys.stderr)
        return 2
    if entry["hardware"] != "laptop":
        print(f"{args.run_id} is a {entry['hardware']} run; use the Kaggle notebook", file=sys.stderr)
        return 2
    return run_entry(args.manifest, entry, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
