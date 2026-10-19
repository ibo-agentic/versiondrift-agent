"""Small exact statistics for Phase 2: Clopper-Pearson intervals and Cohen's kappa.

No SciPy dependency: the binomial tails are summed in log space and the
interval ends are found by bisection, which is exact to ~1e-12 for the
sample sizes used here (tens to a few hundreds).
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Hashable, Sequence


def _log_pmf(k: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if k == n else -math.inf
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + k * math.log(p) + (n - k) * math.log1p(-p))


def _tail_ge(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    return min(1.0, math.fsum(math.exp(_log_pmf(i, n, p)) for i in range(k, n + 1)))


def _tail_le(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p)."""
    return min(1.0, math.fsum(math.exp(_log_pmf(i, n, p)) for i in range(0, k + 1)))


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact two-sided (1 - alpha) confidence interval for a binomial proportion k/n."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= k <= n:
        raise ValueError("k must be between 0 and n")
    a = alpha / 2.0
    lo = 0.0
    if k > 0:
        l, h = 0.0, 1.0           # smallest p with P(X >= k | p) >= a
        for _ in range(200):
            m = (l + h) / 2.0
            if _tail_ge(k, n, m) >= a:
                h = m
            else:
                l = m
        lo = h
    hi = 1.0
    if k < n:
        l, h = 0.0, 1.0           # largest p with P(X <= k | p) >= a
        for _ in range(200):
            m = (l + h) / 2.0
            if _tail_le(k, n, m) >= a:
                l = m
            else:
                h = m
        hi = l
    return lo, hi


def cohen_kappa(a: Sequence[Hashable], b: Sequence[Hashable]) -> float | None:
    """Cohen's kappa for two raters over the same items. None when chance
    agreement is 1 (every item has the same single label for both raters),
    where kappa is undefined."""
    if len(a) != len(b):
        raise ValueError("raters must label the same items")
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[l] * cb[l] for l in set(ca) | set(cb)) / (n * n)
    if pe == 1.0:
        return None
    return (po - pe) / (1.0 - pe)
