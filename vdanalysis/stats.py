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


def bootstrap_ci(per_task, reps: int, seed: int) -> tuple[float, float]:
    """per_task, ordered by sorted task id. Each item is either (diff_sum, count)
    for one condition, or a sequence of such pairs, one per condition. The
    resampled statistic is the equal-weight average over conditions of each
    condition's pooled diff (sum / count), so it reduces to the plain pooled
    diff for a single condition."""
    n = len(per_task)
    if n == 0:
        return float("nan"), float("nan")
    items = [[tuple(x)] if len(x) == 2 and not hasattr(x[0], "__len__") else [tuple(c) for c in x]
             for x in per_task]
    k = len(items[0])
    sums = [[it[c][0] for it in items] for c in range(k)]
    cnts = [[it[c][1] for it in items] for c in range(k)]
    rng = random.Random(seed)
    rr = rng.randrange
    diffs = []
    for _ in range(reps):
        idx = [rr(n) for _ in range(n)]
        parts = []
        for c in range(k):
            cnt = sum(cnts[c][i] for i in idx)
            if cnt:  # a condition absent from this resample drops out of its average
                parts.append(sum(sums[c][i] for i in idx) / cnt)
        diffs.append(sum(parts) / len(parts) if parts else 0.0)
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
    """Every mean/diff is the equal-weight average over the requested
    conditions of that condition's own paired mean (DECISION 2026-10-08:
    stress diff = average of the schema_drift and fault_reporting diffs).
    neg/pos are raw record counts."""
    keys = sorted(k for k in set(old.keys) & set(new.keys) if k[1] in conditions)
    if not keys:
        return None
    conds = sorted({k[1] for k in keys})
    per = {c: {"n": 0, "so": 0.0, "sn": 0.0, "fo": 0, "fn": 0, "mo": 0, "mn": 0} for c in conds}
    by_task: dict[str, dict[str, list]] = {}
    neg = pos = 0
    for k in keys:
        a, ab = old.keys[k]
        b, bb = new.keys[k]
        d = per[k[1]]
        d["n"] += 1
        d["so"] += a
        d["sn"] += b
        d["fo"] += ab == "format"
        d["fn"] += bb == "format"
        d["mo"] += ab == "semantic"
        d["mn"] += bb == "semantic"
        neg += a == 1.0 and b == 0.0
        pos += a == 0.0 and b == 1.0
        t = by_task.setdefault(k[0], {c: [0.0, 0] for c in conds})[k[1]]
        t[0] += b - a
        t[1] += 1

    def avg(fn):
        return sum(fn(d) for d in per.values()) / len(per)

    diff = avg(lambda d: (d["sn"] - d["so"]) / d["n"])
    lo = hi = label_ci = None
    if with_ci:
        # tasks with no records in a condition contribute (0, 0) there
        lo, hi = bootstrap_ci([[tuple(by_task[t][c]) for c in conds] for t in sorted(by_task)], reps, seed)
        label_ci = ci_gate(diff, lo, hi, threshold)
    return Comparison(
        n_records=len(keys), n_tasks=len(by_task), n_old=len(old), n_new=len(new),
        mean_old=avg(lambda d: d["so"] / d["n"]), mean_new=avg(lambda d: d["sn"] / d["n"]), diff=diff,
        ci_lo=lo, ci_hi=hi, label_point=point_gate(diff, threshold), label_ci=label_ci,
        neg=int(neg), pos=int(pos),
        fmt_diff=avg(lambda d: (d["fn"] - d["fo"]) / d["n"]), sem_diff=avg(lambda d: (d["mn"] - d["mo"]) / d["n"]),
    )
