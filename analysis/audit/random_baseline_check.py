"""AUDIT questions J/20 and J/23.

J/20 (circularity check): documents, by code reference, whether the published
gate-accuracy "selected" canary numbers (tables/gate_accuracy.csv) use any
decision's own ground truth during selection. See AUDIT.md section J for the
code citations (scripts/analyze_gate_threshold_sensitivity.py selects by
cross-pair leave-one-out informativeness; scripts/validate_release_gate_splits.py
selects strictly from a disjoint training pair). This script does not need to
recompute that -- it is a code-reading answer.

J/23: no existing script reports a 1000-repetition random-subset verdict-match
rate at a single fixed size (k=30) per upgrade pair, stated as "how often does
the random subset give the same harmful/neutral/beneficial verdict as the full
suite". scripts/analyze_release_gate.py and scripts/validate_release_gate_splits.py
use 200 reps per size across multiple sizes. This script computes exactly what
the reviewer asked: 1000 random 30-task subsets per upgrade pair, per suite,
verdict-match rate against the full-suite (gate_threshold=0.05) ground truth.
Read-only; reuses the exact subset-sampling and gate-threshold convention of
scripts/analyze_release_gate.py (GATE_THRESHOLD=0.05, STRESS=(schema_drift,
runtime_fault), random.Random seeded per (pair, size) for reproducibility).
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import UPGRADE_PAIRS, load_parsed, sc  # noqa: E402

GATE_THRESHOLD = 0.05
STRESS = ("schema_drift", "runtime_fault")
N_REPS = 1000
K = 30
SEED = 20261002  # audit-specific seed, documented here; does not touch existing seeds


def gate_label(d: float) -> str:
    if d < -GATE_THRESHOLD:
        return "harmful"
    if d > GATE_THRESHOLD:
        return "beneficial"
    return "neutral"


def mean_diff(ra: dict, rb: dict, keys: list) -> float:
    return sum(sc(rb[k]) - sc(ra[k]) for k in keys) / len(keys)


def main() -> None:
    for suite in ("synthetic", "BFCL"):
        print(f"\n=== {suite}: 1000x random 30-task subset verdict match vs full-suite truth ===")
        for model_a, model_b in UPGRADE_PAIRS:
            ra = load_parsed(suite, model_a)
            rb = load_parsed(suite, model_b)
            common = sorted(set(ra) & set(rb))
            task_ids = sorted({k[0] for k in common})
            stress_keys = [k for k in common if k[1] in STRESS]
            by_task = {t: [k for k in stress_keys if k[0] == t] for t in task_ids}
            full_diff = mean_diff(ra, rb, stress_keys)
            truth = gate_label(full_diff)

            rng = random.Random(f"{SEED}-{suite}-{model_a}-{model_b}-{K}")
            match = 0
            label_counts = {"harmful": 0, "beneficial": 0, "neutral": 0}
            for _ in range(N_REPS):
                subset = rng.sample(task_ids, K)
                keys = [k for t in subset for k in by_task[t]]
                d = mean_diff(ra, rb, keys)
                pred = gate_label(d)
                label_counts[pred] += 1
                if pred == truth:
                    match += 1
            print(
                f"  {model_a} -> {model_b}: full_diff={full_diff:+.3f} truth={truth:<10} "
                f"match_rate={match/N_REPS:.3f} "
                f"(pred dist: harmful={label_counts['harmful']/N_REPS:.2f} "
                f"beneficial={label_counts['beneficial']/N_REPS:.2f} "
                f"neutral={label_counts['neutral']/N_REPS:.2f})"
            )


if __name__ == "__main__":
    main()
