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


def build_prompt(task: Task, schema: dict[str, Any]) -> str:
    # BFCL-derived tasks render the native upstream function document so the
    # model sees the same schema shape as in the source benchmark; synthetic
    # tasks render our internal schema.
    native = getattr(task, "tool_schema", None)
    if getattr(task, "suite", "synthetic") == "bfcl" and native is not None:
        tool_json = json.dumps({"tools": [native]}, indent=2, sort_keys=True)
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
            prompt = build_prompt(task, schema)
            base_context = {"task": task, "condition": condition, "drift": drift}

            for trial_index, trial in enumerate(trials):
                temperature = trial["temperature"]
                trial_seed = trial["seed"]
                context = dict(base_context, trial_index=trial_index)

                raw = client.generate(
                    prompt, context, temperature=temperature, seed=trial_seed
                )
                parsed = extract_tool_call(raw)
                exec_result = _safe_execute(
                    parsed, schema, drift, fault, strict, canonical_schema=base_schema
                )

                recovered: bool | None = None
                retry_prompt = None
                retry_raw = None
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
                    )
                    retry_parsed = extract_tool_call(retry_raw)
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
                        "retry_prompt_sha256": sha256_text(retry_prompt) if retry_prompt else None,
                        "retry_raw_output": retry_raw,
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
