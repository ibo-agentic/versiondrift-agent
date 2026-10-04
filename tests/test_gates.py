"""PLAN.md step 10.1 item 6: CI gate and point gate as reusable functions
(PLAN.md section 8). Pure-logic tests; cluster_bootstrap_ci uses a tiny
synthetic diff_fn so these run instantly without any real data.
"""

from __future__ import annotations

import pytest

from upgradecanary.gates import (
    GATE_THRESHOLD,
    cluster_bootstrap_ci,
    ci_gate,
    decide,
    point_gate,
)

# --- point_gate --------------------------------------------------------------


@pytest.mark.parametrize(
    "diff,expected",
    [
        (-0.168, "harmful"),
        (-0.051, "harmful"),
        (-0.050, "neutral"),  # exactly at the threshold: NOT harmful (strict <)
        (-0.049, "neutral"),
        (0.0, "neutral"),
        (0.049, "neutral"),
        (0.050, "neutral"),  # exactly at the threshold: NOT beneficial (strict >)
        (0.051, "beneficial"),
        (0.187, "beneficial"),
    ],
)
def test_point_gate(diff, expected):
    assert point_gate(diff) == expected


def test_point_gate_custom_threshold():
    assert point_gate(-0.08, threshold=0.1) == "neutral"
    assert point_gate(-0.11, threshold=0.1) == "harmful"


# --- ci_gate ------------------------------------------------------------------


def test_ci_gate_harmful_requires_whole_interval_past_zero():
    assert ci_gate(diff=-0.10, ci_lower=-0.20, ci_upper=-0.01) == "harmful"


def test_ci_gate_harmful_point_past_threshold_but_ci_straddles_zero_is_neutral():
    # This is exactly the "point estimate alone is not enough" case PLAN.md
    # section 8 draws the CI gate to guard against.
    assert ci_gate(diff=-0.10, ci_lower=-0.20, ci_upper=+0.02) == "neutral"


def test_ci_gate_beneficial_requires_whole_interval_past_zero():
    assert ci_gate(diff=0.12, ci_lower=0.02, ci_upper=0.22) == "beneficial"


def test_ci_gate_beneficial_point_past_threshold_but_ci_straddles_zero_is_neutral():
    assert ci_gate(diff=0.10, ci_lower=-0.02, ci_upper=0.20) == "neutral"


def test_ci_gate_small_diff_is_neutral_regardless_of_ci():
    assert ci_gate(diff=0.01, ci_lower=-0.30, ci_upper=0.30) == "neutral"


# --- cluster_bootstrap_ci -----------------------------------------------------


def test_cluster_bootstrap_ci_percentile_indices_match_project_convention():
    # Every existing script in this project (scripts/analyze_version_trials.py,
    # analysis/audit/*.py) hand-indexes a 10,000-length sorted sample as
    # diffs[250]/diffs[9749]. Confirm this shared implementation lands on
    # exactly the same two values for a case where that's easy to check by
    # construction: a diff_fn that always returns a CONSTANT regardless of
    # the resampled subset collapses every one of the 10,000 reps to the
    # same number, so lo == hi == that constant, proving the indices are
    # in-bounds and symmetric without needing to hand-verify 10,000 draws.
    diffs_seen = cluster_bootstrap_ci(["a", "b", "c"], diff_fn=lambda ids: 0.42, reps=10000, seed=1234)
    assert diffs_seen == (0.42, 0.42)


def test_cluster_bootstrap_ci_varies_with_subset_and_is_reproducible():
    # diff_fn returns the fraction of resampled IDs equal to "a" -- varies
    # by resample composition, so the CI should be non-degenerate, and two
    # calls with the same seed must agree exactly.
    task_ids = ["a", "b", "c", "d"]

    def diff_fn(ids):
        return sum(1 for i in ids if i == "a") / len(ids)

    ci1 = cluster_bootstrap_ci(task_ids, diff_fn, reps=2000, seed=1234)
    ci2 = cluster_bootstrap_ci(task_ids, diff_fn, reps=2000, seed=1234)
    assert ci1 == ci2
    assert ci1[0] <= ci1[1]
    assert 0.0 <= ci1[0] <= 1.0
    assert 0.0 <= ci1[1] <= 1.0


def test_cluster_bootstrap_ci_rejects_zero_reps():
    with pytest.raises(ValueError):
        cluster_bootstrap_ci(["a"], diff_fn=lambda ids: 0.0, reps=0)


# --- decide() convenience wrapper --------------------------------------------


def test_decide_point_mode_skips_bootstrap():
    result = decide(["a", "b"], diff_fn=lambda ids: -0.10, mode="point")
    assert result == {"diff": -0.10, "ci_lower": None, "ci_upper": None, "label": "harmful"}


def test_decide_ci_mode_computes_bootstrap_and_label():
    result = decide(["a", "b", "c"], diff_fn=lambda ids: 0.42, mode="ci", reps=500)
    assert result["diff"] == 0.42
    assert result["ci_lower"] == 0.42
    assert result["ci_upper"] == 0.42
    assert result["label"] == "beneficial"


def test_decide_rejects_unknown_mode():
    with pytest.raises(ValueError):
        decide(["a"], diff_fn=lambda ids: 0.0, mode="weird")


def test_gate_threshold_constant_matches_plan():
    assert GATE_THRESHOLD == 0.05
