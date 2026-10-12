"""Run ONE (result-protocol, model, suite) on the current Kaggle GPU, in its
own process (same crash/VRAM isolation as scripts/real_run_one.py on the
laptop).

The experiment config comes from the laptop's own, unmodified
``scripts.real_run_one.build_config`` (protocol "D" for KAGGLE_HWCHECK and
F5, "R" for R_F5), so seed, trial temperatures/seeds, prompt format,
constrained decoding, max_tokens, n_ctx, perturbations and task files are
the laptop's by construction. Only four things differ, all recorded:

  * model.path          (Kaggle location of the GGUF)
  * experiment          (names the run F5 / R_F5 / KAGGLE_HWCHECK)
  * output_dir          (results_v2/<protocol>/<model>/<suite>)
  * model.quant_level   ("Q8_0" for F5/R_F5, exactly like R_PC_Q2K's "Q2_K")

After upgradecanary.runner.run() finishes, run_manifest.json gets two extra
top-level keys (nothing is removed or changed): ``hardware`` and ``kaggle``.

Usage (called by kaggle_worker.py, CUDA_VISIBLE_DEVICES already set):
  python kaggle/kaggle_run_one.py --repo REPO --protocol F5 --model llama31 \
      --suite synthetic --gguf /kaggle/temp/models/x.gguf --sources-json s.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kaggle_plan as plan  # noqa: E402


def _cmd(args: list[str]) -> str | None:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=30).stdout.strip() or None
    except Exception:
        return None


def hardware_info() -> dict:
    """What GPU/CPU/driver this run actually executed on."""
    cvd = os.environ.get("CUDA_VISIBLE_DEVICES")
    gpu: dict = {}
    out = _cmd(["nvidia-smi", "--query-gpu=index,name,uuid,memory.total,driver_version,compute_cap,pci.bus_id",
                "--format=csv,noheader"])
    if out:
        rows = [[c.strip() for c in line.split(",")] for line in out.splitlines()]
        want = (cvd or "0").split(",")[0].strip()
        pick = next((r for r in rows if r[0] == want), rows[0])
        keys = ["physical_index", "name", "uuid", "memory_total", "driver_version", "compute_cap", "pci_bus_id"]
        gpu = dict(zip(keys, pick))
    header = _cmd(["nvidia-smi"]) or ""
    cuda_driver = None
    for tok in header.split("\n"):
        if "CUDA Version:" in tok:
            cuda_driver = tok.split("CUDA Version:")[1].split()[0]
            break
    cpu_model = None
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    except Exception:
        pass
    nvcc = _cmd(["nvcc", "--version"])
    return {
        "platform_class": "kaggle",
        "gpu": gpu,
        "gpu_count_visible_to_process": len((cvd or "").split(",")) if cvd else None,
        "cuda_visible_devices": cvd,
        "cuda_driver_api_version": cuda_driver,
        "nvcc": nvcc.splitlines()[-1] if nvcc else None,
        "cpu": cpu_model or platform.processor(),
        "cpu_count": os.cpu_count(),
        "kernel": platform.platform(),
        "kaggle_kernel_run_type": os.environ.get("KAGGLE_KERNEL_RUN_TYPE"),
        "kaggle_docker_image": os.environ.get("KAGGLE_DOCKER_IMAGE") or os.environ.get("KAGGLE_IMAGE_VERSION"),
    }


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def build_run_config(repo: Path, protocol: str, model_key: str, suite: str, gguf: str) -> dict:
    sys.path.insert(0, str(repo))
    from scripts.real_run_one import build_config  # the laptop's own builder, unmodified
    from scripts.real_run_models import SUITES as LAPTOP_SUITES

    spec = plan.PROTOCOLS[protocol]
    cfg = build_config(model_key, gguf, suite, LAPTOP_SUITES[suite], protocol=spec["base"],
                       output_dir=plan.run_rel_dir(protocol, model_key, suite))
    cfg["experiment"] = plan.experiment_name(protocol, model_key, suite)
    if spec["quant"]:
        cfg["model"]["quant_level"] = spec["quant"]
    # Guard rails: these must be the project-wide values, whatever build_config did.
    assert cfg["seed"] == plan.SEED and cfg["model"]["seed"] == plan.SEED, cfg["seed"]
    assert cfg["trial_seeds"] == [plan.SEED, plan.SEED + 1, plan.SEED + 2], cfg["trial_seeds"]
    assert cfg["trial_temperatures"] == [0.0, 0.7, 0.7], cfg["trial_temperatures"]
    assert cfg["model"]["n_ctx"] == 4096 and cfg["model"]["n_gpu_layers"] == -1
    return cfg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--protocol", required=True, choices=sorted(plan.PROTOCOLS))
    ap.add_argument("--model", required=True)
    ap.add_argument("--suite", required=True, choices=list(plan.SUITES))
    ap.add_argument("--gguf", required=True, help="absolute path to the (first part of the) GGUF")
    ap.add_argument("--sources-json", required=True, help="JSON written by the worker: model source records")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    os.chdir(repo)  # runner.run() resolves output_dir and data paths relative to cwd
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "analysis" / "audit"))
    import _dll_preload  # noqa: E402  (no-op on Linux; kept so code path == laptop's)

    _dll_preload.preload()
    import yaml  # noqa: E402

    tag = f"{args.protocol}/{args.model}/{args.suite}"
    out_rel = plan.run_rel_dir(args.protocol, args.model, args.suite)
    status_dir = repo / out_rel
    status_dir.mkdir(parents=True, exist_ok=True)
    status_path = status_dir / "_status.json"
    hw = hardware_info()

    cfg = build_run_config(repo, args.protocol, args.model, args.suite, args.gguf)
    gen_dir = repo / "results_v2" / "_generated_configs"
    gen_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = gen_dir / f"{args.protocol}__{args.model}__{args.suite}.yaml"
    with open(cfg_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False)

    print(f"[{tag}] config -> {cfg_path}; gpu={hw.get('gpu', {}).get('name')} "
          f"(CUDA_VISIBLE_DEVICES={hw.get('cuda_visible_devices')})", flush=True)
    t0 = time.perf_counter()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        from upgradecanary.runner import run

        summary = run(str(cfg_path))
    except Exception as exc:
        _write_json(status_path, {
            "model_key": args.model, "suite": args.suite, "protocol": args.protocol, "completed": False,
            "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(), "hardware": hw,
        })
        print(f"[{tag}] FAILED: {exc}", flush=True)
        return 1
    elapsed = time.perf_counter() - t0

    run_id = summary.get("run_id")
    run_dir = repo / cfg["output_dir"] / run_id if run_id else None
    num_records = summary.get("num_records")
    ok = num_records == plan.EXPECTED_RECORDS_PER_RUN

    # Add (never replace) the two new manifest keys.
    if run_dir and (run_dir / "run_manifest.json").exists():
        mpath = run_dir / "run_manifest.json"
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        sources = json.loads(Path(args.sources_json).read_text(encoding="utf-8"))
        manifest["hardware"] = hw
        manifest["kaggle"] = {
            "result_protocol": args.protocol,
            "config_builder_protocol": plan.PROTOCOLS[args.protocol]["base"],
            "model_key": args.model,
            "quant": sources.get("quant"),
            "model_files": sources.get("files"),
            "task_file": {
                "path": cfg["data"],
                "sha256_lf_normalized": plan.lf_normalized_sha256(repo / cfg["data"]),
            },
            "repo_commit": sources.get("repo_commit"),
            "started_utc": started,
            "elapsed_seconds": elapsed,
            "python": platform.python_version(),
        }
        _write_json(mpath, manifest)

    _write_json(status_path, {
        "model_key": args.model, "suite": args.suite, "protocol": args.protocol,
        "completed": bool(ok), "run_id": run_id, "run_dir": str(run_dir) if run_dir else None,
        "num_records": num_records, "expected_records": plan.EXPECTED_RECORDS_PER_RUN,
        "record_count_ok": ok, "elapsed_seconds": elapsed, "hardware": hw,
    })
    if ok:
        print(f"[{tag}] done: {num_records} records in {elapsed:.0f}s", flush=True)
        return 0
    print(f"[{tag}] RECORD COUNT MISMATCH: got {num_records}, expected {plan.EXPECTED_RECORDS_PER_RUN}", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
