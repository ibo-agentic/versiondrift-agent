"""End-to-end checks on FAKE results with known answers (tests/fake_study.py).

Everything is written to pytest's tmp dirs; no model, no GPU, no real results.
"""

import copy
import csv

import pytest

from tests.fake_study import build_fake_results, fake_config_dict
from vdanalysis.aggregate import flip_rates
from vdanalysis.config import Config, assert_safe_output_dir
from vdanalysis.controls import control_rows, control_summary
from vdanalysis.engine import Analysis
from vdanalysis.loader import Store
from vdanalysis.run_analysis import run_all
from vdanalysis.studies import qwen3_f4_vs_f2, robust_checks


@pytest.fixture(scope="module")
def study(tmp_path_factory):
    root = tmp_path_factory.mktemp("fake_results")
    cfg = Config(build_fake_results(root))
    out = tmp_path_factory.mktemp("analysis_out")
    res = run_all(cfg, out)
    return cfg, Analysis(cfg), res, out


def D(an, pair, suite="s1"):
    return an.rows("D")[(pair, suite)]


# ---- verdict labels under D ----
@pytest.mark.parametrize("pair,diff,point,ci", [
    ("h_old->h_new", -0.30, "harmful", "harmful"),
    ("n_old->n_new", 0.0, "neutral", "neutral"),
    ("b_old->b_new", 0.40, "beneficial", "beneficial"),
    ("l_old->l_new", -0.05, "neutral", "neutral"),
    ("x_old->x_new", -7 / 120, "harmful", "neutral"),
])
def test_known_labels(study, pair, diff, point, ci):
    _, an, _, _ = study
    for suite in ("s1", "s2"):
        r = D(an, pair, suite)
        assert r["stress_diff"] == pytest.approx(diff)
        assert (r["label_point"], r["label_ci"]) == (point, ci)


def test_line_pair_is_exactly_minus_point_zero_five_and_neutral(study):
    _, an, _, _ = study
    assert D(an, "l_old->l_new")["stress_diff"] == -0.05
    assert D(an, "l_old->l_new")["label_point"] == "neutral"


def test_clean_baseline_flagged_uninformative_at_ceiling(study):
    _, an, _, _ = study
    assert D(an, "h_old->h_new")["clean_uninformative"] is True


def test_record_level_flips_and_failure_split(study):
    _, an, _, _ = study
    r = D(an, "h_old->h_new")
    assert (r["neg_flips"], r["pos_flips"]) == (36, 0)  # 6 tasks x 6 stress records
    assert r["fmt_fail_change"] == pytest.approx(0.15) and r["sem_fail_change"] == pytest.approx(0.15)


# ---- flip counts per factor ----
def flips(study, factor):
    cfg, an, _, _ = study
    return [f for f in an.flip_table() if f["factor"] == factor]


def test_f1_flips_only_harm(study):
    fl = flips(study, "F1")
    assert {f["pair"] for f in fl if f["flipped"]} == {"h_old->h_new"}
    assert len(fl) == 14  # 7 pairs x 2 suites
    h = [f for f in fl if f["flipped"]][0]
    assert (h["d_label"], h["factor_label"]) == ("harmful", "neutral")
    # decomposition: the +0.30 change is half format, half semantic
    assert h["delta_diff"] == pytest.approx(0.30)
    assert h["delta_from_format"] == pytest.approx(0.15) and h["delta_from_semantic"] == pytest.approx(0.15)


def test_f2_only_covers_the_qwen_like_pair(study):
    fl = flips(study, "F2")
    assert {f["pair"] for f in fl} == {"q_old->q_new"} and not any(f["flipped"] for f in fl)


def test_f9_gate_factor_flips_only_the_over_pair(study):
    fl = flips(study, "F9")
    assert {f["pair"] for f in fl if f["flipped"]} == {"x_old->x_new"}


def test_f6_main_number_uses_only_sampling_changed_pairs(study):
    cfg, an, _, _ = study
    rates = {(r["variant"], r["pair_subset"]): r for r in flip_rates(cfg, an.flip_table())
             if r["factor"] == "F6"}
    main = rates[("main", "all_pairs")]
    allp = rates[("all", "all_pairs")]
    assert (main["n_decisions"], main["n_flips"]) == (2, 2)   # only s_old->s_new x 2 suites
    assert (allp["n_decisions"], allp["n_flips"]) == (14, 2)  # all pairs reported too


