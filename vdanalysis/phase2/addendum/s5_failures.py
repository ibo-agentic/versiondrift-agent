"""S5: failure-type mechanism. Descriptive only, no test.

Failure categories per record (first failing check, so each failure counts once):
  tool-call conditions (schema_drift):  malformed_unparsed, wrong_tool_name, wrong_or_invalid_args, executor_fail
  fault_reporting:                      malformed_unparsed, wrong_status, fabricated_answer
(baseline is a tool-call condition too; it is counted in the per model x protocol x suite shares but not in the
stress shares used for S5.2.)

1. Failure-type shares per model x protocol x suite.
2. For each flip (factor vs its baseline, or rerun arm vs main arm): the change of every category's share between the
   old and the new model, factor minus baseline: ((new - old) under the factor) - ((new - old) under the baseline).
   Shares are stress-condition shares with equal weight over the stress conditions, as the stress diff is.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

CATEGORIES = ("malformed_unparsed", "wrong_tool_name", "wrong_or_invalid_args", "executor_fail",
              "wrong_status", "fabricated_answer")
TOOL_CALL = ("baseline", "schema_drift")


def classify(condition: str, metrics: dict) -> str | None:
    """None for a success; otherwise one of ``CATEGORIES`` (or 'other' if a failed record fails no named check)."""
    if float(metrics.get("score", 0)) == 1.0:
        return None
    if not metrics.get("parse_ok"):
        return "malformed_unparsed"
    if condition == "fault_reporting":
        if not metrics.get("status_ok"):
            return "wrong_status"
        if not metrics.get("no_fabrication", True):
            return "fabricated_answer"
        return "other"
    if not metrics.get("tool_name_ok"):
        return "wrong_tool_name"
    if not metrics.get("args_intent_match") or not metrics.get("args_valid_under_drift"):
        return "wrong_or_invalid_args"
    if not metrics.get("executor_ok"):
        return "executor_fail"
    return "other"


def shares_from_records(records) -> dict[str, dict[str, float]]:
    """``records``: iterable of (condition, metrics). Returns {condition: {n, <category>: share, ..., fail_total}}."""
    count: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for cond, m in records:
        c = count[cond]
        c["n"] += 1
        cat = classify(cond, m)
        if cat:
            c[cat] += 1
    out = {}
    for cond, c in count.items():
        n = c["n"]
        row = {"n": n}
        for k in CATEGORIES + ("other",):
            row[k] = c[k] / n if n else float("nan")
        row["fail_total"] = sum(c[k] for k in CATEGORIES + ("other",)) / n if n else float("nan")
        out[cond] = row
    return out


def stress_share(per_cond: dict[str, dict[str, float]], stress=("schema_drift", "fault_reporting")) -> dict[str, float]:
    """Equal-weight mean over the stress conditions that have records."""
    cs = [c for c in stress if c in per_cond and per_cond[c]["n"]]
    return {k: (sum(per_cond[c][k] for c in cs) / len(cs) if cs else float("nan")) for k in CATEGORIES + ("other", "fail_total")}


def read_records(run) -> list[tuple[str, dict]]:
    """(condition, metrics) of every record of a (merged) run, read from its part folders."""
    out = []
    for part in run.parts:
        f = Path(part) / "parsed_results.jsonl"
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    out.append((r["condition"], r["metrics"]))
    return out


def flip_changes(base_old: dict, base_new: dict, alt_old: dict, alt_new: dict) -> dict[str, float]:
    """Category-by-category change in (new - old) failure share, alternative minus baseline. Inputs are
    ``stress_share`` dicts."""
    out = {}
    for k in CATEGORIES + ("other", "fail_total"):
        out[k] = (alt_new[k] - alt_old[k]) - (base_new[k] - base_old[k])
    return out
