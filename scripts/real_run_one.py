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
    "F3": "default",
    # F3_rerun: granite30 only, after the 2026-10-07 parser fix (Granite-
    # 3.0's "function"-as-string-alias) -- identical config to F3 in
    # every way, written to a separate folder so the original F3 data
    # is kept untouched. See DEVIATIONS.md.
    "F3_rerun": "default",
    # F6 (sampling preset): thinking stays "default" (on) for Qwen3, same
    # as D -- only the sampling preset changes under this protocol.
    "F6": "default",
    # F4_json (generic-JSON constrained decoding): thinking config itself
    # stays "default" (unchanged from D) -- Qwen3's thinking is blocked as
    # a structural SIDE EFFECT of the grammar (the config never turns it
    # off), labeled and reported separately. See DEVIATIONS.md.
    "F4_json": "default",
    # R (PLAN.md section 7): same as F4_json's thinking note -- config
    # stays "default", Qwen3's thinking is blocked as a side effect of the
    # same generic_json grammar, labeled [grammar + thinking blocked].
    "R": "default",
}
# protocol -> max_tokens override. D's only output-budget factor is F1.
PROTOCOL_MAX_TOKENS = {
    "D": 256,
    "F2": 256,
    "F1": 1024,
    "F3": 256,
    "F3_rerun": 256,
    "F6": 256,
    "F4_json": 256,
    # R (PLAN.md section 7, item 1): output budget 1024.
    "R": 1024,
}
# protocol -> prompt_format override. F3 is the only one that changes
# the tool-format mechanism (native chat template + tools= instead of
# the shared JSON-in-prompt schema dump).
PROTOCOL_PROMPT_FORMAT = {
    "D": "shared",
    "F2": "shared",
    "F1": "shared",
    "F3": "native",
    "F3_rerun": "native",
    "F6": "shared",
    "F4_json": "shared",
    "R": "shared",
}
# protocol -> constrained_decoding override. F4's "generic_json" level is
# the only one run (PLAN.md's "full_schema" level is deliberately cut --
# see DEVIATIONS.md, 2026-10-08).
PROTOCOL_CONSTRAINED_DECODING = {
    "D": "off",
    "F2": "off",
    "F1": "off",
    "F3": "off",
    "F3_rerun": "off",
    "F6": "off",
    "F4_json": "generic_json",
    # R (PLAN.md section 7, item 2): generic-JSON constrained decoding --
    # same grammar/mechanism as F4_json, including Qwen3's thinking-block
    # side effect. See DEVIATIONS.md, 2026-10-08.
    "R": "generic_json",
}

# D's own shared sampling defaults (upgradecanary/model/llama_cpp_client.py's
# library defaults) -- F6's greedy trial (index 0) is always pinned to
# these explicitly, never to a model's recommended preset, so repeat_penalty
# (not gated by temperature=0 in llama.cpp's sampling pipeline, unlike
# top_p/top_k/min_p) can never make greedy diverge from D. See DEVIATIONS.md.
_D_SAMPLING_DEFAULTS = {"top_p": 0.95, "top_k": 40, "min_p": 0.05, "repeat_penalty": 1.0}
_D_SAMPLED_TRIAL_TEMPERATURE = 0.7

# 2026-10-07, PLAN.md F6 (sampling preset): per-model recommended sampling
# values for the 2 SAMPLED trials only (trial 0/greedy always uses
# _D_SAMPLING_DEFAULTS + temperature=0.0, both here and in D). Source:
# docs/sampling_presets.md (fetched live 2026-10-04 from each model's own
# generation_config.json and/or model card -- see that file for exact
# citations). A model not listed here has no official recommendation, per
# that file, and uses _D_SAMPLING_DEFAULTS/_D_SAMPLED_TRIAL_TEMPERATURE
# unchanged -- "keep the D value" per explicit instruction.
F6_RECOMMENDED_SAMPLING: dict[str, dict] = {
    "qwen2": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.05, "repeat_penalty": 1.05},
    "qwen25": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.05, "repeat_penalty": 1.05},
    # Thinking stays "default" (on) under F6, same as D -- uses Qwen3's own
    # thinking-mode recommended values, not the non-thinking-mode ones.
    "qwen3": {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "repeat_penalty": 1.0},
    "llama3": {"temperature": 0.6, "top_p": 0.9, "top_k": 40, "min_p": 0.05, "repeat_penalty": 1.0},
    "llama31": {"temperature": 0.6, "top_p": 0.9, "top_k": 40, "min_p": 0.05, "repeat_penalty": 1.0},
    # temperature has no stated recommendation for this model (see
    # docs/sampling_presets.md's caveat) -- keeps D's sampled-trial value.
    "gemma3_4b": {"temperature": 0.7, "top_p": 0.95, "top_k": 64, "min_p": 0.05, "repeat_penalty": 1.0},
}


def build_config(
    model_key: str, gguf_path: str, suite: str, data_path: str,
    protocol: str = "D", output_dir: str | None = None,
) -> dict:
    thinking = PROTOCOL_THINKING[protocol]
    max_tokens = PROTOCOL_MAX_TOKENS[protocol]
    prompt_format = PROTOCOL_PROMPT_FORMAT[protocol]
    constrained_decoding = PROTOCOL_CONSTRAINED_DECODING[protocol]
    if output_dir is None:
        output_dir = f"results_v2/{protocol}/{model_key}/{suite}"

    sampled_temp = _D_SAMPLED_TRIAL_TEMPERATURE
    model_extra: dict = {}
    if protocol == "F6":
        preset = F6_RECOMMENDED_SAMPLING.get(model_key, {"temperature": sampled_temp, **_D_SAMPLING_DEFAULTS})
        sampled_temp = preset["temperature"]
        model_extra["sampling_preset"] = "recommended"
        trial_sampling_extra = {
            "trial_top_p": [_D_SAMPLING_DEFAULTS["top_p"], preset["top_p"], preset["top_p"]],
            "trial_top_k": [_D_SAMPLING_DEFAULTS["top_k"], preset["top_k"], preset["top_k"]],
            "trial_min_p": [_D_SAMPLING_DEFAULTS["min_p"], preset["min_p"], preset["min_p"]],
            "trial_repeat_penalty": [
                _D_SAMPLING_DEFAULTS["repeat_penalty"], preset["repeat_penalty"], preset["repeat_penalty"]
            ],
        }
    else:
        trial_sampling_extra = {}

    return {
        "experiment": f"upgradecanary-real-{protocol}-{model_key}-{suite}",
        "seed": 1234,
        "data": data_path,
        "output_dir": output_dir,
        "conditions": ["baseline", "schema_drift", "fault_reporting"],
        "trials": 3,
        "trial_temperatures": [0.0, sampled_temp, sampled_temp],
        "trial_seeds": [1234, 1235, 1236],
        **trial_sampling_extra,
        "prompt_format": prompt_format,
        "constrained_decoding": constrained_decoding,
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
            # F6 only (model_extra is {} for every other protocol): the
            # client-level top_p/top_k/min_p/repeat_penalty keys are
            # deliberately left UNSET here even under F6 -- they'd equal
            # _D_SAMPLING_DEFAULTS anyway, and the greedy trial already gets
            # those same values explicitly via trial_top_p[0] etc. above, so
            # setting them here too would be redundant, not a behavior
            # change. Only "sampling_preset" (a logging/documentation flag,
            # see docs/sampling_presets.md) is actually added.
            **model_extra,
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
