"""Run ONE (model, suite) full real run for a given protocol (PLAN v1 =
"D"; F2 = "Qwen3 thinking off", 2026-10-05), in its own process -- same
crash/VRAM isolation rationale as scripts/smoke_one_model.py. Writes to
results_v2/<protocol>/<model_key>/<suite>/ (via the real, unmodified
upgradecanary.runner.run()), verifies the record count, and writes a
small status JSON the orchestrator reads for resumability and the final
report.

Usage: python scripts/real_run_one.py <model_key> <suite> [protocol] [task_limit]
  protocol defaults to "D" (unchanged from the original D-protocol runs).
  task_limit is optional, for the F2 5-task-per-suite verification pass
  only -- when set, output goes to a throwaway scratch dir, never into
  results_v2/<protocol>/, so a quick test can never pollute real data.
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

# protocol -> model.thinking override. "default" == D's own behavior
# (Qwen3 thinking on by its own default; a no-op for every other model).
PROTOCOL_THINKING = {
    "D": "default",
    "F2": "off",
    "F1": "default",
}
# protocol -> max_tokens override. D's only output-budget factor is F1.
PROTOCOL_MAX_TOKENS = {
    "D": 256,
    "F2": 256,
    "F1": 1024,
}


def build_config(
    model_key: str, gguf_path: str, suite: str, data_path: str,
    protocol: str = "D", output_dir: str | None = None,
) -> dict:
    thinking = PROTOCOL_THINKING[protocol]
    max_tokens = PROTOCOL_MAX_TOKENS[protocol]
    if output_dir is None:
        output_dir = f"results_v2/{protocol}/{model_key}/{suite}"
    return {
        "experiment": f"upgradecanary-real-{protocol}-{model_key}-{suite}",
        "seed": 1234,
        "data": data_path,
        "output_dir": output_dir,
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
            "max_tokens": max_tokens,
            "seed": 1234,
            # Explicit on every protocol (including D) so this key's
            # presence/absence is never itself a point of difference
            # between protocols -- "default" here is byte-identical to
            # omitting the key (LlamaCppClient's own default), so D's
            # runs are unaffected by making this explicit.
            "thinking": thinking,
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


def main(model_key: str, suite: str, protocol: str = "D", task_limit: int | None = None) -> int:
    gguf_path = dict(MODEL_ORDER)[model_key]
    data_path = SUITES[suite]
    is_quick_test = task_limit is not None

    if is_quick_test:
        status_dir = REPO_ROOT / "results_v2" / "_quick_test" / protocol / model_key / suite
        output_dir = f"results_v2/_quick_test/{protocol}/{model_key}/{suite}"
        expected_records = task_limit * 3 * 3
    else:
        status_dir = REPO_ROOT / "results_v2" / protocol / model_key / suite
        output_dir = None  # build_config derives the real protocol output dir
        expected_records = EXPECTED_RECORDS_PER_RUN
    status_dir.mkdir(parents=True, exist_ok=True)
    status_path = status_dir / "_status.json"

    gen_cfg_dir = REPO_ROOT / "results_v2" / "_generated_configs"
    gen_cfg_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_quicktest" if is_quick_test else ""
    cfg_path = gen_cfg_dir / f"{protocol}__{model_key}__{suite}{suffix}.yaml"
    cfg = build_config(model_key, gguf_path, suite, data_path, protocol=protocol, output_dir=output_dir)
    if is_quick_test:
        cfg["task_limit"] = task_limit

    with open(cfg_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False)

    tag = f"{protocol}/{model_key}/{suite}" + (" (quick test)" if is_quick_test else "")
    print(f"[{tag}] config written to {cfg_path}", flush=True)
    print(f"[{tag}] starting run...", flush=True)
    t0 = time.perf_counter()
    try:
        from upgradecanary.runner import run

        summary = run(str(cfg_path))
    except Exception as exc:
        status = {
            "model_key": model_key, "suite": suite, "protocol": protocol, "completed": False,
            "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(),
        }
        _write_json(status_path, status)
        print(f"[{tag}] FAILED: {exc}", flush=True)
        return 1
    elapsed = time.perf_counter() - t0

    run_id_ = summary.get("run_id")
    run_dir = Path(cfg["output_dir"]) / run_id_ if run_id_ else None
    num_records = summary.get("num_records")
    record_count_ok = num_records == expected_records

    status = {
        "model_key": model_key,
        "suite": suite,
        "protocol": protocol,
        "completed": bool(record_count_ok),
        "run_id": run_id_,
        "run_dir": str(REPO_ROOT / run_dir) if run_dir else None,
        "num_records": num_records,
        "expected_records": expected_records,
        "record_count_ok": record_count_ok,
        "elapsed_seconds": elapsed,
    }
    _write_json(status_path, status)
    if record_count_ok:
        print(f"[{tag}] done: {num_records} records in {elapsed:.0f}s -> {run_dir}", flush=True)
        return 0
    print(f"[{tag}] RECORD COUNT MISMATCH: got {num_records}, expected {expected_records}", flush=True)
    return 1


def _write_json(path: Path, data: dict) -> None:
    import json

    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/real_run_one.py <model_key> <suite> [protocol] [task_limit]")
        sys.exit(2)
    model_key_arg = sys.argv[1]
    suite_arg = sys.argv[2]
    protocol_arg = sys.argv[3] if len(sys.argv) > 3 else "D"
    task_limit_arg = int(sys.argv[4]) if len(sys.argv) > 4 else None
    sys.exit(main(model_key_arg, suite_arg, protocol_arg, task_limit_arg))
