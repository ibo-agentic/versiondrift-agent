"""S3: four-class verdict (secondary gate).

delta = 0.05. Intervals from the task-clustered bootstrap within the decision (B = 10,000, seed 1234).
  harmful      point < -delta and the 95% upper bound < 0   (the pre-registered CI gate)
  beneficial   mirror image
  neutral      the 90% interval lies entirely inside [-delta, +delta]   (TOST at alpha = 0.05)
  inconclusive everything else

The harmful / beneficial calls are taken from the pipeline's own CI gate (``label_ci``, the legacy bootstrap), so
they are exactly the pre-registered ones; only the 90% interval needs a new bootstrap (``interval90``).
"""

from __future__ import annotations

import numpy as np

from . import BOOT_REPS, BOOT_SEED, DELTA
from .data import TaskArrays, boot_diff, draw_counts

CLASSES = ("harmful", "beneficial", "neutral", "inconclusive")


def interval(a: TaskArrays, level: float, reps: int = BOOT_REPS, seed: int = BOOT_SEED) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    d = boot_diff(draw_counts(rng, a.n_tasks, reps), a)
    q = (1 - level) / 2
    return float(np.quantile(d, q)), float(np.quantile(d, 1 - q))


def classify(point: float, lo90: float, hi90: float, label_ci: str, delta: float = DELTA) -> str:
    if label_ci in ("harmful", "beneficial"):
        return label_ci
    if lo90 >= -delta and hi90 <= delta:
        return "neutral"
    return "inconclusive"


def class_share(classes: list[str]) -> dict[str, float]:
    n = len(classes)
    return {c: (classes.count(c) / n if n else float("nan")) for c in CLASSES}
