"""Phase 2 engine on FAKE data with known answers: merged runs, F6 trimming, same-hardware
baselines, views, the new A/A, the secondary gate, descriptive tables. No real data.
"""

import csv
import json
from pathlib import Path

import pytest

from tests.fake_phase2 import KAGGLE, MODELS, N_TASKS, SUITES, TRIM
from tests.phase2_fixtures import by, controls, row, world  # noqa: F401  (fixtures)
from vdanalysis.phase2.analysis import Phase2Analysis, ViewSpec
from vdanalysis.phase2.config import Phase2Config
from vdanalysis.phase2.stats2 import clopper_pearson
from vdanalysis.phase2.controls2 import ControlDesignError, check_same_design, control_rows2, per_control_summary2
from vdanalysis.phase2.descriptive import f5_shift_vs_aa, hw_noise_pairs, hw_noise_runs, r_f5_same_hardware


def test_merged_laptop_run_has_ten_trials_and_no_hard_coded_size(world):
    cfg, _, an, _ = world
    run = an.run_for("D", "a_new", "s1")
    assert run.trials == list(range(10)) and len(run) == N_TASKS * 3 * 10
    assert run.warnings == []
    assert an.store.get("R_PC_Q2K", "a_new", "s1").trials == [0, 1, 2]          # Phase 1 only

def test_kaggle_f5_models_use_only_the_fresh_part_and_phase1_f5_is_not_read(world):
    cfg, _, an, _ = world
    run = an.store.get("F5", "b_new", "s1")                    # v2 holds a conflicting copy; it must not be touched
    assert len(run.parts) == 1 and "results_v3" in str(run.parts[0]) and run.trials == list(range(10))
    small = an.store.get("F5", "d_new", "s1")
    assert len(small.parts) == 2 and small.trials == list(range(10))

def test_decisions_under_d_are_neutral(world):
    _, _, an, _ = world
    for r in an.rows("D").values():
        assert r["stress_diff"] == 0 and r["label_point"] == r["label_ci"] == "neutral"
        # n_unmatched is Phase 1's quantity: records of the run that are not stress records (the baseline ones)
        assert r["n_records"] == N_TASKS * 2 * 10 and r["n_unmatched"] == N_TASKS * 10


# ---- F6 trimming ----

def test_f6_trim_uses_d_records_for_the_listed_models_only(world):
    cfg, _, an, _ = world
    assert an.run_for("F6", "a_new", "s1").protocol == "D"
    assert an.run_for("F6", "c_new", "s1").protocol == "F6"
    # without trimming a_new's F6 data (all-fail on 6 tasks) would flip pair a: with trimming it must not
    assert not row(an, "F6", "a_old->a_new", "s1")["stress_diff"] < 0
    assert row(an, "F6", "c_old->c_new", "s1")["stress_diff"] == pytest.approx(-0.30)
    assert set(cfg.f6_trim_models()) == set(TRIM)

def test_f6_main_flip_rate_uses_only_sampling_changed_pairs(world):
    cfg, _, an, _ = world
    flips = [r for r in an.flip_table() if r["factor"] == "F6"]
    assert {(r["pair"], r["suite"]) for r in flips if r["flipped"]} == {("c_old->c_new", "s1"), ("c_old->c_new", "s2")}
    assert all(r["n_models_changed"] == (1 if r["pair"].startswith("c_") else 0) for r in flips)


# ---- same-hardware rule ----

def test_f5_same_hardware_baseline_is_used_for_kaggle_pairs(world):
    cfg, _, an, _ = world
    flips = {(r["factor"], r["pair"], r["suite"]): r for r in an.flip_table(["F5"])}
    b = flips[("F5", "b_old->b_new", "s1")]
    assert b["baseline_protocol"] == "D_KAGGLE" and b["d_label"] == "harmful" and not b["flipped"]
    d = flips[("F5", "d_old->d_new", "s1")]
    assert d["baseline_protocol"] == "D" and d["flipped"] and d["factor_label"] == "harmful"
    # the Phase 1 way (laptop D baseline) would have called pair b a flip
    assert row(an, "D", "b_old->b_new", "s1")["label_point"] == "neutral"

