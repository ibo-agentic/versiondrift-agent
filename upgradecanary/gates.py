"""Release-gate decision rules (PLAN.md section 8), as reusable functions.

Two gates, both centered on the same +-0.05 threshold (PLAN.md section 4's
default protocol D, and section 8's CI gate):

- ``point_gate``: the simple point-estimate rule D uses by default --
  harmful if diff < -threshold, beneficial if diff > +threshold, else
  neutral. Ignores uncertainty entirely.
- ``ci_gate``: PLAN.md section 8's more conservative rule for R (the robust
  protocol) -- harmful requires BOTH the point diff past the threshold AND
  the whole 95% CI on the harmful side of zero (upper bound < 0);
  beneficial is the mirror image. A point estimate past the threshold with
  a CI that still straddles zero is "neutral/inspect", not a decision.

``cluster_bootstrap_ci`` computes the CI itself: task-level cluster
bootstrap (resample task IDs with replacement, keeping every record of a
resampled task together), 10,000 reps, seed 1234, percentile 95% interval
-- the exact method already used throughout this project's existing
analysis scripts (scripts/analyze_version_trials.py and
analysis/audit/*.py), extracted here as one shared, tested implementation
rather than re-derived ad hoc per script. It is data-shape-agnostic: the
caller supplies ``diff_fn``, a function from a list of task IDs to the
pooled score difference over exactly those tasks' records, so this works
regardless of how a particular script stores its records.
"""

from __future__ import annotations

import random
from typing import Callable

GATE_THRESHOLD = 0.05
BOOTSTRAP_REPS = 10000
BOOTSTRAP_SEED = 1234


def point_gate(diff: float, threshold: float = GATE_THRESHOLD) -> str:
    """PLAN.md section 4 (protocol D's default gate): harmful if
    diff < -threshold, beneficial if diff > +threshold, else neutral."""
    if diff < -threshold:
        return "harmful"
    if diff > threshold:
        return "beneficial"
    return "neutral"


def cluster_bootstrap_ci(
    task_ids: list[str],
    diff_fn: Callable[[list[str]], float],
    reps: int = BOOTSTRAP_REPS,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float]:
    """Task-level cluster bootstrap 95% CI of the pooled diff.

    ``diff_fn(subset_of_task_ids)`` must return the pooled score diff over
    every record belonging to exactly those task IDs (with repeats, if a
    task ID appears more than once in the resample -- i.e. the caller's
    ``diff_fn`` should treat a repeated ID by counting that task's records
    once per repeat, matching the standard cluster-bootstrap definition;
    the simplest correct implementation is to look up each task's records
    from a pre-built per-task index and concatenate across the resampled
    ID list).

    Percentile indices for reps=10000 are the literal [250, 9749] already
    used throughout this project's analysis scripts (2.5th/97.5th
    percentile of a 10,000-length sorted sample); for other ``reps``
    values the equivalent round-to-nearest percentile index is used.
    """
    if reps < 1:
        raise ValueError(f"reps must be >= 1, got {reps}")
    n = len(task_ids)
    rng = random.Random(seed)
    diffs = []
    for _ in range(reps):
        picked = [task_ids[rng.randrange(n)] for _ in range(n)]
        diffs.append(diff_fn(picked))
    diffs.sort()
    lo_idx = round(0.025 * reps)
    hi_idx = round(0.975 * reps) - 1
    lo_idx = max(0, min(lo_idx, reps - 1))
    hi_idx = max(0, min(hi_idx, reps - 1))
    return diffs[lo_idx], diffs[hi_idx]


def ci_gate(diff: float, ci_lower: float, ci_upper: float, threshold: float = GATE_THRESHOLD) -> str:
    """PLAN.md section 8's CI gate: harmful requires diff < -threshold
    AND ci_upper < 0 (the whole interval is on the harmful side of zero);
    beneficial requires diff > +threshold AND ci_lower > 0. Otherwise
    neutral/inspect -- a point estimate alone is never enough."""
    if diff < -threshold and ci_upper < 0:
        return "harmful"
    if diff > threshold and ci_lower > 0:
        return "beneficial"
    return "neutral"


def decide(
    task_ids: list[str],
    diff_fn: Callable[[list[str]], float],
    *,
    mode: str = "point",
    threshold: float = GATE_THRESHOLD,
    reps: int = BOOTSTRAP_REPS,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    """Convenience wrapper: compute the point diff (and, for mode="ci", the
    cluster-bootstrap CI) and return {"diff", "ci_lower", "ci_upper",
    "label"} in one call. ``mode="point"`` skips the bootstrap entirely
    (ci_lower/ci_upper are None) -- useful when only D's cheap default gate
    is needed, not R's more expensive CI gate.
    """
    if mode not in ("point", "ci"):
        raise ValueError(f"mode must be 'point' or 'ci', got {mode!r}")
    diff = diff_fn(task_ids)
    if mode == "point":
        return {"diff": diff, "ci_lower": None, "ci_upper": None, "label": point_gate(diff, threshold)}
    ci_lower, ci_upper = cluster_bootstrap_ci(task_ids, diff_fn, reps=reps, seed=seed)
    return {
        "diff": diff,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "label": ci_gate(diff, ci_lower, ci_upper, threshold),
    }
