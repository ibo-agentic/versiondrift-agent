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
    # Controls (PLAN.md section 6, 2026-10-11): all three are R's config
    # with exactly one change each (seed / tool-description text / model
    # quant file) -- thinking itself stays "default" for all of them.
    "R_AA": "default",
    "R_PC_NODESC": "default",
    "R_PC_Q2K": "default",
    # R_F6/R_F3 (nuisance factors under R, 2026-10-12): thinking stays
    # "default" -- R_F3's Qwen3 would have the same grammar+thinking-
    # blocked side effect as R itself if it were run on Qwen3, but Qwen3
    # isn't a held-out model so it's out of scope for R_F3 this round.
    "R_F6": "default",
    "R_F3": "default",
    # F11 (legacy chat wrapping, exploratory): D's config, only the
    # wrapping mechanism changes -- thinking stays "default" (Qwen3 has
    # no <think>-prefill trick under the plain legacy template, so it
    # keeps thinking ON, same as D's own default; this is a real,
    # expected consequence of swapping wrapping, not a second change).
    "F11": "default",
    # F5 / R_F5 (Q8_0 quantization, 2026-10-13): D's / R's config with ONLY
    # the model file changed -- thinking stays "default".
    "F5": "default",
    "R_F5": "default",
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
    "R_AA": 1024,
    "R_PC_NODESC": 1024,
    "R_PC_Q2K": 1024,
    "R_F6": 1024,
    "R_F3": 1024,
    # F11 (legacy chat wrapping): D's own budget, 256 -- only the
    # wrapping mechanism changes.
    "F11": 256,
    "F5": 256,       # = D
    "R_F5": 1024,    # = R
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
    "R_AA": "shared",
    # R_PC_NODESC's ONE change from R: strip tool/parameter descriptions
    # (runner.py's build_prompt already supports this prompt_format value
    # -- PLAN.md section 6 positive control (b)). Names, types, and
    # "required" are untouched (see _strip_descriptions' own docstring).
    "R_PC_NODESC": "no_description",
    "R_PC_Q2K": "shared",
    "R_F6": "shared",
    # R_F3's ONE change from R: native tool template for the prompt
    # (tools= rendering), same mechanism as F3 -- output stays grammar-
    # constrained to generic JSON regardless (constrained_decoding is
    # unchanged, see PROTOCOL_CONSTRAINED_DECODING below). validate_run_
    # factors() already requires chat_wrapping: native for this, which
    # every protocol except F11 already sets.
    "R_F3": "native",
    "F11": "shared",
    "F5": "shared",
    "R_F5": "shared",
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
    "R_AA": "generic_json",
    "R_PC_NODESC": "generic_json",
    "R_PC_Q2K": "generic_json",
    "R_F6": "generic_json",
    "R_F3": "generic_json",
    # F11 (legacy chat wrapping): D's own "off" -- only the wrapping
    # mechanism changes.
    "F11": "off",
    "F5": "off",              # = D
    "R_F5": "generic_json",   # = R
}
# protocol -> seed override. Every protocol above uses the project's one
# shared seed (1234); R_AA (PLAN.md section 6's A/A null control) is R
# rerun with a different seed, 5678, and nothing else -- the ONLY
# intentional seed change in this project. Threads into build_config's
# top-level seed, model.seed, and trial_seeds (offset by the same amount
# as D's own 1234/1235/1236 convention: base, base+1, base+2).
PROTOCOL_SEED = {"R_AA": 5678}
_DEFAULT_SEED = 1234

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


# PLAN.md section 6 positive control (a), 2026-10-11: Q2_K quant of the
# same 4 models used for every control (mistral_v03, qwen25, llama31,
# granite32). Downloaded from each model's own Q4_K_M source repo except
# mistral_v03 (itlwas/Mistral-7B-Instruct-v0.3-Q4_K_M-GGUF ships only that
# one quant, no Q2_K -- asked the user directly; decided to use
# bartowski/Mistral-7B-Instruct-v0.3-GGUF's Q2_K instead, same base model,
# different uploader/quantizer). See docs/model_manifest.md for sha256s.
Q2K_MODEL_PATHS: dict[str, str] = {
    # NOT from itlwas (that repo has no Q2_K) -- from bartowski instead,
    # kept in its own path so the uploader change is visible, not hidden
    # inside the itlwas/ directory alongside the Q4_K_M file.
    "mistral_v03": "models/mistral_bartowski/Mistral-7B-Instruct-v0.3-Q2_K.gguf",
    "qwen25": "models/qwen/qwen2.5-7b-instruct-q2_k.gguf",
    "llama31": "models/llama/Meta-Llama-3.1-8B-Instruct-Q2_K.gguf",
    "granite32": "models/granite/ibm-granite_granite-3.2-8b-instruct-Q2_K.gguf",
}

