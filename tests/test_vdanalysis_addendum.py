"""Tests for vdanalysis/phase2/addendum (ANALYSIS_ADDENDUM_plan-v2.1.md S1-S9).

Fixture data only. The numeric functions are checked against hand-computed values; the driver is run on the Phase 1
FAKE study of tests/fake_study.py (known answers).
"""

import copy
import math
from types import SimpleNamespace

import numpy as np
import pytest

from tests.fake_study import build_fake_results
from vdanalysis.phase2.addendum import DELTA
from vdanalysis.phase2.addendum.data import (TaskArrays, boot_diff, draw_counts, item_outcomes, make_arrays, point_code,
                                             trial_matrix)
from vdanalysis.phase2.addendum.s1_noise import (S1Input, expected_noise_share, hier_bootstrap, holm, observed,
                                                 per_decision_flip_prob, rerun_rate, summarize)
from vdanalysis.phase2.addendum.s2_types import BOUNDARY, SIGN, count_types, flip_type, split_rows
from vdanalysis.phase2.addendum.s3_fourclass import class_share, classify, interval
from vdanalysis.phase2.addendum.s4_classes import (FACTOR_CLASS, GENERATION_FACTORS, MISCONFIG, headline_flip_rate,
                                                   reasonable_set)
from vdanalysis.phase2.addendum.s5_failures import classify as fail_class
from vdanalysis.phase2.addendum.s5_failures import flip_changes, shares_from_records, stress_share
from vdanalysis.phase2.addendum.s6_power import mde, power_at, project_variance, variance_components
from vdanalysis.phase2.addendum.s7_mcnemar import exact_mcnemar_p, mcnemar_decision
from vdanalysis.phase2.addendum.s8_reference import agreement


def arrays(per_task_diff, n_cond=1):
    """Arrays with one record per task and condition: the per-task diff is the task's (new - old) score."""
    d = np.asarray(per_task_diff, dtype=float)
    S = np.tile(d[:, None], (1, n_cond))
    return TaskArrays([f"t{i:03d}" for i in range(len(d))], [f"c{j}" for j in range(n_cond)], S, np.ones_like(S))


# ------------------------------------------------------------------ data
def test_diff_matches_pipeline_compare():
    from vdanalysis.loader import Run
    from vdanalysis.stats import compare

    rng = np.random.default_rng(3)
    old, new = Run("D", "o", "s", None), Run("D", "n", "s", None)
    for t in range(30):
        for c in ("schema_drift", "fault_reporting"):
            for tr in range(3):
                k = (f"t{t:02d}", c, "x", "y", tr)
                old.keys[k] = (float(rng.random() < 0.8), None)
                new.keys[k] = (float(rng.random() < 0.6), None)
    cmp = compare(old, new, ("schema_drift", "fault_reporting"), 0.05, 100, 1, with_ci=False)
    a = make_arrays(old, new, ("schema_drift", "fault_reporting"))
    assert a.diff() == pytest.approx(cmp.diff, abs=1e-12)
    assert a.n_tasks == 30 and a.N.sum() == 180


def test_boot_diff_handles_empty_condition_like_legacy():
    a = TaskArrays(["a", "b"], ["c1", "c2"], np.array([[1.0, 0.0], [0.0, 0.0]]), np.array([[1.0, 0.0], [1.0, 0.0]]))
    M = np.array([[2, 0], [0, 2]])
    d = boot_diff(M, a)
    assert d[0] == pytest.approx(1.0) and d[1] == pytest.approx(0.0)       # c2 has no records in any resample: dropped