def test_f4_qwen_like_pair_is_labeled_and_split_out(study):
    cfg, an, _, _ = study
    fl = flips(study, "F4")
    q = [f for f in fl if f["pair"] == "q_old->q_new"]
    assert all(f["confounding"] == "grammar+thinking_blocked" for f in q) and all(f["flipped"] for f in q)
    rates = {(r["variant"], r["pair_subset"]): r for r in flip_rates(cfg, an.flip_table()) if r["factor"] == "F4"}
    assert (rates[("main", "all_pairs")]["n_decisions"], rates[("main", "all_pairs")]["n_flips"]) == (12, 0)
    assert rates[("confounded_only", "all_pairs")]["n_flips"] == 2
    assert rates[("all", "all_pairs")]["n_flips"] == 2


def test_size_changing_pairs_are_tagged_and_reported_separately(study):
    cfg, an, res, _ = study
    assert D(an, "q_old->q_new")["size_changing"] is True
    assert D(an, "h_old->h_new")["size_changing"] is False
    assert {r["pair"] for r in res["tables"]["size_changing_decisions"]} == {"q_old->q_new"}
    sub = {r["pair_subset"] for r in flip_rates(cfg, an.flip_table()) if r["factor"] == "F1"}
    assert sub == {"all_pairs", "size_preserving", "size_changing"}


# ---- Qwen3 F4 vs F2 ----
def test_qwen3_f4_vs_f2_separates_grammar_from_thinking(study):
    _, an, _, _ = study
    rows = {(r["suite"], r["conditions"]): r for r in qwen3_f4_vs_f2(an)}
    r = rows[("s1", "stress")]
    assert r["thinking_off_effect(F2-D)_diff"] == 0.0
    assert r["grammar_plus_thinking_blocked(F4-D)_diff"] == pytest.approx(-0.30)
    assert r["grammar_only_effect(F4-F2)_diff"] == pytest.approx(-0.30)
    assert r["f4_label"] == "grammar+thinking_blocked"


def test_r_protocol_qwen_like_pair_carries_the_same_label(study):
    _, an, _, _ = study
    assert an.rows("R")[("q_old->q_new", "s1")]["confounding"] == "grammar+thinking_blocked"
    assert an.rows("R")[("h_old->h_new", "s1")]["confounding"] == ""


# ---- hypotheses (hand-computed, see tests/fake_study.py) ----
def hyp(study, h, variant):
    return [r for r in study[2]["tables"]["hypotheses"] if r["hypothesis"] == h and r["variant"] == variant][0]


def test_h1_supported_8_of_14(study):
    r = hyp(study, "H1", "main/all_pairs")
    assert (r["n_flipped"], r["n_decisions"], r["supported"]) == (8, 14, True)


def test_h2_not_supported_when_other_factors_flip_more(study):
    r = hyp(study, "H2", "main/all_pairs")
    assert r["value"] == pytest.approx(2 / 28) and r["comparison_value"] == pytest.approx(4 / 20)
    assert r["supported"] is False


def test_h3_median_comparison(study):
    r = hyp(study, "H3", "main/all_pairs")
    assert r["value"] == pytest.approx((0 + 7 / 120) / 2)
    assert r["comparison_value"] == pytest.approx(0.05)
    assert r["supported"] is True


def test_h4_per_factor_primary_uses_only_pairs_where_factor_changed(study):
    # held-out pairs: n, b, q (x2 suites). R is clean everywhere -> 0 disagreement.
    f3 = hyp(study, "H4", "F3/primary")   # F3 changed models n_old,n_new,b_old,b_new -> pairs n,b
    assert (f3["n_decisions"], f3["comparison_n_flipped"], f3["supported"]) == (4, 2, True)
    assert f3["value"] == 0.0 and f3["comparison_value"] == pytest.approx(0.5)
    assert hyp(study, "H4", "F3/all_held_out")["n_decisions"] == 6     # q pair included
    assert hyp(study, "H4", "F3/both_native")["n_decisions"] == 4
    f5 = hyp(study, "H4", "F5/primary")
    assert f5["n_decisions"] == 6 and f5["comparison_n_flipped"] == 0 and f5["supported"] is False  # 0 < 0 is False
    f6 = hyp(study, "H4", "F6/primary")   # only s_new changed; the s pair is design, not held-out
    assert f6["n_decisions"] == 0 and f6["supported"] is None
    assert hyp(study, "H4", "F6/all_held_out")["n_decisions"] == 6


def test_h4_pooled(study):
    p = hyp(study, "H4", "pooled/primary")
    assert (p["n_decisions"], p["comparison_n_flipped"], p["n_flipped"], p["supported"]) == (10, 2, 0, True)


