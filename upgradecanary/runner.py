"""Experiment runner: task x condition matrix -> model -> parse -> execute -> score.

Writes four artifacts per run under results/<run_id>/:
- run_manifest.json    config snapshot, seed, versions
- raw_outputs.jsonl    prompt + raw model text (and retry attempt) per record
- parsed_results.jsonl parsed call, executor outcome, fault/drift, metrics
- summary.json         per-condition aggregate means and deltas vs baseline
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


def _safe_execute(parsed, schema, drift, fault, strict) -> dict[str, Any]:
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
        return execute(parsed, schema, drift, fault, strict)
    except Exception as exc:  # handler blew up (e.g. unknown canned key)
        return {
            "ok": False,
            "error": {"type": "exception", "message": f"{type(exc).__name__}: {exc}"},
        }


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
                drift = apply_drift(task.tool, drift_enabled, rng, task.drift_type)
            elif condition == "runtime_fault":
                fault = choose_fault(fault_enabled, rng)

            schema = drifted_schema(BASE_SCHEMAS[task.tool], drift)
            strict = strict_baseline and condition == "baseline"
            prompt = build_prompt(task, schema)
            context = {"task": task, "condition": condition, "drift": drift}

            raw = client.generate(prompt, context)
            parsed = extract_tool_call(raw)
            exec_result = _safe_execute(parsed, schema, drift, fault, strict)

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
                retry_raw = client.generate(retry_prompt, retry_context)
                retry_parsed = extract_tool_call(retry_raw)
                retry_exec = _safe_execute(retry_parsed, schema, drift, None, strict)
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
            )

            raw_rows.append(
                {
                    "run_id": rid,
                    "task_id": task.task_id,
                    "condition": condition,
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

    def record_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            row["task_id"],
            row["condition"],
            (row.get("drift") or {}).get("type", ""),
            (row.get("fault") or {}).get("type", ""),
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