def test_point_code_and_trial_matrix_and_items():
    assert list(point_code(np.array([-0.06, -0.05, 0.0, 0.05, 0.0501]), 0.05)) == [-1, 0, 0, 0, 1]
    from vdanalysis.loader import Run

    old, new = Run("D", "o", "s", None), Run("D", "n", "s", None)
    for t in ("a", "b"):
        for tr, (so, sn) in enumerate([(1, 0), (1, 1), (0, 1)]):
            for c in ("schema_drift", "fault_reporting"):
                old.keys[(t, c, "x", "y", tr)] = (float(so), None)
                new.keys[(t, c, "x", "y", tr)] = (float(sn), None)
    tl, trials, y = trial_matrix(old, new, ("schema_drift", "fault_reporting"))
    assert tl == ["a", "b"] and trials == [0, 1, 2] and y.shape == (2, 3)
    assert list(y[0]) == [-1.0, 0.0, 1.0]
    items = item_outcomes(old, new, ("schema_drift", "fault_reporting"))
    assert items[("a", "schema_drift")] == (pytest.approx(2 / 3), pytest.approx(2 / 3))


# ------------------------------------------------------------------ S2
def test_flip_types():
    assert flip_type("harmful", "beneficial") == SIGN and flip_type("beneficial", "harmful") == SIGN
    assert flip_type("neutral", "harmful") == BOUNDARY and flip_type("harmful", "neutral") == BOUNDARY
    assert flip_type("neutral", "inconclusive") == BOUNDARY and flip_type("inconclusive", "harmful") == BOUNDARY
    assert flip_type("neutral", "neutral") is None
    c = count_types([("harmful", "beneficial"), ("neutral", "harmful"), ("neutral", "neutral")])
    assert c == {"n_decisions": 3, "n_flips": 2, SIGN: 1, BOUNDARY: 1}


def test_split_rows_separates_the_pair():
    rows = [{"factor": "F1", "pair": "qwen25->qwen3", "a": "harmful", "b": "beneficial"},
            {"factor": "F1", "pair": "x->y", "a": "neutral", "b": "harmful"},
            {"factor": "F1", "pair": "z->w", "a": "neutral", "b": "neutral"}]
    out = {r["subset"]: r for r in split_rows(rows, "a", "b", ("factor",), "qwen25->qwen3")}
    assert out["all"]["n_flips"] == 2 and out["only_pair"][SIGN] == 1 and out["excluding_pair"][BOUNDARY] == 1


# ------------------------------------------------------------------ S1
def test_holm_and_expected_share_and_cp():
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj["a"] == pytest.approx(0.03) and adj["c"] == pytest.approx(0.06) and adj["b"] == pytest.approx(0.06)
    assert expected_noise_share([0.1, 0.0], [2, 3]) == pytest.approx(0.095)
    r = rerun_rate(_inp(rerun_same=True), "x")
    assert r["n_rerun_flips"] == 0 and r["cp95_hi"] == pytest.approx(1 - 0.025 ** (1 / r["n_decisions"]), abs=1e-6)


def _inp(factor_shift=-0.3, rerun_same=True, n_pairs=4, n_tasks=60):
    """Decisions where the baseline is neutral (diff 0), the rerun arm equals the baseline (or is as harmful as the
    factor arm), and the factor arm is harmful (shift)."""
    rng = np.random.default_rng(11)
    pairs = [f"p{i}->q{i}" for i in range(n_pairs)]
    suites = ["s1"]
    arr = {}
    for p in pairs:
        base = rng.choice([-1.0, 0.0, 1.0], size=n_tasks, p=[0.05, 0.9, 0.05])
        arr[(p, "s1", "D")] = arrays(base)
        arr[(p, "s1", "D_AA2")] = arrays(base if rerun_same else base + factor_shift)
        arr[(p, "s1", "F1")] = arrays(base + factor_shift)
    cells = {"F1": [(p, "s1", "F1", "D") for p in pairs]}
    return S1Input(pairs, suites, arr, ("D", "D_AA2"), cells)


