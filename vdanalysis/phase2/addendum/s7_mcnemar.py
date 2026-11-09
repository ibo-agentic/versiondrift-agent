"""S7: McNemar gate (secondary).

Item = (task, stress condition). Each item is collapsed to one binary outcome per model: success if the mean
strict score over trials is >= 0.5. Exact two-sided McNemar test (binomial test of the discordant pairs) on the old
versus the new model per decision. Label: harmful / beneficial if p < 0.05 and the point stress diff is beyond
-delta / +delta, else neutral.
"""

from __future__ import annotations

import math

from . import DELTA


def exact_mcnemar_p(n_old_only: int, n_new_only: int) -> float:
    """Two-sided exact p-value: 2 * P(X <= min) for X ~ Binomial(n, 0.5), n = number of discordant items; 1 if n = 0."""
    n = n_old_only + n_new_only
    if n == 0:
        return 1.0
    k = min(n_old_only, n_new_only)
    tail = math.fsum(math.comb(n, i) for i in range(k + 1)) / 2.0 ** n
    return min(1.0, 2.0 * tail)


def mcnemar_decision(items: dict[tuple, tuple[float, float]], point_diff: float, delta: float = DELTA, alpha: float = 0.05) -> dict:
    """``items``: (task, condition) -> (old mean score, new mean score), see ``data.item_outcomes``."""
    n_old_only = n_new_only = n_both = n_none = 0
    for old, new in items.values():
        so, sn = old >= 0.5, new >= 0.5
        if so and not sn:
            n_old_only += 1
        elif sn and not so:
            n_new_only += 1
        elif so and sn:
            n_both += 1
        else:
            n_none += 1
    p = exact_mcnemar_p(n_old_only, n_new_only)
    if p < alpha and point_diff < -delta:
        label = "harmful"
    elif p < alpha and point_diff > delta:
        label = "beneficial"
    else:
        label = "neutral"
    return {"n_items": len(items), "old_only_success": n_old_only, "new_only_success": n_new_only,
            "both_success": n_both, "both_fail": n_none, "p_exact_two_sided": p, "label": label}
