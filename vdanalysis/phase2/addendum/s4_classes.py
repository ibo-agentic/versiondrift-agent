"""S4: factor classification, fixed in ANALYSIS_ADDENDUM_plan-v2.1.md before any Phase 2 result was seen.

"reasonable" = documented reasonable choice; "misconfiguration" = misconfiguration / compound change.
Headline flip rates use the reasonable set only; all factors are still reported. The source for each class is in
the addendum table (kept there, not copied here, so the two cannot drift apart).
"""

from __future__ import annotations

REASONABLE = "reasonable"
MISCONFIG = "misconfiguration_or_compound"

FACTOR_CLASS = {
    "F1": REASONABLE, "F2": REASONABLE, "F3": REASONABLE, "F4": REASONABLE, "F5": REASONABLE, "F6": REASONABLE,
    "F7": REASONABLE, "F8": REASONABLE, "F9": REASONABLE, "F10": REASONABLE,
    "F11": MISCONFIG,
}
GENERATION_FACTORS = ("F1", "F2", "F3", "F4", "F5", "F6", "F11")      # factors that need new generations (Holm family, S1)
RESCORING_FACTORS = ("F7", "F8", "F9")                                # same generations; rerun baseline is 0 (S1.3)
ESTIMATOR_FACTORS = ("F10",)                                          # changes the estimator, not the generations


def reasonable_set(factors) -> list[str]:
    return [f for f in factors if FACTOR_CLASS.get(f) == REASONABLE]


def headline_flip_rate(flips: list[dict], factors: list[str]) -> dict:
    """Share of decisions that flip under >=1 factor of ``factors`` (P1-style, ``flips`` = pipeline flip table rows)."""
    sel = [r for r in flips if r["factor"] in factors]
    decisions = {(r["pair"], r["suite"]) for r in sel}
    flipped = {(r["pair"], r["suite"]) for r in sel if r["flipped"]}
    return {"factors": ",".join(factors), "n_decisions": len(decisions), "n_flipped": len(flipped),
            "share": (len(flipped) / len(decisions)) if decisions else float("nan")}
