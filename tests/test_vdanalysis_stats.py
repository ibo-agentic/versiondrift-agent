"""Gate/bootstrap math on tiny hand-made data (no files, no models)."""

import random

import pytest

from upgradecanary.gates import cluster_bootstrap_ci, point_gate
from vdanalysis.loader import Run
from vdanalysis.stats import bootstrap_ci, compare


def _run(scores: dict, name="m") -> Run:
    r = Run("D", name, "s", path=None)
    for k, v in scores.items():
        r.keys[k] = (float(v), None if v else "semantic")
    return r


def test_fast_bootstrap_matches_repo_gate_implementation():
    rng = random.Random(7)
    tasks = [f"t{i:02d}" for i in range(25)]
    per_task = {t: [rng.choice([-2, -1, 0, 0, 1, 2]), 6] for t in tasks}
    diff_fn = lambda picked: sum(per_task[t][0] for t in picked) / sum(per_task[t][1] for t in picked)
    ref = cluster_bootstrap_ci(sorted(tasks), diff_fn, reps=10000, seed=1234)
    mine = bootstrap_ci([tuple(per_task[t]) for t in sorted(tasks)], reps=10000, seed=1234)
    assert mine == ref


def test_point_gate_boundary_is_neutral():
    assert point_gate(-0.05) == "neutral"
    assert point_gate(0.05) == "neutral"
    assert point_gate(-0.0501) == "harmful"
    assert point_gate(0.0501) == "beneficial"


def test_compare_on_the_line_is_neutral_and_exact():
    # 20 tasks x 6 stress records; new loses exactly one task's 6 records = -6/120.
    keys = [(f"t{t}", "schema_drift", None, None, i) for t in range(20) for i in range(6)]
    old = _run({k: 1 for k in keys})
    new = _run({k: (0 if k[0] == "t0" else 1) for k in keys})
    c = compare(old, new, ["schema_drift"], 0.05, 1000, 1234)
    assert c.diff == -0.05
    assert c.label_point == "neutral" and c.label_ci == "neutral"
    assert (c.neg, c.pos) == (6, 0)


def test_compare_uses_only_matched_keys_and_requested_conditions():
    a = _run({("t0", "schema_drift", None, None, 0): 1, ("t1", "schema_drift", None, None, 0): 1,
              ("t0", "baseline", None, None, 0): 1})
    b = _run({("t0", "schema_drift", None, None, 0): 0, ("t0", "baseline", None, None, 0): 0})
    c = compare(a, b, ["schema_drift"], 0.05, 100, 1234)
    assert c.n_records == 1 and c.diff == -1.0
    assert c.n_old == 3 and c.n_new == 2


def test_ci_gate_needs_ci_clear_of_zero():
    # Two tasks carry all the loss: point harmful, CI includes 0 -> neutral.
    keys = [(f"t{t}", "schema_drift", None, None, i) for t in range(20) for i in range(6)]
    old = _run({k: 1 for k in keys})
    fail = {("t0", 0), ("t0", 1), ("t0", 2), ("t0", 3), ("t0", 4), ("t0", 5), ("t1", 0)}
    new = _run({k: (0 if (k[0], k[4]) in fail else 1) for k in keys})
    c = compare(old, new, ["schema_drift"], 0.05, 10000, 1234)
    assert c.label_point == "harmful"
    assert c.ci_hi >= 0 and c.label_ci == "neutral"


@pytest.mark.parametrize("seed", [1234])
def test_bootstrap_deterministic(seed):
    pt = [(-1.0, 6), (0.0, 6), (2.0, 6)]
    assert bootstrap_ci(pt, 500, seed) == bootstrap_ci(pt, 500, seed)


def test_stress_diff_is_equal_weight_average_even_with_unequal_record_counts():
    # schema_drift: 10 records, new loses 5 -> -0.5. fault_reporting: 2 records, new loses 0 -> 0.
    # equal weight = -0.25 (pooled would be -5/12 = -0.4167).
    keys = [(f"t{i}", "schema_drift", None, None, 0) for i in range(10)]
    fk = [(f"t{i}", "fault_reporting", None, None, 0) for i in range(2)]
    old = _run({k: 1 for k in keys + fk})
    new = _run({k: (0 if k in keys[:5] else 1) for k in keys + fk})
    c = compare(old, new, ["schema_drift", "fault_reporting"], 0.05, 200, 1234)
    assert c.diff == pytest.approx(-0.25)
    assert c.mean_old == 1.0 and c.mean_new == pytest.approx(0.75)


def test_bootstrap_two_conditions_matches_single_when_identical():
    pt = [(-1.0, 6), (0.0, 6), (2.0, 6), (-2.0, 6)]
    two = [[x, x] for x in pt]
    assert bootstrap_ci(two, 500, 1234) == bootstrap_ci(pt, 500, 1234)
