"""Deterministic evaluator: pure comparisons, no model in the loop.

Metrics per record are booleans plus a condition-dependent score:
- baseline:      parse, exact tool name, exact arguments, clean execution
- schema_drift:  parse, tool name, intended meaning preserved, clean execution
- runtime_fault: recovery after a retryable fault; for non-retryable faults
                 (e.g. stale_result) a clean execution counts

Two argument-level metrics answer different questions:
- ``args_intent_match``: does the parsed call have the same intended meaning
  as the expected call? Compared in the drifted schema's semantic space, so a
  stale agent's pre-upgrade arguments still count as matching intent.
- ``args_valid_under_drift``: would the parsed call pass schema validation
  against the (possibly drifted) schema? A stale-but-well-intentioned call can
  have intent_match=True and valid_under_drift=False — that gap is the
  upgrade-drift signal.

Strict policy: required arguments must be present even if the field spec
declares a default; defaults are never auto-applied by the executor.
"""

from __future__ import annotations

from typing import Any

from .perturbations.runtime_faults import Fault, is_retryable
from .perturbations.schema_drift import Drift, compatible
from .tools import validate_call

_METRIC_KEYS = (
    "parse_ok",
    "tool_name_ok",
    "args_exact",
    "args_intent_match",
    "args_valid_under_drift",
    "executor_ok",
    "recovered_after_fault",
)


def evaluate(
    condition: str,
    expected_call: dict[str, Any],
    parsed_call: dict[str, Any] | None,
    exec_result: dict[str, Any],
    drift: Drift | None,
    fault: Fault | None,
    recovered_after_fault: bool | None,
    schema: dict[str, Any],
    strict: bool,
) -> dict[str, Any]:
    parse_ok = parsed_call is not None
    tool_name_ok = bool(parse_ok and parsed_call["name"] == expected_call["name"])
    args_exact = bool(parse_ok and parsed_call["arguments"] == expected_call["arguments"])
    args_intent_match = bool(
        parse_ok and compatible(parsed_call["arguments"], expected_call["arguments"], drift)
    )
    args_valid_under_drift = bool(
        parse_ok
        and not validate_call(parsed_call["name"], parsed_call["arguments"], schema, strict)
    )
    executor_ok = bool(exec_result.get("ok"))

    metrics: dict[str, Any] = {
        "parse_ok": parse_ok,
        "tool_name_ok": tool_name_ok,
        "args_exact": args_exact,
        "args_intent_match": args_intent_match,
        "args_valid_under_drift": args_valid_under_drift,
        "executor_ok": executor_ok,
        "recovered_after_fault": recovered_after_fault,
    }

    if condition == "baseline":
        score = parse_ok and tool_name_ok and args_exact and executor_ok
    elif condition == "schema_drift":
        score = parse_ok and tool_name_ok and args_intent_match and executor_ok
    elif condition == "runtime_fault":
        if is_retryable(fault):
            score = bool(recovered_after_fault)
        else:
            score = executor_ok
    else:
        score = False
    metrics["score"] = float(score)
    return metrics


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate metric means per condition plus delta vs baseline."""
    conditions: list[str] = []
    for record in records:
        if record["condition"] not in conditions:
            conditions.append(record["condition"])

    summary: dict[str, Any] = {
        "num_records": len(records),
        "conditions": {},
    }
    baseline_score: float | None = None
    for condition in conditions:
        rows = [r for r in records if r["condition"] == condition]
        entry: dict[str, Any] = {"n": len(rows)}
        for key in (*_METRIC_KEYS, "score"):
            vals = [r["metrics"][key] for r in rows if r["metrics"].get(key) is not None]
            entry[f"mean_{key}"] = round(sum(vals) / len(vals), 4) if vals else None
        summary["conditions"][condition] = entry
        if condition == "baseline":
            baseline_score = entry["mean_score"]

    for entry in summary["conditions"].values():
        if baseline_score is not None and entry["mean_score"] is not None:
            entry["score_delta_vs_baseline"] = round(entry["mean_score"] - baseline_score, 4)
        else:
            entry["score_delta_vs_baseline"] = None
    return summary
