"""Release-gate simulation: can a small canary task subset predict full-suite
upgrade outcomes for a local LLM?

Uses existing repeated-trial runs (no model execution). Records are matched on
(task_id, condition, drift type, fault type, trial_index) across runs, then
consecutive run pairs are treated as upgrade pairs (A -> B).

For each upgrade pair the full-suite stress difference (schema_drift +
runtime_fault, pooled over tasks x trials) is the ground truth, labelled:
  harmful     if diff < -GATE_THRESHOLD
  beneficial  if diff > +GATE_THRESHOLD
  neutral     otherwise
The same labelling applied to a sampled task subset is the gate prediction.

For subset sizes in SUBSET_SIZES, SUBSETS_PER_SIZE deterministic subsets are
sampled (seeded) and evaluated for accuracy, false-accept rate (harmful truth
not flagged), false-reject rate (beneficial truth not flagged), sign agreement,
and mean absolute deviation from the full-suite difference.

Usage:
    python scripts/analyze_release_gate.py RUN_DIR [RUN_DIR ...]

With no arguments, the three itlwas matched-trial runs are used.
AUROC is not reported: with only two upgrade pairs there is no meaningful
binary class distribution per pair (documented limitation).
"""

from __future__ import annotations

import json
import os
import random
import sys

SUBSET_SIZES = [10, 20, 30, 40, 50]
SUBSETS_PER_SIZE = 200
GATE_THRESHOLD = 0.05
STRESS_CONDITIONS = ("schema_drift", "runtime_fault")
SAMPLING_SEED = 20240929

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


def functional(metrics: dict) -> float:
    return (
        1.0
        if (
            metrics["parse_ok"]
            and metrics["tool_name_ok"]
            and metrics["args_intent_match"]
            and metrics["args_valid_under_drift"]
            and metrics["executor_ok"]
        )
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


def mean_diff(recs_a: dict, recs_b: dict, keys: list) -> float:
    return sum(sc(recs_b[k]) - sc(recs_a[k]) for k in keys) / len(keys)


def main(argv: list[str]) -> None:
    dirs = argv[1:] or DEFAULT_RUNS
    if len(dirs) < 2:
        sys.exit("need at least two run directories")
    runs = [
        (os.path.basename(d).split("_seed")[0].replace("upgradecanary-", ""), load_run(d))
        for d in dirs
    ]
    common = sorted(set.intersection(*(set(r) for _, r in runs)))
    task_ids = sorted({k[0] for k in common})
    stress_keys = [k for k in common if k[1] in STRESS_CONDITIONS]
    print(f"\nmatched records: {len(common)}; stress records: {len(stress_keys)}; tasks: {len(task_ids)}")
    print(f"gate thresholds: harmful < {-GATE_THRESHOLD}, beneficial > +{GATE_THRESHOLD}")

    results = {}
    for i in range(len(runs) - 1):
        (na, ra) = runs[i]
        nb_name, rb = runs[i + 1]
        pair = f"{na}->{nb_name}"
        by_task = {t: [k for k in stress_keys if k[0] == t] for t in task_ids}
        full_diff = mean_diff(ra, rb, stress_keys)
        truth = gate_label(full_diff)
        print(f"\n=== {pair}: full-suite stress diff = {full_diff:+.3f} -> truth: {truth} ===")

        for size in SUBSET_SIZES:
            rng = random.Random(f"{SAMPLING_SEED}-{pair}-{size}")
            n_correct = n_fa = n_fr = n_sign = 0
            mae = 0.0
            for _ in range(SUBSETS_PER_SIZE):
                subset = rng.sample(task_ids, size)
                keys = [k for t in subset for k in by_task[t]]
                d = mean_diff(ra, rb, keys)
                pred = gate_label(d)
                n_correct += pred == truth
                if truth == "harmful" and pred != "harmful":
                    n_fa += 1
                if truth == "beneficial" and pred != "beneficial":
                    n_fr += 1
                n_sign += (d > 0) == (full_diff > 0)
                mae += abs(d - full_diff)
            n = SUBSETS_PER_SIZE
            results[(pair, size)] = {
                "accuracy": n_correct / n,
                "false_accept": n_fa / n,
                "false_reject": n_fr / n,
                "sign_match": n_sign / n,
                "mae": mae / n,
            }
            r = results[(pair, size)]
            print(
                f"  size={size:3d}: accuracy={r['accuracy']:.3f} falseAccept={r['false_accept']:.3f} "
                f"falseReject={r['false_reject']:.3f} signMatch={r['sign_match']:.3f} MAE={r['mae']:.3f}"
            )

        # Informativeness: per-task and per-type effect sizes on the full set.
        per_task = sorted(
            ((t, mean_diff(ra, rb, by_task[t])) for t in task_ids),
            key=lambda x: abs(x[1]),
            reverse=True,
        )
        print("  top tasks by |stress diff|: " + ", ".join(f"{t}:{d:+.2f}" for t, d in per_task[:8]))
        print("  effect by category (full set):")
        for cond, types in (
            ("schema_drift", ["field_rename", "field_drop", "type_mutation", "unexpected_field", "enum_drift"]),
            ("runtime_fault", ["timeout", "tool_exception", "empty_result", "stale_result", "partial_result"]),
        ):
            for ty in types:
                idx = 2 if cond == "schema_drift" else 3
                keys = [k for k in stress_keys if k[1] == cond and k[idx] == ty]
                if keys:
                    d = mean_diff(ra, rb, keys)
                    flag = gate_label(d)
                    print(f"    {cond}/{ty}: {d:+.3f} ({flag})")

    print("\n=== TRADEOFF SUMMARY (min size with accuracy >= 0.95 on every pair) ===")
    best = None
    for size in SUBSET_SIZES:
        accs = [results[(p, size)]["accuracy"] for p in
                [f"{runs[i][0]}->{runs[i+1][0]}" for i in range(len(runs) - 1)]]
        ok = all(a >= 0.95 for a in accs)
        print(f"size={size:3d}: min pair-accuracy={min(accs):.3f} {'OK' if ok else 'below target'}")
        if ok and best is None:
            best = size
    print(f"recommended canary size: {best if best is not None else '>= max tested'}")
    print("\nNote: AUROC is not defined here — only two upgrade pairs exist, so there is")
    print("no per-pair binary class distribution; accuracy / sign-match are reported instead.")


if __name__ == "__main__":
    main(sys.argv)
