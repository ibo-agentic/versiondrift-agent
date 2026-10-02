"""AUDIT question K/24: per-condition (clean/drift/fault) gap + bootstrap CI,
per upgrade pair, per suite -- checks whether ranking/sign is consistent
across conditions or driven by one condition.

Read-only. Reuses the task-level cluster bootstrap convention from
scripts/analyze_version_trials.py (resample task IDs with replacement,
10000 reps, seed 1234, percentile 95% CI).
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import UPGRADE_PAIRS, load_parsed, sc  # noqa: E402

BOOTSTRAP_REPS = 10000
BOOTSTRAP_SEED = 1234
CONDITIONS = ["baseline", "schema_drift", "runtime_fault"]


def mean_diff(ra: dict, rb: dict, keys: list) -> float:
    return sum(sc(rb[k]) - sc(ra[k]) for k in keys) / len(keys)


def cluster_ci(ra: dict, rb: dict, keys: list, rng: random.Random) -> tuple:
    task_ids = sorted({k[0] for k in keys})
    by_task = {t: [k for k in keys if k[0] == t] for t in task_ids}
    diffs = []
    for _ in range(BOOTSTRAP_REPS):
        picked = [task_ids[rng.randrange(len(task_ids))] for _ in task_ids]
        ks = [k for t in picked for k in by_task[t]]
        diffs.append(mean_diff(ra, rb, ks))
    diffs.sort()
    return diffs[250], diffs[9749]


def main() -> None:
    for suite in ("synthetic", "BFCL"):
        print(f"\n=== {suite}: per-condition gap + 95% CI, per upgrade pair ===")
        rng = random.Random(BOOTSTRAP_SEED)
        for model_a, model_b in UPGRADE_PAIRS:
            ra = load_parsed(suite, model_a)
            rb = load_parsed(suite, model_b)
            common = sorted(set(ra) & set(rb))
            print(f"\n  {model_a} -> {model_b}")
            signs = []
            for cond in CONDITIONS:
                keys = [k for k in common if k[1] == cond]
                d = mean_diff(ra, rb, keys)
                lo, hi = cluster_ci(ra, rb, keys, rng)
                sig = "significant" if (lo > 0 or hi < 0) else "n.s."
                signs.append((cond, d, lo, hi, sig))
                print(f"    {cond:14}: diff={d:+.3f}  CI=[{lo:+.3f}, {hi:+.3f}]  {sig}")
            base_sign = signs[0][1] > 0
            drift_sign = signs[1][1] > 0
            fault_sign = signs[2][1] > 0
            agree = "ALL SAME SIGN" if (base_sign == drift_sign == fault_sign) else "SIGNS DISAGREE"
            print(f"    -> baseline/drift/fault sign agreement: {agree}")


if __name__ == "__main__":
    main()
