"""Run ONE (model, suite) full D-protocol real run (PLAN v1, 2026-10-05),
in its own process -- same crash/VRAM isolation rationale as
scripts/smoke_one_model.py. Writes to results_v2/D/<model_key>/<suite>/
(via the real, unmodified upgradecanary.runner.run()), verifies the
record count, and writes a small status JSON the orchestrator reads for
resumability and the final report.

Usage: python scripts/real_run_one.py <model_key> <suite>
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

import yaml  # noqa: E402

from scripts.real_run_models import EXPECTED_RECORDS_PER_RUN, MODEL_ORDER, SUITES  # noqa: E402

STATUS_ROOT = REPO_ROOT / "results_v2" / "D"
GENERATED_CFG_DIR = REPO_ROOT / "results_v2" / "_generated_configs"


def build_config(model_key: str, gguf_path: str, suite: str, data_path: str) -> dict:
    return {
        "experiment": f"upgradecanary-real-D-{model_key}-{suite}",
        "seed": 1234,
        "data": data_path,
        "output_dir": f"results_v2/D/{model_key}/{suite}",
        "conditions": ["baseline", "schema_drift", "fault_reporting"],
        "trials": 3,
        "trial_temperatures": [0.0, 0.7, 0.7],
        "trial_seeds": [1234, 1235, 1236],
        "prompt_format": "shared",
        "constrained_decoding": "off",
        "model": {
            "provider": "llama_cpp",
            "path": gguf_path,
            "chat_wrapping": "native",
            "n_ctx": 4096,
            "n_gpu_layers": -1,
            "temperature": 0.0,
            "max_tokens": 256,
            "seed": 1234,
        },
        "perturbations": {
            "schema_drift": {
                "enabled": ["field_rename", "field_drop", "type_mutation", "unexpected_field", "enum_drift"]
            },
            # runtime_faults is read unconditionally by runner.run() even
            # though "runtime_fault" is not in conditions above (PLAN.md
            # section 3: the old condition is not rerun under D) -- empty
            # and inert here, just satisfies the required config key.
            "runtime_faults": {"enabled": []},
            "fault_reporting": {"enabled": ["timeout", "tool_exception", "empty_result", "partial_result"]},
        },
        "executor": {"strict_baseline_args": True},
    }


def main(model_key: str, suite: str) -> int:
    gguf_path = dict(MODEL_ORDER)[model_key]
    data_path = SUITES[suite]
    status_dir = STATUS_ROOT / model_key / suite
    status_dir.mkdir(parents=True, exist_ok=True)
    status_path = status_dir / "_status.json"

    GENERATED_CFG_DIR.mkdir(parents=True, exist_ok=True)
    cfg_path = GENERATED_CFG_DIR / f"{model_key}__{suite}.yaml"
    cfg = build_config(model_key, gguf_path, suite, data_path)
    with open(cfg_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False)

    print(f"[{model_key}/{suite}] config written to {cfg_path}", flush=True)
    print(f"[{model_key}/{suite}] starting run...", flush=True)
    t0 = time.perf_counter()
    try:
        from upgradecanary.runner import run

        summary = run(str(cfg_path))
    except Exception as exc:
        status = {
            "model_key": model_key, "suite": suite, "completed": False,
            "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(),
        }
        _write_json(status_path, status)
        print(f"[{model_key}/{suite}] FAILED: {exc}", flush=True)
        return 1
    elapsed = time.perf_counter() - t0

    run_id_ = summary.get("run_id")
    run_dir = REPO_ROOT / "results_v2" / "D" / model_key / suite / run_id_ if run_id_ else None
    num_records = summary.get("num_records")
    record_count_ok = num_records == EXPECTED_RECORDS_PER_RUN

    status = {
        "model_key": model_key,
        "suite": suite,
        "completed": bool(record_count_ok),
        "run_id": run_id_,
        "run_dir": str(run_dir) if run_dir else None,
        "num_records": num_records,
        "expected_records": EXPECTED_RECORDS_PER_RUN,
        "record_count_ok": record_count_ok,
        "elapsed_seconds": elapsed,
    }
    _write_json(status_path, status)
    if record_count_ok:
        print(f"[{model_key}/{suite}] done: {num_records} records in {elapsed:.0f}s -> {run_dir}", flush=True)
        return 0
    print(
        f"[{model_key}/{suite}] RECORD COUNT MISMATCH: got {num_records}, "
        f"expected {EXPECTED_RECORDS_PER_RUN}",
        flush=True,
    )
    return 1


def _write_json(path: Path, data: dict) -> None:
    import json

    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/real_run_one.py <model_key> <suite>")
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
