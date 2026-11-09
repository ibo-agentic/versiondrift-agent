"""S8: reference verdict check (small models).

For the decisions where both models have local Q8_0 files (phi3_mini->phi35_mini, phi35_mini->phi4_mini,
gemma2_2b->gemma3_4b; 9 decisions) the F5 (Q8_0) label is the reference. Report how often every other protocol's
label agrees with it. Descriptive only.
"""

from __future__ import annotations

SMALL_PAIRS = ("phi3_mini->phi35_mini", "phi35_mini->phi4_mini", "gemma2_2b->gemma3_4b")


def agreement(reference: dict[tuple, str], others: dict[str, dict[tuple, str]]) -> list[dict]:
    """``reference``: (pair, suite) -> label; ``others``: protocol -> {(pair, suite): label}."""
    rows = []
    for proto, labels in others.items():
        common = [k for k in reference if k in labels]
        agree = sum(labels[k] == reference[k] for k in common)
        rows.append({"protocol": proto, "n_compared": len(common), "n_agree": agree,
                     "share": (agree / len(common)) if common else float("nan"),
                     "disagree": ";".join(f"{k[0]}/{k[1]}:{labels[k]}!={reference[k]}" for k in common if labels[k] != reference[k])})
    return rows
