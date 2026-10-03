"""Experiment runner: task x condition x trial -> model -> parse -> execute -> score.

Each task-condition is repeated for every configured trial (``trials``,
``trial_temperatures``, ``trial_seeds``; default 1 trial using the model's
temperature/seed). Synthetic tasks draw schemas from the global registry;
BFCL-derived tasks (``suite == "bfcl"``) carry their own schemas and are
rendered to the model in BFCL-native form. Writes four artifacts per run
under results/<run_id>/:
- run_manifest.json    config snapshot, seed, versions, trial count
- raw_outputs.jsonl    prompt + raw model text (and retry attempt) per record,
                       with trial_index/temperature/seed
- parsed_results.jsonl parsed call, executor outcome, fault/drift, metrics,
                       with trial_index/temperature/seed (no volatile fields)
- summary.json         per-condition aggregate means, per-trial means, deltas
"""

from __future__ import annotations

import argparse
import json
import platform
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from . import __version__
from .bfcl import to_native_doc
from .constrained import response_schema_for, schema_to_openai_tool
from .evaluator import evaluate, summarize
from .model import create_client
from .parsing import extract_tool_call
from .perturbations.runtime_faults import choose as choose_fault
from .perturbations.runtime_faults import is_retryable
from .perturbations.schema_drift import apply as apply_drift
from .perturbations.schema_drift import drifted_schema
from .tasks import Task, load_tasks
from .tools import BASE_SCHEMAS, execute
from .utils import run_id, sha256_text, utc_now_iso, write_json, write_jsonl, rng_for


def build_prompt(task: Task, schema: dict[str, Any], prompt_format: str = "shared") -> str:
    # PLAN.md F3: "native" sends only the bare question -- the model's own
    # chat template renders the tool definitions from the tools= list
    # passed separately to ModelClient.generate() (see run(), below). This
    # requires chat_wrapping: native (validated in run()); the hand-built
    # JSON-in-prompt instruction below is specific to "shared" and has no
    # equivalent under a model's native tool template.
    if prompt_format == "native":
        return task.prompt
    if prompt_format != "shared":
        raise ValueError(f"prompt_format must be 'shared' or 'native', got {prompt_format!r}")
    # BFCL-derived tasks render the BFCL-native form of the PASSED schema, so
    # schema drift is visible to the model exactly as the evaluator/executor
    # apply it; synthetic tasks render our internal schema.
    native = getattr(task, "tool_schema", None)
    candidates = getattr(task, "candidate_schemas", None)
    if getattr(task, "suite", "synthetic") == "bfcl" and candidates is not None:
        # BFCL "multiple" category (PLAN.md 10.1 item 3): every candidate is
        # shown. The correct tool (matched by name -- drift never renames a
        # tool, only its arguments, so schema["name"] == native["name"]
        # always holds) renders the DRIFTED schema, exactly as the
        # single-tool case; every distractor renders verbatim, never
        # drift-perturbed, per PLAN.md section 3's "schema drift applies
        # only to the gold tool's schema; distractor tools unchanged."
        tools_native = [
            to_native_doc(schema, candidate) if candidate.get("name") == schema.get("name") else candidate
            for candidate in candidates
        ]
        tool_json = json.dumps({"tools": tools_native}, indent=2, sort_keys=True)
    elif getattr(task, "suite", "synthetic") == "bfcl" and native is not None:
        tool_json = json.dumps({"tools": [to_native_doc(schema, native)]}, indent=2, sort_keys=True)
    else:
        tool_json = json.dumps({"tools": [schema]}, indent=2, sort_keys=True)
    return (
        "You are an agent that answers questions by calling tools.\n"
        f"Available tool schema:\n{tool_json}\n"
        "Reply with ONLY a single JSON object of the form "
        '{"name": <tool name>, "arguments": {<args>}}. '
        "No markdown fences, no explanation, no text before or after the JSON.\n"
        f"Question: {task.prompt}\n"
        "Answer:"
    )