def test_mixed_hardware_pair_is_refused(world):
    cfg, _, an, _ = world
    with pytest.raises(ValueError, match="mixes hardware"):
        an.baseline_protocol_for("F5", {"old": "b_new", "new": "c_old"})

def test_r_f5_effect_is_measured_against_the_kaggle_r_baseline(world):
    _, _, an, _ = world
    rows = {(r["pair"], r["suite"]): r for r in r_f5_same_hardware(an)}
    b = rows[("b_old->b_new", "s1")]
    assert b["baseline_protocol"] == "R_KAGGLE" and b["baseline_label_ci"] == "harmful" and not b["flipped"]
    assert rows[("d_old->d_new", "s1")]["baseline_protocol"] == "R"
    # 3-trial R_F5 against the 10-trial baseline: only the shared trials are compared
    assert an.rows("R_F5")[("b_old->b_new", "s1")]["n_records"] == N_TASKS * 2 * 3


# ---- P1 ----

def test_f10_is_d_greedy_only_and_needs_no_files(world):
    _, _, an, _ = world
    run = an.run_for("F10", "a_new", "s1")
    assert run.trials == [0] and run.protocol == "D"


# ---- P2 / P6 ----

def test_aa2_compares_all_records_with_identical_prompts(world, controls):
    for r in by(controls, "AA2_R") + by(controls, "AA2_D"):
        # n_unmatched is Phase 1's quantity: records of the run that are not stress records (the baseline ones)
        assert r["n_records"] == N_TASKS * 2 * 10 and r["n_unmatched"] == N_TASKS * 10
        assert r["greedy_scores_identical"] is True
    assert len(by(controls, "AA2_R")) == 16 == len(by(controls, "AA2_D"))

def test_aa2_d_point_gate_false_alarms(controls):
    fa = [r for r in by(controls, "AA2_D") if r["label"] != "neutral"]
    assert {(r["old"], r["suite"]) for r in fa} == {("c_old", "s1"), ("c_old", "s2")}
    assert fa[0]["stress_diff"] == pytest.approx(-0.27)
    assert fa[0]["full_diff"] == pytest.approx(-0.18)          # secondary gate: baseline + stress, equal weight

def test_aa2_r_ci_gate(controls):
    fa = {(r["old"], r["suite"]) for r in by(controls, "AA2_R") if r["label"] != "neutral"}
    assert fa == {("a_old", "s1"), ("a_old", "s2")}
    d_old = by(controls, "AA2_R", "d_old", "s1")[0]
    assert d_old["label_point"] == "harmful" and d_old["label_ci"] == "neutral"      # gates differ, on purpose

def test_secondary_gate_sees_what_the_stress_gate_cannot(controls):
    for r in by(controls, "PC_NODESC_R"):
        assert r["stress_diff"] == 0 and r["label"] == "neutral"
        assert r["full_diff"] == pytest.approx(-0.4 / 3) and r["full_label"] == "harmful"
        assert r["n_records"] == N_TASKS * 2 * 3                      # 3-trial control vs 10-trial R: shared trials

def test_primary_gate_columns_are_unchanged_by_the_secondary_gate(world):
    _, _, an, _ = world
    plain = control_rows2(an, secondary=False)
    full = control_rows2(an, secondary=True)
    assert len(plain) == len(full)
    for p, f in zip(plain, full):
        assert {k: f[k] for k in p} == p                   # every primary column identical
    assert "full_label" not in plain[0] and "full_label" in full[0]

def test_control_summaries_have_exact_cis(controls):
    s = {r["control"]: r for r in per_control_summary2(controls)}
    assert s["AA2_R"]["false_alarm_rate"] == 0.125 and s["AA2_R"]["n_models"] == 8 and s["AA2_R"]["n_models_with_flag"] == 1
    assert (s["AA2_R"]["ci95_lo"], s["AA2_R"]["ci95_hi"]) == clopper_pearson(2, 16)
    assert s["PC_NODESC_R"]["detection_rate"] == 0 and s["PC_NODESC_R"]["full_detection_rate"] == 1.0
    assert s["AA2_D"]["full_false_alarm_rate"] == 0.125

