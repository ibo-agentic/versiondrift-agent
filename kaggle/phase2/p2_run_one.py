"""Run ONE Phase 2 Kaggle run (a W1_kaggle manifest entry) on the current GPU, in its own process.

The config is scripts.phase2.build.build_run_config (the laptop's build_config + trial keys only), with the
downloaded GGUF as model.path. After the run, run_manifest.json gets three extra top-level keys (nothing is
removed): ``hardware``, ``kaggle`` and ``phase2``.

  python kaggle/phase2/p2_run_one.py --repo REPO --run-id F5/llama31/synthetic --gguf PATH --sources-json S.json
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import kaggle_run_one as k1  # noqa: E402  (hardware_info, package versions: shared with Phase 1)
import kaggle_plan as plan  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--manifest", default="W1_kaggle")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--sources-json", required=True)
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    import os
    os.chdir(repo)
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "analysis" / "audit"))
    import _dll_preload  # noqa: E402

    _dll_preload.preload()
    from scripts.phase2.build import build_run_config, write_config
    from scripts.phase2.plan import load_manifest

    entry = next(e for e in load_manifest(args.manifest, repo / "configs" / "phase2")["runs"] if e["id"] == args.run_id)
    tag = entry["id"]
    out_dir = repo / entry["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    status_path = out_dir / "_status.json"
    hw = k1.hardware_info()
    cfg = build_run_config(entry, gguf=args.gguf)
    cfg_path = write_config(cfg, repo / "results_v3" / "_generated_configs" /
                            f"{entry['folder']}__{entry['model']}__{entry['suite']}.yaml")
    print(f"[{tag}] config -> {cfg_path}; gpu={hw.get('gpu', {}).get('name')} "
          f"(CUDA_VISIBLE_DEVICES={hw.get('cuda_visible_devices')})", flush=True)
    t0 = time.perf_counter()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        from upgradecanary.runner import run

        summary = run(str(cfg_path))
    except Exception as exc:  # noqa: BLE001
        status_path.write_text(json.dumps({"id": tag, "completed": False, "error": f"{type(exc).__name__}: {exc}",
                                           "traceback": traceback.format_exc(), "hardware": hw}, indent=2, sort_keys=True),
                               encoding="utf-8")
        print(f"[{tag}] FAILED: {exc}", flush=True)
        return 1
    elapsed = time.perf_counter() - t0
    run_id = summary.get("run_id")
    run_dir = repo / cfg["output_dir"] / run_id if run_id else None
    n = summary.get("num_records")
    ok = n == entry["expected_records"]
    if run_dir and (run_dir / "run_manifest.json").exists():
        mp = run_dir / "run_manifest.json"
        m = json.loads(mp.read_text(encoding="utf-8"))
        sources = json.loads(Path(args.sources_json).read_text(encoding="utf-8"))
        m["hardware"] = hw
        m["kaggle"] = {"result_protocol": entry["folder"], "config_builder_protocol": entry["config_protocol"],
                       "model_key": entry["model"], "quant": sources.get("quant"), "model_files": sources.get("files"),
                       "task_file": {"path": cfg["data"],
                                     "sha256_lf_normalized": plan.lf_normalized_sha256(repo / cfg["data"])},
                       "repo_commit": sources.get("repo_commit"), "started_utc": started, "elapsed_seconds": elapsed,
                       "python": platform.python_version(), "package_versions": k1._package_versions()}
        m["phase2"] = {"manifest": args.manifest, "id": tag, "plan": "PLAN_PHASE2.md v4",
                       "trial_first_index": entry["trial_first_index"], "reuse": entry["reuse"],
                       "estimated_hours": entry["estimated_hours"]}
        mp.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")
    status_path.write_text(json.dumps({"id": tag, "model_key": entry["model"], "suite": entry["suite"],
                                       "protocol": entry["folder"], "completed": bool(ok), "run_id": run_id,
                                       "run_dir": str(run_dir) if run_dir else None, "num_records": n,
                                       "expected_records": entry["expected_records"], "record_count_ok": ok,
                                       "elapsed_seconds": elapsed, "hardware": hw}, indent=2, sort_keys=True),
                           encoding="utf-8")
    print(f"[{tag}] {'done' if ok else 'RECORD COUNT MISMATCH'}: {n} records (expected {entry['expected_records']}) "
          f"in {elapsed:.0f}s", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
