"""Per-task arrays behind every addendum analysis.

A decision (upgrade pair x suite) under a protocol is reduced to, for every task and stress condition,
the sum of (new - old) strict scores over the matched records and the number of matched records. This is
exactly the information ``vdanalysis.stats.compare`` uses, so the stress diff computed from these arrays
equals the pipeline's (tests check it), and a task-level bootstrap is a matrix product.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CODE = {"harmful": -1, "neutral": 0, "beneficial": 1}
NAME = {v: k for k, v in CODE.items()}


@dataclass
class TaskArrays:
    tasks: list[str]
    conds: list[str]
    S: np.ndarray                      # (T, C) sum of new - old over matched records
    N: np.ndarray                      # (T, C) number of matched records

    @property
    def n_tasks(self) -> int:
        return len(self.tasks)

    def diff(self) -> float:
        return float(boot_diff(np.ones((1, self.n_tasks)), self)[0])


def make_arrays(old, new, conditions, tasks=None) -> TaskArrays | None:
    """``old``/``new`` are loader ``Run`` objects (``.keys``: (task, condition, drift, fault, trial) -> (score, bucket))."""
    keys = [k for k in set(old.keys) & set(new.keys) if k[1] in conditions]
    if not keys:
        return None
    conds = sorted({k[1] for k in keys})
    tl = sorted(tasks) if tasks is not None else sorted({k[0] for k in keys})
    ti = {t: i for i, t in enumerate(tl)}
    ci = {c: i for i, c in enumerate(conds)}
    S = np.zeros((len(tl), len(conds)))
    N = np.zeros_like(S)
    for k in keys:
        i = ti.get(k[0])
        if i is None:
            continue
        S[i, ci[k[1]]] += new.keys[k][0] - old.keys[k][0]
        N[i, ci[k[1]]] += 1
    return TaskArrays(tl, conds, S, N)


def boot_diff(M: np.ndarray, a: TaskArrays) -> np.ndarray:
    """Stress diff of each resample. ``M`` (K, T) = how often each task is drawn. Equal-weight average over
    the conditions that have records in the resample (as in ``vdanalysis.stats.bootstrap_ci``)."""
    num = M @ a.S
    den = M @ a.N
    ok = den > 0
    r = np.where(ok, num / np.where(ok, den, 1.0), 0.0)
    cnt = ok.sum(axis=1)
    return np.where(cnt > 0, r.sum(axis=1) / np.maximum(cnt, 1), 0.0)


def point_code(diff: np.ndarray, delta: float) -> np.ndarray:
    """Point gate (PLAN.md section 4): -1 harmful, 0 neutral, +1 beneficial."""
    return np.where(diff < -delta, -1, np.where(diff > delta, 1, 0))


def draw_counts(rng: np.random.Generator, n_tasks: int, size: int) -> np.ndarray:
    """``size`` bootstrap resamples of ``n_tasks`` tasks, as (size, n_tasks) draw counts."""
    return rng.multinomial(n_tasks, np.full(n_tasks, 1.0 / n_tasks), size=size)


def item_outcomes(old, new, conditions) -> dict[tuple, tuple[float, float]]:
    """(task, condition) -> (old mean score, new mean score) over the trials both runs have (S7 collapses
    each of these to one binary outcome per model)."""
    acc: dict[tuple, list] = {}
    for k in set(old.keys) & set(new.keys):
        if k[1] not in conditions:
            continue
        a = acc.setdefault((k[0], k[1]), [0.0, 0.0, 0])
        a[0] += old.keys[k][0]
        a[1] += new.keys[k][0]
        a[2] += 1
    return {k: (v[0] / v[2], v[1] / v[2]) for k, v in acc.items()}


def trial_matrix(old, new, conditions, tasks=None) -> tuple[list[str], list[int], np.ndarray]:
    """Per-task, per-trial stress diff: rows = tasks, columns = trial indices. For each trial the diff is the
    equal-weight mean over the stress conditions with a matched record for that task. NaN where none."""
    keys = [k for k in set(old.keys) & set(new.keys) if k[1] in conditions]
    tl = sorted(tasks) if tasks is not None else sorted({k[0] for k in keys})
    trials = sorted({k[4] for k in keys})
    ti = {t: i for i, t in enumerate(tl)}
    tr = {t: j for j, t in enumerate(trials)}
    conds = sorted(conditions)
    ci = {c: i for i, c in enumerate(conds)}
    sums = np.zeros((len(tl), len(trials), len(conds)))
    cnt = np.zeros_like(sums)
    for k in keys:
        i = ti.get(k[0])
        if i is None:
            continue
        sums[i, tr[k[4]], ci[k[1]]] += new.keys[k][0] - old.keys[k][0]
        cnt[i, tr[k[4]], ci[k[1]]] += 1
    ok = cnt > 0
    per = np.where(ok, sums / np.where(ok, cnt, 1.0), 0.0)
    n = ok.sum(axis=2)
    y = np.where(n > 0, per.sum(axis=2) / np.maximum(n, 1), np.nan)
    return tl, trials, y


def cluster_arrays(a: TaskArrays, groups: dict[str, str]) -> TaskArrays:
    """Merge tasks that share a group label (here: the same baseline prompt) into one resampling unit: S and N are
    summed over the group's tasks, so a cluster bootstrap is the same matrix product over clusters. Tasks without a
    label stay their own cluster."""
    keys = [groups.get(t) or f"__task__{t}" for t in a.tasks]
    names = sorted(set(keys))
    idx = {k: i for i, k in enumerate(names)}
    S = np.zeros((len(names), a.S.shape[1]))
    N = np.zeros_like(S)
    for r, k in enumerate(keys):
        S[idx[k]] += a.S[r]
        N[idx[k]] += a.N[r]
    return TaskArrays(names, a.conds, S, N)
