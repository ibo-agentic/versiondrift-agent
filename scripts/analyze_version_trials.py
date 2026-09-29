"""Paired repeated-trial analysis across model-version runs.

Usage:
    python scripts/analyze_version_trials.py RUN_DIR [RUN_DIR ...]

For each run directory, loads parsed_results_corrected.jsonl if present,
otherwise parsed_results.jsonl. Records are matched on
(task_id, condition, drift type, fault type, trial_index) across all runs.

Prints per-condition pooled and per-trial functional scores, pairwise
comparison tables (score difference, flips, unchanged counts, task-level
cluster bootstrap 95% CIs), schema_drift / runtime_fault breakdowns per
pair, and per-trial consistency stats.

The functional score is recomputed from the stored component metrics:
parse_ok & tool_name_ok & args_intent_match & args_valid_under_drift &
executor_ok. This keeps the analysis identical even if scoring definitions
change after a run was produced.
"""

from __future__ import annotations

import json
import os
import random
import sys

BOOTSTRAP_REPS = 10000
BOOTSTRAP_SEED = 1234
CONDITIONS = ["baseline", "schema_drift", "runtime_fault"]
DRIFT_TYPES = ["field_rename", "field_drop", "type_mutation", "unexpected_field", "enum_drift"]
FAULT_TYPES = ["timeout", "tool_exception", "empty_result", "stale_result", "partial_result"]


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


def cluster_ci(recs_a: dict, recs_b: dict, keys: list, rng: random.Random) -> tuple:
    """Percentile CI of the pooled score difference, resampling whole tasks."""
    task_ids = sorted({k[0] for k in keys})
    by_task = {t: [k for k in keys if k[0] == t] for t in task_ids}
    diffs = []
    for _ in range(BOOTSTRAP_REPS):
        picked = [task_ids[rng.randrange(len(task_ids))] for _ in task_ids]
        ks = [k for t in picked for k in by_task[t]]
        diffs.append(
            sum(sc(recs_b[k]) for k in ks) / len(ks)
            - sum(sc(recs_a[k]) for k in ks) / len(ks)
        )
    diffs.sort()
    return diffs[250], diffs[9749]


def flip_counts(recs_a: dict, recs_b: dict, keys: list) -> tuple:
    neg = sum(1 for k in keys if sc(recs_a[k]) == 1 and sc(recs_b[k]) == 0)
    pos = sum(1 for k in keys if sc(recs_a[k]) == 0 and sc(recs_b[k]) == 1)
    us = sum(1 for k in keys if sc(recs_a[k]) == 1 and sc(recs_b[k]) == 1)
    uf = sum(1 for k in keys if sc(recs_a[k]) == 0 and sc(recs_b[k]) == 0)
    return neg, pos, us, uf


def main(argv: list[str]) -> None:
    if len(argv) < 3:
        sys.exit("usage: python scripts/analyze_version_trials.py RUN_DIR [RUN_DIR ...]")
    runs = [
        (os.path.basename(d).split("_seed")[0].replace("upgradecanary-", ""), load_run(d))
        for d in argv[1:]
    ]
    common = sorted(set.intersection(*(set(r) for _, r in runs)))
    print(f"\nmatched records across {len(runs)} runs: {len(common)}")

    print("\n=== PER-CONDITION FUNCTIONAL SCORE (pooled | t0/t1/t2) ===")
    for c in CONDITIONS:
        keys = [k for k in common if k[1] == c]
        cells = []
        for name, r in runs:
            pooled = sum(sc(r[k]) for k in keys) / len(keys)
            per_trial = []
            for t in sorted({k[4] for k in keys}):
                tk = [k for k in keys if k[4] == t]
                per_trial.append(f"{sum(sc(r[k]) for k in tk) / len(tk):.2f}")
            cells.append(f"{name}: {pooled:.2f} | {'/'.join(per_trial)}")
        print(f"{c} (n={len(keys)}):  " + "   ".join(cells))

    print("\n=== PAIRWISE PAIRED COMPARISONS (neg = A ok -> B fail; pos = A fail -> B ok) ===")
    rng = random.Random(BOOTSTRAP_SEED)
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            (na, ra), (nb, rb) = runs[i], runs[j]
            print(f"\n--- {na} -> {nb} ---")
            for c in CONDITIONS:
                keys = [k for k in common if k[1] == c]
                neg, pos, us, uf = flip_counts(ra, rb, keys)
                d = sum(sc(rb[k]) - sc(ra[k]) for k in keys) / len(keys)
                lo, hi = cluster_ci(ra, rb, keys, rng)
                print(
                    f"{c}: diff={d:+.3f} neg={neg} pos={pos} "
                    f"unchangedS={us} unchangedF={uf} CI=[{lo:+.3f}, {hi:+.3f}]"
                )
            print("schema_drift by drift type (A->B score, neg/pos):")
            for dt in DRIFT_TYPES:
                keys = [k for k in common if k[1] == "schema_drift" and k[2] == dt]
                if not keys:
                    continue
                neg, pos, _, _ = flip_counts(ra, rb, keys)
                a = sum(sc(ra[k]) for k in keys) / len(keys)
                b = sum(sc(rb[k]) for k in keys) / len(keys)
                print(f"  {dt} (n={len(keys)}): {a:.2f}->{b:.2f} neg={neg} pos={pos}")
            print("runtime_fault by fault type (A->B score, neg/pos):")
            for ft in FAULT_TYPES:
                keys = [k for k in common if k[1] == "runtime_fault" and k[3] == ft]
                if not keys:
                    continue
                neg, pos, _, _ = flip_counts(ra, rb, keys)
                a = sum(sc(ra[k]) for k in keys) / len(keys)
                b = sum(sc(rb[k]) for k in keys) / len(keys)
                print(f"  {ft} (n={len(keys)}): {a:.2f}->{b:.2f} neg={neg} pos={pos}")

    print("\n=== CONSISTENCY (per task x condition unit) ===")
    for name, r in runs:
        units = sorted({(k[0], k[1]) for k in common})
        all_s = all_f = 0
        ranges = []
        for u in units:
            s = [sc(r[k]) for k in common if k[0] == u[0] and k[1] == u[1]]
            ranges.append(max(s) - min(s))
            if sum(s) == len(s):
                all_s += 1
            if sum(s) == 0:
                all_f += 1
        print(
            f"{name}: all-trials-succeed={all_s}/{len(units)}  "
            f"all-trials-fail={all_f}/{len(units)}  mean range={sum(ranges) / len(ranges):.3f}"
        )


if __name__ == "__main__":
    main(sys.argv)
