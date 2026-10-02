"""Shared read-only helpers for the AUDIT.md analyses.

Reuses the exact record-matching convention and functional-score formula
from scripts/analyze_version_trials.py (task_id, condition, drift type,
fault type, trial_index) and
parse_ok & tool_name_ok & args_intent_match & args_valid_under_drift & executor_ok.
No existing files are written to; this module only reads results/*/parsed_results.jsonl
and results/*/raw_outputs.jsonl.
"""

from __future__ import annotations

import json
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

FINAL_RUNS = {
    ("synthetic", "Mistral v0.1"): "upgradecanary-real-trials-itlwas-v0.1_seed1234_20260929T120210Z",
    ("synthetic", "Mistral v0.2"): "upgradecanary-real-trials-itlwas-v0.2_seed1234_20260929T121701Z",
    ("synthetic", "Mistral v0.3"): "upgradecanary-real-trials-itlwas-v0.3_seed1234_20260929T192811Z",
    ("synthetic", "Qwen2.5"): "upgradecanary-real-trials-qwen25_seed1234_20260929T222007Z",
    ("synthetic", "Qwen3"): "upgradecanary-real-trials-qwen3_seed1234_20260929T230135Z",
    ("BFCL", "Mistral v0.1"): "upgradecanary-bfcl-trials-itlwas-v0.1_seed1234_20261001T142620Z",
    ("BFCL", "Mistral v0.2"): "upgradecanary-bfcl-trials-itlwas-v0.2_seed1234_20261001T151819Z",
    ("BFCL", "Mistral v0.3"): "upgradecanary-bfcl-trials-itlwas-v0.3_seed1234_20261001T160749Z",
    ("BFCL", "Qwen2.5"): "upgradecanary-bfcl-trials-qwen25_seed1234_20261001T162536Z",
    ("BFCL", "Qwen3"): "upgradecanary-bfcl-trials-qwen3_seed1234_20261001T190657Z",
}

# Pre-fix BFCL runs retained for the H (old vs new) comparison only.
PREFIX_BFCL_RUNS = {
    "Mistral v0.1": "upgradecanary-bfcl-trials-itlwas-v0.1_seed1234_20261001T042558Z",
    "Mistral v0.2": "upgradecanary-bfcl-trials-itlwas-v0.2_seed1234_20261001T045510Z",
    "Mistral v0.3": "upgradecanary-bfcl-trials-itlwas-v0.3_seed1234_20261001T051347Z",
    "Qwen2.5": "upgradecanary-bfcl-trials-qwen25_seed1234_20261001T053040Z",
    "Qwen3": "upgradecanary-bfcl-trials-qwen3_seed1234_20261001T054551Z",
}

UPGRADE_PAIRS = [
    ("Mistral v0.1", "Mistral v0.2"),
    ("Mistral v0.2", "Mistral v0.3"),
    ("Mistral v0.1", "Mistral v0.3"),
    ("Qwen2.5", "Qwen3"),
]


# Qwen3 thinking-mode-fix reruns (2026-10-02 follow-up). nothink = primary
# corrected config (thinking disabled); think_long = secondary corrected
# config (thinking on, budget raised to 2048). The original ("Qwen3" in
# FINAL_RUNS above) is referred to as "pre-fix" wherever these are compared.
NEW_QWEN_RUNS = {
    ("synthetic", "Qwen3-nothink"): "upgradecanary-real-trials-qwen3-nothink_seed1234_20261001T213910Z",
    ("BFCL", "Qwen3-nothink"): "upgradecanary-bfcl-trials-qwen3-nothink_seed1234_20261001T220328Z",
    ("synthetic", "Qwen3-think_long"): "upgradecanary-real-trials-qwen3-think-long_seed1234_20261001T221907Z",
    ("BFCL", "Qwen3-think_long"): "upgradecanary-bfcl-trials-qwen3-think-long_seed1234_20261001T232407Z",
}


def run_dir(suite: str, model: str) -> str:
    if (suite, model) in NEW_QWEN_RUNS:
        return os.path.join(REPO_ROOT, "results", NEW_QWEN_RUNS[(suite, model)])
    return os.path.join(REPO_ROOT, "results", FINAL_RUNS[(suite, model)])


def load_parsed(suite: str, model: str) -> dict:
    path = os.path.join(run_dir(suite, model), "parsed_results.jsonl")
    recs = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            p = json.loads(line)
            key = (
                p["task_id"],
                p["condition"],
                (p.get("drift") or {}).get("type"),
                (p.get("fault") or {}).get("type"),
                p.get("trial_index", 0),
            )
            recs[key] = p
    return recs


