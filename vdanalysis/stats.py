"""Paired comparison + task-level cluster bootstrap (PLAN.md section 8).

``bootstrap_ci`` draws exactly the same resamples as
upgradecanary.gates.cluster_bootstrap_ci (random.Random(seed), one
randrange(n) per draw over the sorted task ids, percentile indices from the
same formula) but evaluates each resample from per-task sums, so 10,000
reps over hundreds of decisions stays fast. tests/test_vdanalysis_stats.py
checks the two agree.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from upgradecanary.gates import ci_gate, point_gate

from .loader import Run


def bootstrap_ci(per_task: list[tuple[float, int]], reps: int, seed: int) -> tuple[float, float]:
    """per_task: [(sum of score diffs, record count)] ordered by sorted task id."""
    n = len(per_task)
    if n == 0:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    sums = [s for s, _ in per_task]
    cnts = [c for _, c in per_task]
    diffs = []
    rr = rng.randrange
    for _ in range(reps):
        idx = [rr(n) for _ in range(n)]
        diffs.append(sum(sums[i] for i in idx) / sum(cnts[i] for i in idx))
    diffs.sort()
    lo = max(0, min(round(0.025 * reps), reps - 1))
    hi = max(0, min(round(0.975 * reps) - 1, reps - 1))
    return diffs[lo], diffs[hi]


@dataclass
class Comparison:
    n_records: int
    n_tasks: int
    n_old: int
    n_new: int
    mean_old: float
    mean_new: float
    diff: float
    ci_lo: float | None
    ci_hi: float | None
    label_point: str
    label_ci: str | None
    neg: int          # old ok -> new fail (record level)
    pos: int          # old fail -> new ok
    fmt_diff: float   # change in format-failure rate (new - old)
    sem_diff: float   # change in semantic-failure rate (new - old)


def compare(old: Run, new: Run, conditions, threshold: float, reps: int, seed: int,
            with_ci: bool = True) -> Comparison | None:
    keys = sorted(k for k in set(old.keys) & set(new.keys) if k[1] in conditions)
    if not keys:
        return None
    by_task: dict[str, list] = {}
    so = sn = neg = pos = fo = fn = mo = mn = 0
    for k in keys:
        a, ab = old.keys[k]
        b, bb = new.keys[k]
        so += a
        sn += b
        neg += a == 1.0 and b == 0.0
        pos += a == 0.0 and b == 1.0
        fo += ab == "format"
        fn += bb == "format"
        mo += ab == "semantic"
        mn += bb == "semantic"
        t = by_task.setdefault(k[0], [0.0, 0])
        t[0] += b - a
        t[1] += 1
    n = len(keys)
    diff = (sn - so) / n
    lo = hi = label_ci = None
    if with_ci:
        lo, hi = bootstrap_ci([tuple(by_task[t]) for t in sorted(by_task)], reps, seed)
        label_ci = ci_gate(diff, lo, hi, threshold)
    return Comparison(
        n_records=n, n_tasks=len(by_task), n_old=len(old), n_new=len(new),
        mean_old=so / n, mean_new=sn / n, diff=diff, ci_lo=lo, ci_hi=hi,
        label_point=point_gate(diff, threshold), label_ci=label_ci,
        neg=int(neg), pos=int(pos), fmt_diff=(fn - fo) / n, sem_diff=(mn - mo) / n,
    )