def resolve_run_factors(cfg: dict[str, Any]) -> dict[str, Any]:
    """PLAN.md section 5's F1-F6 as an explicit, logged summary -- read
    straight from the raw config (no model instantiation needed), so every
    run (including the mock provider) gets one unambiguous record of which
    factor levels it used. Values mirror the config's own keys/defaults;
    this function does not invent a level the config didn't ask for.
    """
    model_cfg = cfg.get("model", {})
    return {
        "F1_max_tokens": model_cfg.get("max_tokens"),
        "F2_thinking": model_cfg.get("thinking", "default"),
        "F3_prompt_format": cfg.get("prompt_format", "shared"),
        "F4_constrained_decoding": cfg.get("constrained_decoding", "off"),
        "F5_quant_level": model_cfg.get("quant_level", "unspecified"),
        "F6_sampling_preset": model_cfg.get("sampling_preset", "shared"),
        "F11_chat_wrapping": model_cfg.get("chat_wrapping", "legacy"),
        # 2026-10-03: explicit regardless of provider (not just inside
        # llama_cpp's own backend_info()) -- PLAN.md's n_ctx=4096-for-all-
        # new-runs decision needs to be visible/auditable for every run.
        "n_ctx": model_cfg.get("n_ctx", 4096),
    }


def validate_run_factors(cfg: dict[str, Any]) -> None:
    """Config-time checks for factor levels/combinations that cannot work.
    Raises ValueError with a clear message; called before any model call."""
    model_cfg = cfg.get("model", {})
    prompt_format = cfg.get("prompt_format", "shared")
    constrained_decoding = cfg.get("constrained_decoding", "off")
    sampling_preset = model_cfg.get("sampling_preset", "shared")
    chat_wrapping = model_cfg.get("chat_wrapping", "legacy")

    if prompt_format not in ("shared", "native"):
        raise ValueError(f"prompt_format must be 'shared' or 'native', got {prompt_format!r}")
    if constrained_decoding not in ("off", "generic_json", "full_schema"):
        raise ValueError(
            f"constrained_decoding must be 'off', 'generic_json', or 'full_schema', got {constrained_decoding!r}"
        )
    if sampling_preset not in ("shared", "recommended"):
        raise ValueError(f"model.sampling_preset must be 'shared' or 'recommended', got {sampling_preset!r}")
    if prompt_format == "native" and chat_wrapping != "native":
        raise ValueError(
            "prompt_format: native requires model.chat_wrapping: native -- "
            "legacy wrapping has no mechanism to pass a tools= list into a "
            "hand-built template string."
        )


def _safe_execute(parsed, schema, drift, fault, strict, canonical_schema=None) -> dict[str, Any]:
    """Execute a parsed call, converting any failure into a structured result."""
    if parsed is None:
        return {
            "ok": False,
            "error": {
                "type": "parse_failure",
                "message": "model output contained no valid tool call",
            },
        }
    try:
        return execute(parsed, schema, drift, fault, strict, canonical_schema=canonical_schema)
    except Exception as exc:  # handler blew up (e.g. unknown canned key)
        return {
            "ok": False,
            "error": {"type": "exception", "message": f"{type(exc).__name__}: {exc}"},
        }


