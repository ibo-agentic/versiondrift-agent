"""Run every applicable PLAN.md 10.2 smoke config for ONE model, in its own
process (so a crash/OOM on one model can never take down the other 15, and
so VRAM is guaranteed fully released when the process exits). Invoked by
scripts/smoke_test.py; not meant to be run standalone, though it works
that way too: `python scripts/smoke_one_model.py <model_key>`.

Writes results_smoke/<model_key>/<config_name>/{raw_outputs,parsed_results}.jsonl
+ config_summary.json (per config), and results_smoke/<model_key>/model_result.json
(the aggregate across that model's configs, including the load step itself).
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "analysis" / "audit"))
import _dll_preload  # noqa: E402

_dll_preload.preload()

from scripts.smoke_lib import VramSampler, run_smoke_config  # noqa: E402
from scripts.smoke_models import MODEL_REGISTRY, configs_for  # noqa: E402

OUT_ROOT = REPO_ROOT / "results_smoke"


def main(model_key: str) -> int:
    entry = MODEL_REGISTRY[model_key]
    model_dir = OUT_ROOT / model_key
    model_dir.mkdir(parents=True, exist_ok=True)
    result: dict = {"model_key": model_key, "path": entry["path"], "configs": {}}

    path = REPO_ROOT / entry["path"]
    if not path.exists():
        result["load_error"] = f"GGUF not found at {path}"
        _write_result(model_dir, result)
        print(f"[{model_key}] SKIP: GGUF not found at {path}", flush=True)
        return 1

    vram = VramSampler()
    vram.start()

    t_load0 = time.perf_counter()
    try:
        from upgradecanary.model.llama_cpp_client import LlamaCppClient

        client = LlamaCppClient({
            "path": str(path),
            "chat_wrapping": "native",
            "n_ctx": 4096,
            "n_gpu_layers": -1,
            "seed": 0,
            "temperature": 0.0,
            "max_tokens": 256,
        })
    except Exception as exc:
        result["load_error"] = f"{type(exc).__name__}: {exc}"
        result["load_error_traceback"] = traceback.format_exc()
        _write_result(model_dir, result)
        print(f"[{model_key}] LOAD FAILED: {exc}", flush=True)
        vram.stop()
        return 1
    result["load_seconds"] = time.perf_counter() - t_load0
    result["native_chat_template_found"] = client.backend_info().get("native_chat_template_found")

    for cfg in configs_for(model_key):
        config_name = cfg["name"]
        vram.reset()
        out_dir = model_dir / config_name
        print(f"[{model_key}] running config {config_name}...", flush=True)
        try:
            summary = run_smoke_config(
                client, model_key, config_name,
                prompt_format=cfg["prompt_format"],
                constrained_decoding=cfg["constrained_decoding"],
                out_dir=out_dir,
            )
            summary["peak_vram_mib"] = vram.peak_mib()
            result["configs"][config_name] = summary
        except Exception as exc:
            result["configs"][config_name] = {
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "peak_vram_mib": vram.peak_mib(),
            }
            print(f"[{model_key}] config {config_name} FAILED: {exc}", flush=True)

    vram.stop()
    _write_result(model_dir, result)
    print(f"[{model_key}] done.", flush=True)
    return 0


def _write_result(model_dir: Path, result: dict) -> None:
    from upgradecanary.utils import write_json

    write_json(model_dir / "model_result.json", result)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in MODEL_REGISTRY:
        print(f"Usage: python scripts/smoke_one_model.py <model_key>\nValid keys: {sorted(MODEL_REGISTRY)}")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