def test_aa2_refuses_arms_with_different_prompts(world):
    _, _, an, _ = world
    a = an.store.get("D", "a_old", "s1")
    b = an.store.get("D_AA2", "a_old", "s1")
    b2 = type(b)(**{**b.__dict__, "prompts": {k: v[::-1] for k, v in b.prompts.items()}})
    with pytest.raises(ControlDesignError, match="prompts differ"):
        check_same_design(a, b2, "t")
    short = b.view("all", tasks={"t000"})
    with pytest.raises(ControlDesignError):
        check_same_design(a, short, "t")
    b3 = type(b)(**{**b.__dict__, "keys": dict(list(b.keys.items())[:-1])})
    with pytest.raises(ControlDesignError, match="not every record is matched"):
        check_same_design(a, b3, "t")
    b4 = type(b)(**{**b.__dict__, "prompts": {}})
    with pytest.raises(ControlDesignError, match="not available"):
        check_same_design(a, b4, "t")


# ---- views ----

def test_greedy_and_sampled_views(world):
    cfg, _, an, _ = world
    g, s = an.with_view(ViewSpec(trials="greedy")), an.with_view(ViewSpec(trials="sampled"))
    assert g.run_for("D", "a_new", "s1").trials == [0]
    assert s.run_for("D", "a_new", "s1").trials == list(range(1, 10))
    assert g.rows("F1")[("a_old->a_new", "s1")]["stress_diff"] == pytest.approx(-0.30)
    # the A/A sampled-only failures are invisible to the greedy view, fully visible to the sampled view
    assert all(r["label"] == "neutral" for r in control_rows2(g) if r["control"] == "AA2_D")
    sampled_fa = [r for r in control_rows2(s) if r["control"] == "AA2_D" and r["label"] != "neutral"]
    assert len(sampled_fa) == 2 and sampled_fa[0]["stress_diff"] == pytest.approx(-0.30)


# ---- descriptive outputs ----

def test_hardware_noise(world):
    _, _, an, _ = world
    runs = {(r["model"], r["suite"]): r for r in hw_noise_runs(an)}
    assert set(runs) == {(m, s) for m in KAGGLE for s in SUITES}
    assert runs[("b_new", "s1")]["stress_diff"] == pytest.approx(-0.30)
    assert runs[("b_new", "s1")]["greedy_stress_diff"] == pytest.approx(-0.30)
    assert runs[("b_old", "s1")]["stress_diff"] == 0 and runs[("b_new", "s1")]["prompts_identical"] is True
    pairs = hw_noise_pairs(an)
    assert len(pairs) == 2 and pairs[0]["hardware_diff"] == pytest.approx(-0.30) and not pairs[0]["labels_agree"]

def test_f5_shift_against_aa_noise(world, controls):
    _, _, an, _ = world
    rows = {(r["model"], r["suite"]): r for r in f5_shift_vs_aa(an, controls, "AA2_D")}
    d_new = rows[("d_new", "s1")]
    assert d_new["f5_shift"] == pytest.approx(-0.30) and d_new["baseline_protocol"] == "D"
    assert d_new["aa_max_abs_diff"] == pytest.approx(0.27) and d_new["exceeds_aa_max"] is True
    b_new = rows[("b_new", "s1")]
    assert b_new["baseline_protocol"] == "D_KAGGLE" and b_new["f5_shift"] == 0 and b_new["exceeds_aa_max"] is False
    assert f5_shift_vs_aa(an, [], "AA2_D")[0]["aa_max_abs_diff"] is None

def test_missing_runs_fail_loudly_or_are_listed(world, tmp_path):
    cfg, _, _, root = world
    import shutil
    # a copy of the world without D_AA2 for one model
    raw = json.loads(json.dumps(cfg.raw))
    store_root = Path(cfg.raw["phase2"]["roots"]["v3"])
    victim = store_root / "D_AA2" / "a_old" / "s1"
    backup = tmp_path / "bak"
    shutil.move(str(victim), str(backup))
    try:
        fresh = Phase2Analysis(Phase2Config(raw, base_dir=root))
        with pytest.raises(FileNotFoundError):
            control_rows2(fresh)
        lenient = Phase2Analysis(Phase2Config(raw, base_dir=root), allow_missing=True)
        rows = control_rows2(lenient)
        assert len(by(rows, "AA2_D")) == 15 and any("D_AA2/a_old/s1" in m or "a_old" in m for m in lenient.missing)
    finally:
        shutil.move(str(backup), str(victim))