def test_f3_main_flip_count_needs_both_models_native(study):
    cfg, an, _, _ = study
    rates = {(r["variant"], r["pair_subset"]): r for r in flip_rates(cfg, an.flip_table()) if r["factor"] == "F3"}
    assert rates[("main", "all_pairs")]["n_decisions"] == 4      # n and b pairs (x2 suites)
    assert rates[("all", "all_pairs")]["n_decisions"] == 6       # plus h (only h_new native)


def test_h5_not_supported_with_a_false_alarm(study):
    r = hyp(study, "H5", "R_controls")
    assert r["value"] == pytest.approx(0.5) and r["comparison_value"] == 1.0
    assert r["supported"] is False


def test_h5_supported_when_aa_is_clean(study):
    cfg, an, _, _ = study
    raw = copy.deepcopy(cfg.raw)
    raw["controls"][0]["models"] = ["aa_ok"]
    an2 = Analysis(Config(raw), store=an.store)
    s = control_summary(control_rows(an2))
    assert s["false_alarm_rate"] == 0.0 and s["detection_rate"] == 1.0


def test_aa_and_positive_control_labels(study):
    cfg, an, _, _ = study
    by = {(r["old"], r["suite"]): r["label"] for r in control_rows(an)}
    assert by[("aa_ok", "s1")] == "neutral" and by[("aa_bad", "s1")] == "harmful"
    assert by[("pc_a", "s1")] == "harmful" and by[("pc_b", "s2")] == "harmful"


# ---- R checks ----
def test_robust_truncation_flag(study):
    _, an, _, _ = study
    rows = {(r["pair"], r["suite"]): r for r in robust_checks(an)}
    r = rows[("x_old->x_new", "s1")]
    assert r["truncation_new"] == pytest.approx(0.05) and r["truncation_flag_new"] is True
    assert rows[("h_old->h_new", "s1")]["truncation_flag_new"] is False


# ---- official folders ----
def test_override_uses_rerun_and_audit_only_folder_is_refused(study):
    cfg, an, _, _ = study
    store = an.store
    assert store.folder_name("F3", "b_new") == "F3_rerun"
    assert store.folder_name("F3", "n_new") == "F3"
    # b pair stays beneficial under F3 only because the rerun (clean) is used, not the audit-only data
    f3 = an.rows("F3")[("b_old->b_new", "s1")]
    assert f3["label_point"] == "beneficial" and "F3_rerun" in str(store.get("F3", "b_new", "s1").path)
    raw = copy.deepcopy(cfg.raw)
    raw["overrides"] = []
    with pytest.raises(ValueError, match="audit-only"):
        Store(Config(raw)).get("F3", "b_new", "s1")


def test_missing_runs_fail_loudly_unless_allowed(tmp_path):
    cfg_dict = build_fake_results(tmp_path)
    import shutil
    shutil.rmtree(tmp_path / "F1" / "h_new")
    with pytest.raises(FileNotFoundError):
        Analysis(Config(cfg_dict)).rows("F1")
    an = Analysis(Config(cfg_dict), allow_missing=True)
    an.rows("F1")
    assert any("F1/h_new" in m for m in an.missing)


def test_manifest_mismatch_and_record_count_warn(tmp_path):
    cfg_dict = fake_config_dict(tmp_path)
    build_fake_results(tmp_path, cfg_dict)
    cfg_dict["protocols"]["F1"]["expect_manifest"] = {"F1_max_tokens": 4096}
    cfg_dict["expected_records_per_run"] = 900
    store = Store(Config(cfg_dict))
    store.get("F1", "h_new", "s1")
    warns = " ".join(store.all_warnings())
    assert "F1_max_tokens" in warns and "expected 900" in warns


# ---- outputs ----
def test_tables_written_and_report_mentions_hypotheses(study):
    _, _, res, out = study
    for name in ("decisions_D", "flip_rates_by_factor", "hypotheses", "controls_summary", "qwen3_f4_vs_f2",
                 "failure_split", "size_changing_decisions", "disagreement"):
        assert (out / f"{name}.csv").exists(), name
    assert "## Hypotheses" in (out / "report.md").read_text(encoding="utf-8")
    with open(out / "decisions_D.csv", encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == 14


def test_output_dir_guard_refuses_protected_folders(tmp_path):
    for bad in ("results", "results_smoke", "results_v2"):
        with pytest.raises(ValueError):
            assert_safe_output_dir(tmp_path / bad / "x")
    assert_safe_output_dir(tmp_path / "analysis_out")
