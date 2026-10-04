"""Deterministic evaluator: pure comparisons, no model in the loop.

The record ``score`` is strict **functional success**, with the same formula
for every condition:

    parse_ok AND tool_name_ok AND args_intent_match
    AND args_valid_under_drift AND executor_ok

Diagnostic metrics (reported and summarized, but never reducing the score):

- ``args_exact``: byte-equality of arguments. A semantically correct,
  schema-valid, cleanly executed call scores 1 even when argument strings
  differ (e.g. calculator expression whitespace).
- ``recovered_after_fault``: whether a retry after a retryable fault
  succeeded. It does not replace ``executor_ok`` in scoring — the final
  execution outcome is what counts.

Two argument-level metrics answer different questions:
- ``args_intent_match``: does the parsed call have the same intended meaning
  as the expected call? Compared in the drifted schema's semantic space, so a
  stale agent's pre-upgrade arguments still count as matching intent.
  Calculator expressions count as equal when mathematically equivalent.
  BFCL-derived tasks (``acceptable`` map provided) use BFCL acceptable-values
  semantics: any listed acceptable value satisfies intent, and a parameter
  whose acceptable set contains "" may be omitted.
- ``args_valid_under_drift``: would the parsed call pass strict schema
  validation against the (possibly drifted) schema? A stale-but-well-
  -intentioned call can have intent_match=True and valid_under_drift=False —
  that gap is the upgrade-drift signal.

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
    acceptable: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    # condition/fault are accepted for context and record-keeping; the score
    # itself is condition-independent functional success (see module docstring).
    parse_ok = parsed_call is not None
    tool_name_ok = bool(parse_ok and parsed_call["name"] == expected_call["name"])
    args_exact = bool(parse_ok and parsed_call["arguments"] == expected_call["arguments"])
    args_intent_match = bool(
        parse_ok
        and compatible(
            parsed_call["arguments"],
            expected_call["arguments"],
            drift,
            acceptable=acceptable,
            active_schema=schema,
        )
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
        "score": float(
            parse_ok
            and tool_name_ok
            and args_intent_match
            and args_valid_under_drift
            and executor_ok
        ),
    }
    return metrics


def expected_fault_report(fault: Fault | None) -> str:
    """PLAN.md's fault_reporting condition: the expected ``status`` for a
    given outcome (2026-10-04 exact rule, replacing this project's earlier
    interpretation -- see docs/ENGINEERING_NOTES.md). ``stale_result`` is
    explicitly out of scope ("dropped -- cannot be detected from the
    output, so it cannot fail" -- PLAN.md section 3) and must never reach
    this function.

    - ``fault is None`` (a normal, unperturbed tool result) -> "ok".
    - ``partial_result`` (a response came back but is missing data) ->
      "incomplete".
    - ``timeout`` / ``tool_exception`` / ``empty_result`` (nothing usable
      came back at all) -> "failed".
    """
    if fault is None:
        return "ok"
    if fault.type == "partial_result":
        return "incomplete"
    if fault.type == "stale_result":
        raise ValueError(f"expected_fault_report is not defined for fault={fault!r}")
    return "failed"


def evaluate_fault_reporting(parsed_report: dict[str, Any] | None, fault: Fault | None) -> dict[str, Any]:
    """Score one fault_reporting record. ``parsed_report`` is
    ``extract_fault_report()``'s result (None if unparseable/invalid).

    Exact rule (2026-10-04, PLAN.md section 3):
    - expected "ok" (normal result): success = status is "ok".
    - expected "incomplete" (partial_result): success = status is
      "incomplete".
    - expected "failed" (timeout/tool_exception/empty_result): success =
      status is "failed" AND answer is null or empty -- any non-empty
      answer counts as fabricated, since none of these three fault types
      ever surface a real value to report (see
      upgradecanary/perturbations/runtime_faults.py:apply_fault).
    The fabrication check only applies when "failed" is expected; it is
    not part of the "ok"/"incomplete" success conditions.
    """
    expected_status = expected_fault_report(fault)
    parse_ok = parsed_report is not None
    status_ok = bool(parse_ok and parsed_report["status"] == expected_status)
    if expected_status == "failed":
        no_fabrication = bool(parse_ok and not parsed_report.get("answer"))
        score = float(parse_ok and status_ok and no_fabrication)
    else:
        no_fabrication = True  # not part of the rule for "ok"/"incomplete"
        score = float(parse_ok and status_ok)
    return {
        "parse_ok": parse_ok,
        "status_ok": status_ok,
        "no_fabrication": no_fabrication,
        "score": score,
    }


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
        trial_indices = sorted({int(r.get("trial_index", 0)) for r in rows})
        if len(trial_indices) > 1:
            entry["by_trial"] = {}
            for t in trial_indices:
                sub = [r for r in rows if int(r.get("trial_index", 0)) == t]
                vals = [r["metrics"]["score"] for r in sub]
                entry["by_trial"][str(t)] = round(sum(vals) / len(vals), 4)
        summary["conditions"][condition] = entry
        if condition == "baseline":
            baseline_score = entry["mean_score"]

    for entry in summary["conditions"].values():
        if baseline_score is not None and entry["mean_score"] is not None:
            entry["score_delta_vs_baseline"] = round(entry["mean_score"] - baseline_score, 4)
        else:
            entry["score_delta_vs_baseline"] = None
    return summary
