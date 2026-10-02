"""Calibration check: relaxed_compatible(..., causes=ALL_CAUSES) must agree
with the strict metric on all 32 agreements in intent_spotcheck_filled.csv,
and must flip exactly the 8 known disagreements (all rule=False/human=yes)
to True. Not a deliverable; a one-off self-test before trusting the full
scan.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from common import load_parsed, task_lookup  # noqa: E402
from relaxed_intent import ALL_CAUSES, relaxed_compatible  # noqa: E402

from upgradecanary.runner import task_base_schema  # noqa: E402
from upgradecanary.perturbations.schema_drift import Drift, drifted_schema  # noqa: E402


def to_drift(d):
    return Drift(type=d["type"], tool=d["tool"], field=d["field"], params=d.get("params", {})) if d else None


def main() -> None:
    with open(Path(__file__).parent / "intent_spotcheck_filled.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    tasks_cache = {}
    n_total = n_agree_with_rule_when_true = n_match_strict = n_match_relaxed = 0
    mismatches = []
    for row in rows:
        suite, model = row["suite"], row["model"]
        if suite not in tasks_cache:
            tasks_cache[suite] = task_lookup(suite)
        tasks = tasks_cache[suite]
        recs = load_parsed(suite, model)
        key = (row["task_id"], "schema_drift", row["drift_type"] or None, None, int(row["trial_index"]))
        # drift field in key tuple position 2 must match stored key; find by scanning task_id+trial since
        # fault-type slot is always None for schema_drift and drift-type slot must match exactly.
        matches = [k for k in recs if k[0] == row["task_id"] and k[1] == "schema_drift" and k[4] == int(row["trial_index"])]
        if not matches:
            print("NOT FOUND:", row["task_id"], model, suite)
            continue
        prec = recs[matches[0]]
        task = tasks[prec["task_id"]]
        drift = to_drift(prec.get("drift"))
        base_schema = task_base_schema(task)
        schema = drifted_schema(base_schema, drift)
        parsed_call = prec.get("parsed_call") or {}
        parsed_args = parsed_call.get("arguments", {})

        strict = bool(prec["metrics"]["args_intent_match"])
        relaxed = relaxed_compatible(parsed_args, task.expected_call["arguments"], drift, task.acceptable, schema, set(ALL_CAUSES))

        rule_v = row["rule_verdict"].strip() == "True"
        human_v = row["human_verdict"].strip().lower() == "yes"
        n_total += 1
        if strict != rule_v:
            mismatches.append((row["task_id"], model, "strict recompute != stored rule_verdict", strict, rule_v))
            continue
        if human_v:
            if relaxed:
                n_match_relaxed += 1
            else:
                mismatches.append((row["task_id"], model, "human=yes but relaxed(all causes) still False", strict, relaxed))
        else:
            if not relaxed:
                n_match_relaxed += 1
            else:
                mismatches.append((row["task_id"], model, "human=no but relaxed(all causes) now True (OVER-RELAXED)", strict, relaxed))

    print(f"checked {n_total} rows; relaxed-matches-human: {n_match_relaxed}/{n_total}")
    if mismatches:
        print("MISMATCHES:")
        for m in mismatches:
            print(" ", m)
    else:
        print("ALL CLEAR: relaxed_compatible(all causes) agrees with human_verdict on all 40 rows.")


if __name__ == "__main__":
    main()