def load_raw(suite: str, model: str) -> dict:
    path = os.path.join(run_dir(suite, model), "raw_outputs.jsonl")
    rows = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            key = (row["task_id"], row["condition"], row["trial_index"])
            rows[key] = row
    return rows


def task_lookup(suite: str) -> dict:
    """task_id -> Task, for schema/expected-call reconstruction."""
    import sys

    sys.path.insert(0, REPO_ROOT)
    from upgradecanary.tasks import load_tasks

    path = os.path.join(REPO_ROOT, "data", "base_tasks.jsonl" if suite == "synthetic" else "bfcl_tasks.jsonl")
    return {t.task_id: t for t in load_tasks(path)}


def _to_drift(d):
    if not d:
        return None
    from upgradecanary.perturbations.schema_drift import Drift

    return Drift(type=d["type"], tool=d["tool"], field=d["field"], params=d.get("params", {}))


def _to_fault(f):
    if not f:
        return None
    from upgradecanary.perturbations.runtime_faults import Fault

    return Fault(type=f["type"], params=f.get("params", {}))


def recompute_record(
    tasks: dict,
    prec: dict,
    rrow: dict,
    *,
    use_final_attempt: bool = False,
    lenient: bool = False,
    strip_think: bool = False,
):
    """Re-derive metrics for one record straight from its raw text + the
    existing (unmodified) deterministic pipeline functions -- no model call.

    use_final_attempt=False, lenient=False, strip_think=False reproduces the
    ORIGINAL stored scoring exactly (same mixed first-attempt/retry metric
    computation as upgradecanary/runner.py); this is checked for parity by
    every script that uses this function. Returns
    (final_metrics, first_try_metrics).
    """
    from upgradecanary.runner import _safe_execute, task_base_schema
    from upgradecanary.perturbations.schema_drift import drifted_schema
    from upgradecanary.perturbations.runtime_faults import is_retryable
    from upgradecanary.evaluator import evaluate
    from upgradecanary.parsing import extract_tool_call

    task = tasks[prec["task_id"]]
    condition = prec["condition"]
    drift = _to_drift(prec.get("drift"))
    fault = _to_fault(prec.get("fault"))
    base_schema = task_base_schema(task)
    schema = drifted_schema(base_schema, drift)
    strict = condition == "baseline"  # strict_baseline_args: true in every config used here

    first_raw = rrow.get("raw_output", "") or ""
    first_parsed = extract_tool_call(first_raw, strip_think=strip_think, lenient=lenient)
    first_exec = _safe_execute(first_parsed, schema, drift, fault, strict, canonical_schema=base_schema)
    first_metrics = evaluate(
        condition, task.expected_call, first_parsed, first_exec, drift, fault, None,
        schema, strict, acceptable=task.acceptable,
    )

    final_parsed, final_exec, recovered = first_parsed, first_exec, None
    did_retry = (
        condition == "runtime_fault"
        and is_retryable(fault)
        and not first_exec.get("ok")
        and rrow.get("retry_raw_output") is not None
    )
    if did_retry:
        retry_raw = rrow.get("retry_raw_output", "") or ""
        retry_parsed = extract_tool_call(retry_raw, strip_think=strip_think, lenient=lenient)
        retry_exec = _safe_execute(retry_parsed, schema, drift, None, strict, canonical_schema=base_schema)
        recovered = bool(retry_exec.get("ok"))
        if use_final_attempt:
            final_parsed, final_exec = retry_parsed, retry_exec
        else:
            # Original (mixed) behavior: four metrics stay first-attempt,
            # only executor_ok/score reflect the retry's outcome.
            final_exec = {"first_attempt": first_exec, "retry": retry_exec, "ok": retry_exec.get("ok", False)}

    final_metrics = evaluate(
        condition, task.expected_call, final_parsed, final_exec, drift, fault, recovered,
        schema, strict, acceptable=task.acceptable,
    )
    return final_metrics, first_metrics


def functional(m: dict) -> float:
    return (
        1.0
        if (
            m["parse_ok"]
            and m["tool_name_ok"]
            and m["args_intent_match"]
            and m["args_valid_under_drift"]
            and m["executor_ok"]
        )
        else 0.0
    )


def sc(rec: dict) -> float:
    return functional(rec["metrics"])
