"""AUDIT question D/9: failure-mode breakdown per model x suite x condition.

Buckets every failing record (score == 0) into exactly one exclusive category,
in this priority order (matches the AND-chain in upgradecanary/evaluator.py
evaluate(), lines 95-101):

  1. parse_failure     : parse_ok is False
  2. wrong_tool_name    : parse_ok True, tool_name_ok False
  3. intent_mismatch    : tool_name_ok True, args_intent_match False
  4. invalid_under_drift: args_intent_match True, args_valid_under_drift False
  5. executor_failure   : args_valid_under_drift True, executor_ok False
  6. other              : score == 0 but none of the above (should not occur)

Read-only: only reads results/*/parsed_results.jsonl.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FINAL_RUNS, load_parsed, sc  # noqa: E402

CONDITIONS = ["baseline", "schema_drift", "runtime_fault"]


def bucket(m: dict) -> str:
    if not m["parse_ok"]:
        return "parse_failure"
    if not m["tool_name_ok"]:
        return "wrong_tool_name"
    if not m["args_intent_match"]:
        return "intent_mismatch"
    if not m["args_valid_under_drift"]:
        return "invalid_under_drift"
    if not m["executor_ok"]:
        return "executor_failure"
    return "other"


def main() -> None:
    header = (
        f"{'suite':9} {'model':12} {'cond':14} {'n':4} {'fail':5} "
        f"{'parse':6} {'wrong_tool':10} {'intent':7} {'invalid_drift':13} {'exec_fail':9} {'other':5}"
    )
    print(header)
    print("-" * len(header))

    totals_by_model = {}

    for (suite, model) in FINAL_RUNS:
        recs = load_parsed(suite, model)
        model_fail_buckets = totals_by_model.setdefault(
            (suite, model), {"n": 0, "fail": 0, "parse_failure": 0, "wrong_tool_name": 0,
                              "intent_mismatch": 0, "invalid_under_drift": 0,
                              "executor_failure": 0, "other": 0}
        )
        for cond in CONDITIONS:
            rows = [r for r in recs.values() if r["condition"] == cond]
            n = len(rows)
            buckets = {"parse_failure": 0, "wrong_tool_name": 0, "intent_mismatch": 0,
                       "invalid_under_drift": 0, "executor_failure": 0, "other": 0}
            fail = 0
            for r in rows:
                if sc(r) == 0.0:
                    fail += 1
                    b = bucket(r["metrics"])
                    buckets[b] += 1
                    model_fail_buckets[b] += 1
            model_fail_buckets["n"] += n
            model_fail_buckets["fail"] += fail
            print(
                f"{suite:9} {model:12} {cond:14} {n:4} {fail:5} "
                f"{buckets['parse_failure']:6} {buckets['wrong_tool_name']:10} "
                f"{buckets['intent_mismatch']:7} {buckets['invalid_under_drift']:13} "
                f"{buckets['executor_failure']:9} {buckets['other']:5}"
            )

    print("\n=== Q9: % of all failures that are parse/format failures, per (suite, model) ===")
    for (suite, model), t in totals_by_model.items():
        pct = 100.0 * t["parse_failure"] / t["fail"] if t["fail"] else 0.0
        print(f"{suite:9} {model:12}: fail={t['fail']:4} parse_failure={t['parse_failure']:4} ({pct:5.1f}%)")


if __name__ == "__main__":
    main()
