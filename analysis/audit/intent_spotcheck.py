"""AUDIT follow-up item 6: export 40 scored schema_drift records (20
intent_match=true, 20 false; spread across drift types, models, suites) for
a human spot-check of the rule-based intent-match metric.

Read-only. Writes analysis/audit/intent_spotcheck.csv with an empty
"human_verdict" column for manual review.
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FINAL_RUNS, REPO_ROOT, load_parsed, load_raw, task_lookup  # noqa: E402

sys.path.insert(0, REPO_ROOT)

SEED = 20261002
PER_CLASS = 20


def main() -> None:
    from upgradecanary.runner import task_base_schema
    from upgradecanary.perturbations.schema_drift import drifted_schema, Drift

    rng = random.Random(SEED)
    tasks_cache: dict[str, dict] = {}
    rows: list[dict] = []

    for suite, model in FINAL_RUNS:
        if suite not in tasks_cache:
            tasks_cache[suite] = task_lookup(suite)
        tasks = tasks_cache[suite]
        recs = load_parsed(suite, model)
        raw = load_raw(suite, model)
        for key, prec in recs.items():
            if prec["condition"] != "schema_drift" or not prec.get("drift"):
                continue
            d = prec["drift"]
            drift = Drift(type=d["type"], tool=d["tool"], field=d["field"], params=d.get("params", {}))
            task = tasks[prec["task_id"]]
            base_schema = task_base_schema(task)
            schema = drifted_schema(base_schema, drift)
            rrow = raw.get((prec["task_id"], prec["condition"], prec["trial_index"]), {})
            intent = bool(prec["metrics"]["args_intent_match"])
            rows.append(
                {
                    "group_key": (intent, suite, model, d["type"]),
                    "suite": suite,
                    "model": model,
                    "task_id": prec["task_id"],
                    "trial_index": prec["trial_index"],
                    "drift_type": d["type"],
                    "intent_match_rule_verdict": intent,
                    "question": task.prompt,
                    "schema_shown_args": json.dumps(schema.get("args", {}), sort_keys=True),
                    "expected_args": json.dumps(task.expected_call.get("arguments", {}), sort_keys=True),
                    "parsed_args": json.dumps((prec.get("parsed_call") or {}).get("arguments"), sort_keys=True),
                    "model_output": (rrow.get("raw_output") or "")[:400],
                }
            )

    by_group: dict[tuple, list[dict]] = {}
    for r in rows:
        by_group.setdefault(r["group_key"], []).append(r)
    for g in by_group.values():
        rng.shuffle(g)

    def sample_class(intent_value: bool, n: int) -> list[dict]:
        class_groups = sorted([k for k in by_group if k[0] == intent_value])
        rng.shuffle(class_groups)
        picked: list[dict] = []
        idx = 0
        guard = 0
        max_guard = 100000
        while len(picked) < n and guard < max_guard:
            guard += 1
            g = class_groups[idx % len(class_groups)]
            pool = by_group[g]
            if pool:
                picked.append(pool.pop())
            idx += 1
            if all(not by_group[k] for k in class_groups):
                break
        return picked

    true_sample = sample_class(True, PER_CLASS)
    false_sample = sample_class(False, PER_CLASS)
    selected = true_sample + false_sample
    rng.shuffle(selected)

    out_path = Path(__file__).parent / "intent_spotcheck.csv"
    fieldnames = [
        "suite", "model", "task_id", "trial_index", "drift_type",
        "question", "schema_shown_args", "expected_args", "parsed_args",
        "model_output", "rule_verdict", "human_verdict",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in selected:
            writer.writerow(
                {
                    "suite": r["suite"],
                    "model": r["model"],
                    "task_id": r["task_id"],
                    "trial_index": r["trial_index"],
                    "drift_type": r["drift_type"],
                    "question": r["question"],
                    "schema_shown_args": r["schema_shown_args"],
                    "expected_args": r["expected_args"],
                    "parsed_args": r["parsed_args"],
                    "model_output": r["model_output"],
                    "rule_verdict": r["intent_match_rule_verdict"],
                    "human_verdict": "",
                }
            )

    print(f"wrote {out_path}: {len(selected)} rows ({len(true_sample)} true / {len(false_sample)} false)")
    print("drift_type spread:", Counter(r["drift_type"] for r in selected))
    print("model spread:", Counter(r["model"] for r in selected))
    print("suite spread:", Counter(r["suite"] for r in selected))


if __name__ == "__main__":
    main()
