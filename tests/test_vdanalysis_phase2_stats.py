"""Clopper-Pearson, kappa, and the Phase 2 config layer."""

import math

import pytest
import yaml

from vdanalysis.phase2.config import Phase2Config, deep_merge_config, load_phase2_config
from vdanalysis.phase2.stats2 import _tail_ge, _tail_le, clopper_pearson, cohen_kappa


@pytest.mark.parametrize("k,n,lo,hi", [
    (3, 10, 0.0667, 0.6525),          # standard textbook values
    (0, 10, 0.0, 1 - 0.025 ** 0.1),
    (10, 10, 0.025 ** 0.1, 1.0),
    (1, 1, 0.025, 1.0),
    (0, 48, 0.0, 1 - 0.025 ** (1 / 48)),
])
def test_clopper_pearson_known_values(k, n, lo, hi):
    got = clopper_pearson(k, n)
    assert got[0] == pytest.approx(lo, abs=5e-4)
    assert got[1] == pytest.approx(hi, abs=5e-4)


@pytest.mark.parametrize("k,n", [(2, 48), (5, 48), (13, 30), (4, 8), (7, 13), (0, 3), (47, 48)])
def test_clopper_pearson_satisfies_its_defining_equations(k, n):
    lo, hi = clopper_pearson(k, n)
    if k > 0:
        assert _tail_ge(k, n, lo) == pytest.approx(0.025, abs=1e-9)
    if k < n:
        assert _tail_le(k, n, hi) == pytest.approx(0.025, abs=1e-9)
    assert 0.0 <= lo <= k / n <= hi <= 1.0


def test_clopper_pearson_contains_point_and_widens_with_less_data():
    a, b = clopper_pearson(5, 50), clopper_pearson(1, 10)
    assert (a[1] - a[0]) < (b[1] - b[0])


def test_clopper_pearson_rejects_bad_input():
    with pytest.raises(ValueError):
        clopper_pearson(3, 2)
    with pytest.raises(ValueError):
        clopper_pearson(0, 0)


def test_kappa():
    assert cohen_kappa(list("aabb"), list("aabb")) == pytest.approx(1.0)
    assert cohen_kappa(list("aabb"), list("bbaa")) == pytest.approx(-1.0)
    # 10 items, 7 agree, marginals 50/50 -> po 0.7, pe 0.5 -> kappa 0.4
    a = list("aaaaabbbbb")
    b = list("aaabbbbbba")[:5] + list("bbbbb")
    assert cohen_kappa(["a"] * 5 + ["b"] * 5, ["a", "a", "a", "b", "b", "b", "b", "b", "a", "a"]) == pytest.approx(0.2)
    assert cohen_kappa(["a", "a"], ["a", "a"]) is None          # chance agreement 1: undefined
    assert cohen_kappa([], []) is None
    with pytest.raises(ValueError):
        cohen_kappa(["a"], ["a", "b"])


# ---- config ----
def test_extends_merges_one_level_deep(tmp_path):
    (tmp_path / "parent.yaml").write_text(yaml.safe_dump({
        "protocols": {"D": {"folder": "D"}, "F10": {"folder": "F10", "root": "rescored"}},
        "controls": [{"name": "old"}], "gate": {"threshold": 0.05, "reps": 10, "seed": 1}, "x": 1}))
    (tmp_path / "child.yaml").write_text(yaml.safe_dump({
        "extends": "parent.yaml", "protocols": {"F10": {"folder": "F10"}, "E": {"folder": "E"}},
        "controls": [{"name": "new"}], "gate": {"reps": 99}}))
    from vdanalysis.phase2.config import _load_raw
    raw = _load_raw(tmp_path / "child.yaml")
    assert raw["protocols"]["D"] == {"folder": "D"}                  # parent entry kept
    assert raw["protocols"]["F10"] == {"folder": "F10"}              # child entry replaces the whole entry
    assert "E" in raw["protocols"]
    assert raw["controls"] == [{"name": "new"}]                      # lists are replaced
    assert raw["gate"] == {"threshold": 0.05, "reps": 99, "seed": 1}  # dicts merge one level
    assert raw["x"] == 1 and "extends" not in raw


def test_real_phase2_config_loads_and_resolves_parts():
    cfg = load_phase2_config("configs/analysis_phase2.yaml")
    assert cfg.mode == "phase2" and cfg.n_trials == 10
    # Kaggle F5 models: only the fresh results_v3 part; laptop models: Phase 1 trials + add-on trials
    assert [(p.root, p.trial_offset) for p in cfg.parts_for("F5", "qwen3")] == [("v3", 0)]
    assert [(p.root, p.trial_offset) for p in cfg.parts_for("F5", "phi3_mini")] == [("results_root", 0), ("v3", 3)]
    assert [(p.root, p.trial_offset) for p in cfg.parts_for("D", "llama3")] == [("results_root", 0), ("v3", 3)]
    assert [p.root for p in cfg.parts_for("F7", "llama3")] == ["rescored_root", "rescored_v3"]
    assert [p.root for p in cfg.parts_for("R_F5", "llama3")] == ["results_root"]
    assert cfg.f6_trim_models() == set(cfg.model_sets["f6_equals_d"]) and len(cfg.f6_trim_models()) == 10
    assert cfg.same_hardware_for("F5")["baseline"] == "D_KAGGLE" and len(cfg.same_hardware_for("F5")["models"]) == 11
    assert cfg.same_hardware_for("R_F5")["baseline"] == "R_KAGGLE" and len(cfg.same_hardware_for("R_F5")["models"]) == 5
    assert cfg.same_hardware_for("D") is None
    assert cfg.seed_base("D_AA2") == 5678 and cfg.seed_base("D") == 1234
    assert [c["name"] for c in cfg.controls] == ["AA2_R", "AA2_D", "PC_Q2K_R", "PC_NODESC_R"]


def test_phase1_mode_switches_phase2_features_off():
    cfg = load_phase2_config("configs/analysis_phase1_regression.yaml")
    assert cfg.mode == "phase1"
    assert cfg.f6_trim_models() == set() and cfg.same_hardware_for("F5") is None
    assert [p.root for p in cfg.parts_for("F10", "qwen3")] == ["rescored_root"]
    assert cfg.seed_base("R_AA") == 5678


def test_bad_references_are_rejected(tmp_path):
    base = yaml.safe_load(open("configs/analysis_official_folders.yaml", encoding="utf-8"))
    base["phase2"] = {"mode": "phase2", "roots": {}, "default_parts": [{"root": "nowhere"}]}
    with pytest.raises(ValueError, match="unknown root"):
        Phase2Config(base, tmp_path)
    base["phase2"] = {"mode": "phase2", "default_parts": [{"root": "auto", "models": "no_such_set"}]}
    with pytest.raises(ValueError, match="unknown model set"):
        Phase2Config(base, tmp_path)
    base["phase2"] = {"mode": "weird"}
    with pytest.raises(ValueError, match="mode"):
        Phase2Config(base, tmp_path)