# F5 / R_F5 (PLAN.md F5, Q8_0), laptop side: only the 5 small models run
# here (gemma2_2b, gemma3_4b, phi3_mini, phi35_mini, phi4_mini; same repos as
# their Q4_K_M files). The 8B models' Q8_0 does not fit in 8 GB of VRAM and
# runs on Kaggle (kaggle/, results land in the same results_v2/F5 and
# results_v2/R_F5 folders). Sources/hashes: docs/model_manifest.md section 7.
# A model not listed here has no local Q8_0 -> KeyError, never a silent
# fallback to Q4_K_M.
Q8_0_MODEL_PATHS: dict[str, str] = {
    "gemma2_2b": "models/gemma/gemma-2-2b-it-Q8_0.gguf",
    "gemma3_4b": "models/gemma/google_gemma-3-4b-it-Q8_0.gguf",
    "phi3_mini": "models/phi/Phi-3-mini-4k-instruct-Q8_0.gguf",
    "phi35_mini": "models/phi/Phi-3.5-mini-instruct-Q8_0.gguf",
    "phi4_mini": "models/phi/microsoft_Phi-4-mini-instruct-Q8_0.gguf",
}

# F11 (legacy chat wrapping, exploratory, 2026-10-12): the hand-typed
# wrapper strings this project used before PLAN v1's native-template work
# -- fetched from this project's own pre-PLAN configs (e.g. configs/
# real_trials_itlwas_v0.3.yaml, configs/real_smoke_qwen3.yaml), not
# reinvented. Mistral's own "[INST]" form (no explicit leading <s> --
# llama.cpp's own tokenizer adds BOS); Qwen's own ChatML form, identical
# across Qwen2/2.5/3 (same special tokens in all three). Deliberately
# does NOT include Qwen3's <think></think> empty-prefill trick (that's a
# separate, F2-specific mechanism) -- under F11, Qwen3's thinking stays
# on by default, same as D, consistent with "only the wrapping changes."
F11_PROMPT_TEMPLATES: dict[str, str] = {
    "mistral_v01": "[INST]\n{prompt}\n[/INST]",
    "mistral_v02": "[INST]\n{prompt}\n[/INST]",
    "mistral_v03": "[INST]\n{prompt}\n[/INST]",
    "qwen2": "<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant",
    "qwen25": "<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant",
    "qwen3": "<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant",
}


def build_config(
    model_key: str, gguf_path: str, suite: str, data_path: str,
    protocol: str = "D", output_dir: str | None = None,
) -> dict:
    thinking = PROTOCOL_THINKING[protocol]
    max_tokens = PROTOCOL_MAX_TOKENS[protocol]
    prompt_format = PROTOCOL_PROMPT_FORMAT[protocol]
    constrained_decoding = PROTOCOL_CONSTRAINED_DECODING[protocol]
    seed = PROTOCOL_SEED.get(protocol, _DEFAULT_SEED)
    if output_dir is None:
        output_dir = f"results_v2/{protocol}/{model_key}/{suite}"

    sampled_temp = _D_SAMPLED_TRIAL_TEMPERATURE
    model_extra: dict = {}
    if protocol in ("F6", "R_F6"):
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
    if protocol == "R_PC_Q2K":
        # Labels the semantic change explicitly in run_factors.F5_quant_level
        # (resolve_run_factors reads model.quant_level) -- model_backend.
        # model_path also differs (necessarily, swapping quant means
        # swapping the file), so this is a second, clearer label for the
        # same single change, not an additional change.
        model_extra["quant_level"] = "Q2_K"
    if protocol in ("F5", "R_F5"):
        # Same label mechanism as R_PC_Q2K: run_factors.F5_quant_level.
        model_extra["quant_level"] = "Q8_0"
    chat_wrapping = "native"
    if protocol == "F11":
        chat_wrapping = "legacy"
        model_extra["prompt_template"] = F11_PROMPT_TEMPLATES[model_key]

    return {
        "experiment": f"upgradecanary-real-{protocol}-{model_key}-{suite}",
        "seed": seed,
        "data": data_path,
        "output_dir": output_dir,
        "conditions": ["baseline", "schema_drift", "fault_reporting"],
        "trials": 3,
        "trial_temperatures": [0.0, sampled_temp, sampled_temp],
        "trial_seeds": [seed, seed + 1, seed + 2],
        **trial_sampling_extra,
        "prompt_format": prompt_format,
        "constrained_decoding": constrained_decoding,
        "model": {
            "provider": "llama_cpp",
            "path": gguf_path,
            "chat_wrapping": chat_wrapping,
            "n_ctx": 4096,
            "n_gpu_layers": -1,
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "seed": seed,
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
    if protocol == "R_PC_Q2K":
        gguf_path = Q2K_MODEL_PATHS[model_key]
    elif protocol in ("F5", "R_F5"):
        gguf_path = Q8_0_MODEL_PATHS[model_key]
    else:
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