def build_trials(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve the trial list from config: one {temperature, seed} per trial.

    ``trial_temperatures``/``trial_seeds`` fall back to the model's defaults
    repeated ``trials`` times; explicit lists must match ``trials`` in length.
    """
    n = int(cfg.get("trials", 1))
    if n < 1:
        raise ValueError(f"trials must be >= 1, got {n}")
    model = cfg.get("model", {})
    temps = cfg.get("trial_temperatures")
    seeds = cfg.get("trial_seeds")
    if temps is None:
        temps = [model.get("temperature", 0.0)] * n
    if seeds is None:
        seeds = [model.get("seed", 0)] * n
    if len(temps) != n or len(seeds) != n:
        raise ValueError(
            f"trials={n} but trial_temperatures has {len(temps)} entries "
            f"and trial_seeds has {len(seeds)}"
        )
    return [{"temperature": float(t), "seed": int(s)} for t, s in zip(temps, seeds)]


def task_base_schema(task: Task) -> dict[str, Any]:
    """Canonical schema for a task: per-task for BFCL, registry for synthetic."""
    if task.suite == "bfcl" and task.internal_schema is not None:
        return task.internal_schema
    return BASE_SCHEMAS[task.tool]


def run(config_path: str) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    validate_run_factors(cfg)

    seed = int(cfg["seed"])
    rid = run_id(cfg.get("experiment", "run"), seed)
    out_dir = Path(cfg["output_dir"]) / rid

    tasks = load_tasks(cfg["data"])
    task_limit = cfg.get("task_limit")
    if task_limit is not None:
        tasks = tasks[: int(task_limit)]

    client = create_client(cfg["model"])
    trials = build_trials(cfg)

    drift_enabled = cfg["perturbations"]["schema_drift"].get("enabled", [])
    fault_cfg = cfg["perturbations"]["runtime_faults"]
    fault_enabled = fault_cfg.get("enabled", [])
    retry_once = bool(fault_cfg.get("retry_once", True))
    strict_baseline = bool(cfg.get("executor", {}).get("strict_baseline_args", True))
    # Off by default; see upgradecanary/parsing.py. Existing configs have no
    # "parsing" key, so extract_tool_call behavior is unchanged unless a
    # config explicitly opts in (2026-10-02 audit follow-up, item 2).
    strip_think = bool(cfg.get("parsing", {}).get("strip_think_block", False))
    # PLAN.md F3/F4. Both default to the exact pre-existing behavior
    # ("shared" prompt text, no constrained decoding) when the keys are
    # absent, so every existing config is unaffected.
    prompt_format = cfg.get("prompt_format", "shared")
    constrained_decoding = cfg.get("constrained_decoding", "off")

    raw_rows: list[dict[str, Any]] = []
    parsed_rows: list[dict[str, Any]] = []

    for task in tasks:
        for condition in cfg["conditions"]:
            if task.condition_tags and condition not in task.condition_tags:
                continue

            rng = rng_for(seed, task.task_id, condition)
            drift = None
            fault = None
            if condition == "schema_drift":
                drift = apply_drift(
                    task.tool, drift_enabled, rng, task.drift_type,
                    schema=task_base_schema(task),
                )
            elif condition == "runtime_fault":
                fault = choose_fault(fault_enabled, rng)

            base_schema = task_base_schema(task)
            schema = drifted_schema(base_schema, drift)
            strict = strict_baseline and condition == "baseline"
            prompt = build_prompt(task, schema, prompt_format=prompt_format)
            base_context = {"task": task, "condition": condition, "drift": drift}
            tools = [schema_to_openai_tool(schema)] if prompt_format == "native" else None
            response_schema = response_schema_for(constrained_decoding, schema)

            for trial_index, trial in enumerate(trials):
                temperature = trial["temperature"]
                trial_seed = trial["seed"]
                context = dict(base_context, trial_index=trial_index)

                raw = client.generate(
                    prompt, context, temperature=temperature, seed=trial_seed,
                    tools=tools, response_schema=response_schema,
                )
                truncated = (
                    client.last_truncated() if hasattr(client, "last_truncated") else None
                )
                parsed = extract_tool_call(raw, strip_think=strip_think)
                exec_result = _safe_execute(
                    parsed, schema, drift, fault, strict, canonical_schema=base_schema
                )

                recovered: bool | None = None
                retry_prompt = None
                retry_raw = None
                retry_truncated = None
                if (
                    condition == "runtime_fault"
                    and is_retryable(fault)
                    and not exec_result.get("ok")
                    and retry_once
                ):
                    feedback = exec_result.get("error", {}).get("message", "tool call failed")
                    retry_prompt = (
                        prompt
                        + f"\nYour previous tool call failed: {feedback}\n"
                        + "Provide a corrected JSON answer:"
                    )
                    retry_context = dict(context, is_retry=True, feedback=feedback)
                    retry_raw = client.generate(
                        retry_prompt,
                        retry_context,
                        temperature=temperature,
                        seed=trial_seed,
                        tools=tools,
                        response_schema=response_schema,
                    )
                    retry_truncated = (
                        client.last_truncated() if hasattr(client, "last_truncated") else None
                    )
                    retry_parsed = extract_tool_call(retry_raw, strip_think=strip_think)
                    retry_exec = _safe_execute(
                        retry_parsed, schema, drift, None, strict,
                        canonical_schema=base_schema,
                    )
                    recovered = bool(retry_exec.get("ok"))
                    exec_result = {
                        "first_attempt": exec_result,
                        "retry": retry_exec,
                        "ok": retry_exec.get("ok", False),
                    }

                metrics = evaluate(
                    condition,
                    task.expected_call,
                    parsed,
                    exec_result,
                    drift,
                    fault,
                    recovered,
                    schema,
                    strict,
                    acceptable=task.acceptable,
                )

                raw_rows.append(
                    {
                        "run_id": rid,
                        "task_id": task.task_id,
                        "condition": condition,
                        "trial_index": trial_index,
                        "temperature": temperature,
                        "seed": trial_seed,
                        "prompt_sha256": sha256_text(prompt),
                        "prompt": prompt,
                        "raw_output": raw,
                        # None = unknown/not applicable (e.g. mock client);
                        # True/False only for backends that report a finish
                        # reason (2026-10-02 audit follow-up, item 2).
                        "truncated": truncated,
                        "retry_prompt_sha256": sha256_text(retry_prompt) if retry_prompt else None,
                        "retry_raw_output": retry_raw,
                        "retry_truncated": retry_truncated,
                    }
                )
                # No run_id/timestamps here: parsed_results.jsonl must stay
                # byte-identical across reruns of the same config. Volatile
                # metadata lives in run_manifest.json instead.
                parsed_rows.append(
                    {
                        "task_id": task.task_id,
                        "condition": condition,
                        "trial_index": trial_index,
                        "temperature": temperature,
                        "seed": trial_seed,
                        "drift": asdict(drift) if drift else None,
                        "fault": asdict(fault) if fault else None,
                        "parsed_call": parsed,
                        "exec_result": exec_result,
                        "metrics": metrics,
                    }
                )

    summary = summarize(parsed_rows)
    summary["run_id"] = rid
    summary["model_provider"] = cfg["model"].get("provider", "mock")
    summary["num_trials"] = len(trials)

    def record_key(row: dict[str, Any]) -> tuple[str, str, str, str, int]:
        return (
            row["task_id"],
            row["condition"],
            (row.get("drift") or {}).get("type", ""),
            (row.get("fault") or {}).get("type", ""),
            int(row.get("trial_index", 0)),
        )

    raw_rows.sort(key=record_key)
    parsed_rows.sort(key=record_key)

    write_jsonl(out_dir / "raw_outputs.jsonl", raw_rows)
    write_jsonl(out_dir / "parsed_results.jsonl", parsed_rows)
    write_json(out_dir / "summary.json", summary)
    write_json(
        out_dir / "run_manifest.json",
        {
            "run_id": rid,
            "created_utc": utc_now_iso(),
            "config_path": str(config_path),
            "seed": seed,
            "package_version": __version__,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "num_tasks": len(tasks),
            "num_trials": len(trials),
            "num_records": len(parsed_rows),
            # Backend/version/sampling-params snapshot for reproducibility
            # (2026-10-02 audit follow-up, item 4). {} for the mock client,
            # which has no backend_info().
            "model_backend": client.backend_info() if hasattr(client, "backend_info") else {},
            # PLAN.md section 5, F1-F6 + F11: one explicit, unambiguous
            # record of every factor level this run used (PLAN.md 10.1
            # item 2: "All choices must be logged in run_manifest.json").
            "run_factors": resolve_run_factors(cfg),
        },
    )
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run an UpgradeCanary experiment.")
    parser.add_argument("--config", required=True, help="Path to a YAML config file.")
    args = parser.parse_args(argv)
    summary = run(args.config)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
