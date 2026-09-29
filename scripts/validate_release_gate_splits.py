"""Leave-one-upgrade-out validation of the release gate.

Question: does a canary task set selected from one upgrade pair (training)
detect the outcome of a different upgrade pair (held-out test)?

Selection (training pair only): rank tasks by |pooled stress difference|
(schema_drift + runtime_fault, task-level mean over trials), then pick top-k
with a coverage pass that first takes the highest-|diff| task introducing an
uncovered drift/fault category. The held-out pair's full-suite stress
difference is the ground truth; classification: harmful < -0.05,
beneficial > +0.05, else neutral. The same rule applied to the canary
subset's difference on the TEST pair is the prediction.

Also evaluates RANDOM subsets of the same size on the test pair as a
baseline, so "does selection help?" is answered against chance.

Usage:
    python scripts/validate_release_gate_splits.py RUN_DIR [RUN_DIR ...]

With no arguments, the three itlwas matched-trial runs are used.
"""

from __future__ import annotations

import json
import os
import random
import sys

KS = [10, 20, 30, 40]
GATE_THRESHOLD = 0.05
STRESS = ("schema_drift", "runtime_fault")
RANDOM_SUBSETS = 200
RANDOM_SEED = 20240930

DEFAULT_RUNS = [
    r"results\upgradecanary-real-trials-itlwas-v0.1_seed1234_20260929T120210Z",
    r"results\upgradecanary-real-trials-itlwas-v0.2_seed1234_20260929T121701Z",
    r"results\upgradecanary-real-trials-itlwas-v0.3_seed1234_20260929T132749Z",
]


def load_run(run_dir: str) -> dict:
    for name in ("parsed_results_corrected.jsonl", "parsed_results.jsonl"):
        path = os.path.join(run_dir, name)
        if os.path.exists(path):
            recs = {}
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    p = json.loads(line)
                    key = (
                        p["task_id"],
                        p["condition"],
                        (p["drift"] or {}).get("type"),
                        (p["fault"] or {}).get("type"),
                        p.get("trial_index", 0),
                    )
                    recs[key] = p
            print(f"[loaded {len(recs)} records from {run_dir} ({name})]")
            return recs
    raise FileNotFoundError(f"no parsed results found in {run_dir}")


def functional(m: dict) -> float:
    return (
        1.0
        if (m["parse_ok"] and m["tool_name_ok"] and m["args_intent_match"]
            and m["args_valid_under_drift"] and m["executor_ok"])
        else 0.0
    )


def sc(rec: dict) -> float:
    return functional(rec["metrics"])


def gate_label(diff: float) -> str:
    if diff < -GATE_THRESHOLD:
        return "harmful"
    if diff > GATE_THRESHOLD:
        return "beneficial"
    return "neutral"


def subset_diff(recs_a: dict, recs_b: dict, keys: list) -> float:
    return sum(sc(recs_b[k]) - sc(recs_a[k]) for k in keys) / len(keys)


def select_canary(ranked: list, categories: dict, k: int) -> list:
    """Top-k by training |diff| with category coverage where possible."""
    selected: list = []
    covered: set = set()
    for t in ranked:  # coverage pass
        if len(selected) >= k:
            break
        if categories[t] - covered:
            selected.append(t)
            covered |= categories[t]
    for t in ranked:  # fill pass
        if len(selected) >= k:
            break
        if t not in selected:
            selected.append(t)
    return selected


def main(argv: list[str]) -> None:
    dirs = argv[1:] or DEFAULT_RUNS
    if len(dirs) != 3:
        sys.exit("expected exactly three run directories (two upgrade pairs)")
    runs = [
        (os.path.basename(d).split("_seed")[0].replace("upgradecanary-", ""), load_run(d))
        for d in dirs
    ]
    common = sorted(set.intersection(*(set(r) for _, r in runs)))
    task_ids = sorted({k[0] for k in common})
    stress_keys = [k for k in common if k[1] in STRESS]
    by_task = {t: [k for k in stress_keys if k[0] == t] for t in task_ids}
    categories = {
        t: {k[2] for k in ks if k[1] == "schema_drift"}
        | {k[3] for k in ks if k[1] == "runtime_fault"}
        for t, ks in by_task.items()
    }
    print(f"\nmatched: {len(common)} records, {len(stress_keys)} stress, {len(task_ids)} tasks")

    pairs = [(0, 1), (1, 2)]  # upgrade pairs by position

    for train_idx, test_idx in ((0, 1), (1, 0)):
        ta_name, ra = runs[pairs[train_idx][0]]
        tb_name, rb = runs[pairs[train_idx][1]]
        tc_name, rc = runs[pairs[test_idx][0]]
        td_name, rd = runs[pairs[test_idx][1]]
        train_pair = f"{ta_name}->{tb_name}"
        test_pair = f"{tc_name}->{td_name}"

        train_diff = {t: subset_diff(ra, rb, by_task[t]) for t in task_ids}
        ranked = sorted(task_ids, key=lambda t: abs(train_diff[t]), reverse=True)
        test_full = subset_diff(rc, rd, stress_keys)
        test_truth = gate_label(test_full)
        print(f"\n=== train on {train_pair} | test on {test_pair} ===")
        print(f"test full-suite stress diff = {test_full:+.3f} -> truth: {test_truth}")
        print(f"top-20 training tasks: {ranked[:20]}")

        for k in KS:
            canary = select_canary(ranked, categories, k)
            keys = [key for t in canary for key in by_task[t]]
            d = subset_diff(rc, rd, keys)
            pred = gate_label(d)
            correct = pred == test_truth
            sign_ok = (d > 0) == (test_full > 0)
            fa = test_truth == "harmful" and pred != "harmful"
            fr = test_truth == "beneficial" and pred != "beneficial"

            rng = random.Random(f"{RANDOM_SEED}-{train_pair}-{k}")
            rand_diffs = []
            rand_correct = 0
            for _ in range(RANDOM_SUBSETS):
                sub = rng.sample(task_ids, k)
                sk = [key for t in sub for key in by_task[t]]
                r_diff = subset_diff(rc, rd, sk)
                rand_diffs.append(r_diff)
                rand_correct += gate_label(r_diff) == test_truth
            rand_diffs.sort()
            pct = sum(1 for x in rand_diffs if abs(x) <= abs(d)) / len(rand_diffs)
            rand_acc = rand_correct / RANDOM_SUBSETS
            print(
                f"  k={k:2d}: canary diff={d:+.3f} pred={pred:<10} correct={correct} "
                f"signMatch={sign_ok} FA={fa} FR={fr} | random acc={rand_acc:.3f} "
                f"|diff| percentile vs random={pct:.2f}"
            )

    print("\n=== cross-pair overlap of top-20 informative tasks ===")
    top_sets = []
    for i, j in pairs:
        ra, rb = runs[i][1], runs[j][1]
        d = {t: subset_diff(ra, rb, by_task[t]) for t in task_ids}
        top = set(sorted(task_ids, key=lambda t: abs(d[t]), reverse=True)[:20])
        top_sets.append(top)
        print(f"{runs[i][0]}->{runs[j][0]}: {sorted(top)}")
    inter = top_sets[0] & top_sets[1]
    print(f"overlap: {len(inter)}/20 -> {sorted(inter)}")


if __name__ == "__main__":
    main(sys.argv)