def test_s1_excess_flip_when_rerun_is_quiet():
    inp = _inp(rerun_same=True)
    ob = observed(inp)
    assert ob["rerun"]["k"] == 0 and ob["factors"]["F1"]["k_factor"] == 4
    boot = hier_bootstrap(inp, reps=400, seed=1)
    row = summarize(inp, boot)[0]
    assert row["f_F"] == 1.0 and row["r_on_same_decisions"] == 0.0 and row["e_F"] == 1.0
    assert row["e_F_ci95_lo"] > 0.2 and row["p_one_sided_e_gt_0"] < 0.02


def test_s1_no_excess_when_rerun_is_as_bad_as_the_factor():
    inp = _inp(rerun_same=False)
    boot = hier_bootstrap(inp, reps=400, seed=1)
    row = summarize(inp, boot)[0]
    assert row["e_F"] == 0.0 and row["p_one_sided_e_gt_0"] > 0.5


def test_s1_exclusion_and_determinism():
    inp = _inp()
    a = hier_bootstrap(inp, reps=200, seed=5)
    b = hier_bootstrap(inp, reps=200, seed=5)
    assert np.array_equal(a["factors"]["F1"]["e"], b["factors"]["F1"]["e"], equal_nan=True)
    c = hier_bootstrap(inp, reps=200, seed=5, exclude_pairs=("p0->q0",))
    assert c["pairs"] == ["p1->q1", "p2->q2", "p3->q3"]


def test_per_decision_flip_prob_zero_for_identical_arms():
    a = arrays(np.zeros(50))
    assert per_decision_flip_prob(a, arrays(np.zeros(50)), reps=200, seed=1) == 0.0
    near = arrays(np.r_[np.full(25, 0.1), np.full(25, 0.0)])         # diff 0.05 exactly: the point gate is neutral
    shifted = arrays(np.r_[np.full(25, 0.1), np.full(25, 0.02)])
    p = per_decision_flip_prob(near, shifted, reps=500, seed=1)
    assert 0.0 < p < 1.0


# ------------------------------------------------------------------ S3
def test_classify_four_classes():
    assert classify(-0.2, -0.3, -0.1, "harmful") == "harmful"
    assert classify(0.2, 0.1, 0.3, "beneficial") == "beneficial"
    assert classify(0.01, -0.03, 0.04, "neutral") == "neutral"           # 90% interval inside +-0.05
    assert classify(0.01, -0.06, 0.04, "neutral") == "inconclusive"       # wide interval
    assert classify(-0.055, -0.07, 0.01, "neutral") == "inconclusive"     # beyond the margin but CI includes 0
    sh = class_share(["harmful", "neutral", "neutral", "inconclusive"])
    assert sh["neutral"] == 0.5 and sh["beneficial"] == 0.0


def test_interval_width_shrinks_with_tasks():
    rng = np.random.default_rng(2)
    small = arrays(rng.choice([-1.0, 0.0, 1.0], 40, p=[0.1, 0.8, 0.1]))
    big = arrays(rng.choice([-1.0, 0.0, 1.0], 400, p=[0.1, 0.8, 0.1]))
    ws, wb = (lambda lo, hi: hi - lo)(*interval(small, 0.90, 2000, 1)), (lambda lo, hi: hi - lo)(*interval(big, 0.90, 2000, 1))
    assert wb < ws
    lo90, hi90 = interval(big, 0.90, 2000, 1)
    lo95, hi95 = interval(big, 0.95, 2000, 1)
    assert lo95 <= lo90 and hi95 >= hi90


# ------------------------------------------------------------------ S4
def test_factor_classes():
    assert FACTOR_CLASS["F11"] == MISCONFIG
    assert all(FACTOR_CLASS[f] == "reasonable" for f in ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10"))
    assert reasonable_set(["F1", "F11", "F5"]) == ["F1", "F5"]
    assert set(GENERATION_FACTORS) == {"F1", "F2", "F3", "F4", "F5", "F6", "F11"}
    flips = [{"factor": "F1", "pair": "a", "suite": "s", "flipped": True}, {"factor": "F11", "pair": "b", "suite": "s", "flipped": True},
             {"factor": "F1", "pair": "b", "suite": "s", "flipped": False}]
    assert headline_flip_rate(flips, ["F1"])["share"] == 0.5
    assert headline_flip_rate(flips, ["F1", "F11"])["share"] == 1.0


# ------------------------------------------------------------------ S5
def test_failure_categories_first_failing_check():
    ok = {"score": 1.0}
    assert fail_class("schema_drift", ok) is None
    assert fail_class("schema_drift", {"score": 0.0, "parse_ok": False}) == "malformed_unparsed"
    assert fail_class("schema_drift", {"score": 0.0, "parse_ok": True, "tool_name_ok": False}) == "wrong_tool_name"
    assert fail_class("schema_drift", {"score": 0.0, "parse_ok": True, "tool_name_ok": True, "args_intent_match": False}) == "wrong_or_invalid_args"
    assert fail_class("schema_drift", {"score": 0.0, "parse_ok": True, "tool_name_ok": True, "args_intent_match": True,
                                       "args_valid_under_drift": True, "executor_ok": False}) == "executor_fail"
    assert fail_class("fault_reporting", {"score": 0.0, "parse_ok": True, "status_ok": False}) == "wrong_status"
    assert fail_class("fault_reporting", {"score": 0.0, "parse_ok": True, "status_ok": True, "no_fabrication": False}) == "fabricated_answer"


def test_shares_and_flip_changes():
    recs = [("schema_drift", {"score": 1.0}), ("schema_drift", {"score": 0.0, "parse_ok": False}),
            ("fault_reporting", {"score": 0.0, "parse_ok": True, "status_ok": False}), ("fault_reporting", {"score": 1.0})]
    pc = shares_from_records(recs)
    assert pc["schema_drift"]["malformed_unparsed"] == 0.5 and pc["fault_reporting"]["wrong_status"] == 0.5
    st = stress_share(pc)
    assert st["malformed_unparsed"] == 0.25 and st["wrong_status"] == 0.25 and st["fail_total"] == 0.5
    zero = {k: 0.0 for k in st}
    worse = dict(zero, malformed_unparsed=0.2, fail_total=0.2)
    d = flip_changes(zero, zero, zero, worse)
    assert d["malformed_unparsed"] == pytest.approx(0.2) and d["fail_total"] == pytest.approx(0.2)
    d2 = flip_changes(zero, worse, zero, worse)
    assert d2["malformed_unparsed"] == 0.0


# ------------------------------------------------------------------ S6
def test_mde_and_power_known_values():
    assert mde(0.25, 100) == pytest.approx(2.801585 * 0.025, rel=1e-6)
    assert power_at(mde(0.25, 100), 0.25, 100) == pytest.approx(0.80, abs=0.002)
    assert power_at(0.0, 0.25, 100) == pytest.approx(0.05, abs=1e-4)
    assert mde(0.25, 400) == pytest.approx(mde(0.25, 100) / 2)


def test_variance_components_recover_known_parts_and_project():
    rng = np.random.default_rng(0)
    n, sb, ss = 20000, 0.20, 0.30                                         # between-task SD, sampling SD
    mu = rng.normal(0, sb, n)
    y = np.column_stack([mu] + [mu + rng.normal(0, ss, n) for _ in range(2)])      # greedy trial = mu (no noise)
    comp = variance_components(y, greedy_col=0)
    assert comp["sigma2_sampling"] == pytest.approx(ss ** 2, rel=0.05)
    assert comp["B_between_from_all_trials"] == pytest.approx(sb ** 2, rel=0.08)
    assert comp["B_between_from_sampled_trials"] == pytest.approx(sb ** 2, rel=0.08)
    v10 = project_variance(sb ** 2, ss ** 2, 10)
    assert v10 == pytest.approx(sb ** 2 + 0.09 * ss ** 2)
    assert project_variance(sb ** 2, ss ** 2, 3) == pytest.approx(sb ** 2 + (2 / 9) * ss ** 2)
    assert project_variance(-1.0, 0.04, 10) == pytest.approx(0.09 * 0.04)             # negative between-variance is clipped


# ------------------------------------------------------------------ S7
def test_exact_mcnemar_known_values():
    assert exact_mcnemar_p(10, 0) == pytest.approx(2 * 0.5 ** 10)
    assert exact_mcnemar_p(5, 5) == 1.0 and exact_mcnemar_p(0, 0) == 1.0
    assert exact_mcnemar_p(3, 12) == pytest.approx(2 * (1 + 15 + 105 + 455) / 2 ** 15)
    assert exact_mcnemar_p(12, 3) == exact_mcnemar_p(3, 12)


def test_mcnemar_decision_labels():
    harm = {(f"t{i}", "c"): (1.0, 0.0) for i in range(12)}
    harm.update({(f"u{i}", "c"): (1.0, 1.0) for i in range(20)})
    r = mcnemar_decision(harm, -0.2)
    assert r["label"] == "harmful" and r["old_only_success"] == 12 and r["p_exact_two_sided"] < 0.001
    assert mcnemar_decision(harm, -0.04)["label"] == "neutral"              # significant but inside the margin
    ben = {(f"t{i}", "c"): (0.0, 1.0) for i in range(12)}
    assert mcnemar_decision(ben, 0.2)["label"] == "beneficial"
    few = {("t", "c"): (1.0, 0.0), ("u", "c"): (1.0, 1.0)}
    assert mcnemar_decision(few, -0.3)["label"] == "neutral"                # one discordant item: p = 1
    half = {("t", "c"): (0.5, 0.0)}
    assert mcnemar_decision(half, -0.3)["old_only_success"] == 1            # mean score 0.5 counts as success


# ------------------------------------------------------------------ S8
def test_reference_agreement():
    ref = {("a", "s1"): "neutral", ("a", "s2"): "harmful", ("b", "s1"): "neutral"}
    others = {"D": {("a", "s1"): "neutral", ("a", "s2"): "neutral", ("b", "s1"): "neutral"}, "F1": {("a", "s1"): "neutral"}}
    rows = {r["protocol"]: r for r in agreement(ref, others)}
    assert rows["D"]["n_agree"] == 2 and rows["D"]["n_compared"] == 3 and "a/s2" in rows["D"]["disagree"]
    assert rows["F1"]["share"] == 1.0


def test_cluster_arrays_merges_tasks_sharing_a_prompt():
    from vdanalysis.phase2.addendum.data import TaskArrays, cluster_arrays

    a = TaskArrays(["t1", "t2", "t3"], ["c1", "c2"], np.array([[1., 0.], [1., 1.], [-1., 0.]]), np.array([[2., 2.], [2., 2.], [2., 2.]]))
    c = cluster_arrays(a, {"t1": "P", "t2": "P"})              # t3 has no label: stays alone
    assert c.n_tasks == 2 and c.S.sum() == a.S.sum() and c.N.sum() == a.N.sum()
    assert abs(c.diff() - a.diff()) < 1e-12                   # clustering changes resampling units, not the point estimate
    assert sorted(c.N[:, 0]) == [2.0, 4.0]


# ------------------------------------------------------------------ S9
def _sim_s9(n_task=40, n_pair=6, beta=(0.0, 0.2, -0.3, 0.8, -0.2), seed=3):
    rng = np.random.default_rng(seed)
    rows = {k: [] for k in ("y", "new", "proto", "cond", "task", "pair")}
    ut = rng.normal(0, 0.8, n_task)
    up = rng.normal(0, 0.4, n_pair)
    for p in range(n_pair):
        for t in range(n_task):
            for new in (0, 1):
                for proto in (0, 1):
                    for cond in (0, 1):
                        for _ in range(3):
                            eta = beta[0] + beta[1] * new + beta[2] * proto + beta[3] * new * proto + beta[4] * cond + ut[t] + up[p]
                            rows["y"].append(int(rng.random() < 1 / (1 + math.exp(-eta))))
                            rows["new"].append(new); rows["proto"].append(proto); rows["cond"].append(cond)
                            rows["task"].append(f"t{t}"); rows["pair"].append(f"p{p}")
    return rows


def test_s9_recovers_a_known_interaction_and_is_seeded():
    from vdanalysis.phase2.addendum.s9_hierarchical import fit

    d = _sim_s9()
    r1 = fit(d["y"], d["new"], d["proto"], d["cond"], d["task"], d["pair"], seed=1234)
    r2 = fit(d["y"], d["new"], d["proto"], d["cond"], d["task"], d["pair"], seed=1234)
    assert r1["coef_new_x_protocol_mean"] == r2["coef_new_x_protocol_mean"]
    assert abs(r1["coef_new_x_protocol_mean"] - 0.8) < 0.3 and r1["coef_new_x_protocol_sd"] > 0
    assert r1["n_tasks"] == 40 and r1["n_pairs"] == 6 and r1["n_records"] == len(d["y"])
    nul = _sim_s9(beta=(0.0, 0.2, -0.3, 0.0, -0.2), seed=4)
    r0 = fit(nul["y"], nul["new"], nul["proto"], nul["cond"], nul["task"], nul["pair"])
    assert abs(r0["coef_new_x_protocol_mean"]) < 0.3


def test_s9_sign_agrees_rules():
    from vdanalysis.phase2.addendum.s9_hierarchical import sign_agrees

    assert sign_agrees(0.4, 0.02) is True and sign_agrees(-0.4, 0.02) is False
    assert sign_agrees(0.4, 0.0) is None and sign_agrees(0.0, 0.1) is None and sign_agrees(float("nan"), 0.1) is None


def _fake_run(records):
    return SimpleNamespace(keys={k: (v, "b") for k, v in records.items()})


def test_s9_stack_duplicates_shared_models_and_rejects_non_binary():
    from vdanalysis.phase2.addendum.s9_hierarchical import stack_records

    m = {  # model b is "new" in pair 1 and "old" in pair 2
        "a": _fake_run({("t1", "schema_drift", "x", "y", 0): 1}), "b": _fake_run({("t1", "schema_drift", "x", "y", 0): 0}),
        "c": _fake_run({("t1", "schema_drift", "x", "y", 0): 1, ("t1", "baseline", "x", "y", 0): 1}),
    }
    runs = {"p1": {"D": (m["a"], m["b"]), "R": (m["a"], m["b"])}, "p2": {"D": (m["b"], m["c"]), "R": (m["b"], m["c"])}}
    cols = stack_records(runs, "R", {"schema_drift"})
    assert len(cols["y"]) == 8                       # 2 pairs x 2 protocols x 2 models, baseline record skipped
    assert sum(1 for p, n in zip(cols["pair"], cols["new"]) if p == "p1" and n == 1) == 2
    assert sum(1 for p, n in zip(cols["pair"], cols["new"]) if p == "p2" and n == 0) == 2   # b again, now as old
    bad = {"p1": {"D": (_fake_run({("t", "schema_drift", "x", "y", 0): 0.5}),) * 2, "R": (m["a"], m["b"])}}
    with pytest.raises(ValueError):
        stack_records(bad, "R", {"schema_drift"})


# ------------------------------------------------------------------ driver on the fake Phase 1 study
@pytest.fixture(scope="module")
def fake_run(tmp_path_factory):
    from vdanalysis.phase2.addendum.run_addendum import run_addendum
    from vdanalysis.phase2.config import Phase2Config

    root = tmp_path_factory.mktemp("fake_results")
    raw = build_fake_results(root)
    p1 = copy.deepcopy(raw)
    p1["phase2"] = {"mode": "phase1", "n_trials": 3, "seed_base": 1234, "default_parts": [{"root": "auto", "require_prompts": False}]}
    out = tmp_path_factory.mktemp("addendum_out")
    res = run_addendum(Phase2Config(p1, base_dir=root), out, reruns=[], reps=300, seed=1234)
    return res, out


def test_driver_writes_tables_and_known_classes(fake_run):
    res, out = fake_run
    for name in ("s3_classes", "s3_shares", "s4_headline", "s5_shares", "s6_projection", "s7_decisions", "s7_agreement", "meta"):
        assert (out / f"{name}.csv").exists() or (out / f"{name}.json").exists(), name
    cls = {(r["pair"], r["suite"]): r["class4"] for r in res["s3_classes"] if r["protocol"] == "D"}
    assert cls[("h_old->h_new", "s1")] == "harmful"        # -0.30
    assert cls[("n_old->n_new", "s1")] == "neutral"        # 0.00, 20 tasks of zeros: 90% interval is a point at 0
    assert cls[("b_old->b_new", "s1")] == "beneficial"      # +0.40
    rows = {(r["pair"], r["suite"]): r for r in res["s7_decisions"] if r["protocol"] == "D"}
    assert rows[("h_old->h_new", "s1")]["label"] == "harmful"
    assert rows[("n_old->n_new", "s1")]["p_exact_two_sided"] == 1.0


def test_driver_s5_and_s6_on_fake(fake_run):
    res, _ = fake_run
    assert res["s5_shares"] and all(set(r) >= {"protocol", "model", "suite", "condition", "n"} for r in res["s5_shares"])
    assert res["s6_components"] and res["s6_projection"]
    assert all(math.isfinite(r["mde_80"]) for r in res["s6_projection"])
    assert "s3_cluster_synthetic" in res and "s3_cluster_synthetic_summary" in res      # (empty: fake suites are not "synthetic")
    assert "s9_interaction" in res and "s9_skipped" in res      # fake study has no complete generation-side protocol


def test_driver_refuses_protected_output_folders(tmp_path):
    from vdanalysis.phase2.run_phase2 import assert_safe_output_dir_p2

    with pytest.raises(ValueError):
        assert_safe_output_dir_p2(tmp_path / "results_v3" / "addendum")


def test_driver_s1_end_to_end_with_a_silent_rerun_arm(tmp_path_factory):
    """Rerun arm = D against itself (no flips possible): the excess equals the factor flip rate, S2/S3 tables exist."""
    from vdanalysis.phase2.addendum.run_addendum import run_addendum
    from vdanalysis.phase2.config import Phase2Config

    root = tmp_path_factory.mktemp("fake_results_s1")
    raw = build_fake_results(root)
    p1 = copy.deepcopy(raw)
    p1["phase2"] = {"mode": "phase1", "n_trials": 3, "seed_base": 1234, "default_parts": [{"root": "auto", "require_prompts": False}]}
    out = tmp_path_factory.mktemp("addendum_out_s1")
    res = run_addendum(Phase2Config(p1, base_dir=root), out, reruns=[("D", "D")], reps=200, seed=1234, sections=("s1", "s3"))
    rr = res["s1_rerun_rates"][0]
    assert rr["n_rerun_flips"] == 0 and rr["n_decisions"] > 0
    rows = {r["factor"]: r for r in res["s1_factors"]}
    assert rows["F1"]["k_factor_flips"] >= 1 and rows["F1"]["k_rerun_flips"] == 0
    assert rows["F1"]["e_F"] == pytest.approx(rows["F1"]["f_F"])
    assert all(0.0 <= r["p_holm"] <= 1.0 for r in res["s1_factors"] if not math.isnan(r["p_holm"]))
    assert res["s1_factors_excl_qwen25_qwen3"] and res["s2_factor_flips"] and res["s3_factor_flips"]
    assert (out / "s1_factors.csv").exists() and (out / "s1_per_decision.csv").exists()
    assert res["s1_headline"][0]["n_decisions_with_rerun"] > 0
