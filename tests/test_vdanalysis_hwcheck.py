"""Kaggle hardware-check analysis on FAKE results (known answers; no real data).

Fake setup (tests/fake_study.py): KAGGLE_HWCHECK has h_old and h_new. h_old is
identical to D. h_new fails 7 tasks instead of D's 6, so:
  pair stress diff: D -0.30, Kaggle -0.35  -> hardware diff -0.05
  greedy score of h_new: D 0.80 -> Kaggle 0.7667 (-1/30, outside 0.03)
  parse rate of h_new:   D 0.90 -> Kaggle 0.8667 (-1/30, outside 0.03)
"""

import pytest

from tests.fake_study import build_fake_results
from vdanalysis.config import Config
from vdanalysis.engine import Analysis
from vdanalysis.hwcheck import hwcheck_pair_rows, hwcheck_run_rows, hwcheck_summary
from vdanalysis.run_analysis import run_all


@pytest.fixture(scope="module")
def cfg(tmp_path_factory):
    return Config(build_fake_results(tmp_path_factory.mktemp("fake_hw")))


def test_pair_level_hardware_difference(cfg):
    rows = hwcheck_pair_rows(Analysis(cfg))
    assert {r["suite"] for r in rows} == {"s1", "s2"}
    for r in rows:
        assert r["pair"] == "h_old->h_new"
        assert r["laptop_stress_diff"] == pytest.approx(-0.30)
        assert r["kaggle_stress_diff"] == pytest.approx(-0.35)
        assert r["hardware_diff"] == pytest.approx(-0.05)
        assert r["abs_hardware_diff"] == pytest.approx(0.05)
        assert r["laptop_label_point"] == "harmful" and r["kaggle_label_point"] == "harmful"
        assert r["label_point_changed"] is False


def test_run_level_tolerance(cfg):
    rows = hwcheck_run_rows(Analysis(cfg))
    assert len(rows) == 4  # 2 models x 2 suites
    by = {(r["model"], r["suite"]): r for r in rows}
    old = by[("h_old", "s1")]
    assert old["score_diff"] == 0 and old["parse_rate_diff"] == 0 and old["within_tolerance"] is True
    new = by[("h_new", "s1")]
    assert new["laptop_greedy_score"] == pytest.approx(0.80)
    assert new["kaggle_greedy_score"] == pytest.approx(0.8 - 1 / 30)
    assert new["laptop_parse_rate"] == pytest.approx(0.90)
    assert new["kaggle_parse_rate"] == pytest.approx(0.9 - 1 / 30)
    assert new["within_tolerance"] is False
    assert new["n_greedy_laptop"] == new["n_greedy_kaggle"] == 60


def test_tolerance_is_configurable_and_boundary_is_inclusive(cfg):
    cfg.raw["hardware_check"]["tolerance"] = 1 / 30 + 1e-9
    try:
        assert all(r["within_tolerance"] for r in hwcheck_run_rows(Analysis(cfg)))
    finally:
        cfg.raw["hardware_check"]["tolerance"] = 0.03


def test_summary(cfg):
    an = Analysis(cfg)
    s = hwcheck_summary(hwcheck_pair_rows(an), hwcheck_run_rows(an), expected_runs=4)
    assert s["runs_compared"] == 4 and s["n_outside_tolerance"] == 2
    assert s["all_within_tolerance"] is False
    assert s["max_abs_hardware_diff"] == pytest.approx(0.05)
    assert s["pair_suites_label_changed"] == 0


def test_missing_kaggle_runs_are_notes_not_errors(tmp_path):
    import shutil

    d = build_fake_results(tmp_path)
    shutil.rmtree(tmp_path / "KAGGLE_HWCHECK" / "h_new" / "s2")
    an = Analysis(Config(d))
    pair, runs = hwcheck_pair_rows(an), hwcheck_run_rows(an)
    assert [r["suite"] for r in pair] == ["s1"]
    assert len(runs) == 3
    assert len(an.hwcheck_notes) == 2 and not an.missing
    s = hwcheck_summary(pair, runs, expected_runs=4)
    assert s["all_within_tolerance"] is False  # incomplete never counts as a pass


def test_full_pipeline_writes_tables_and_keeps_hwcheck_out_of_decisions(cfg, tmp_path):
    res = run_all(cfg, tmp_path / "out")
    for name in ("hwcheck_pair", "hwcheck_runs", "hwcheck_summary"):
        assert (tmp_path / "out" / f"{name}.csv").exists()
    assert not any(r["protocol"] == "KAGGLE_HWCHECK" for r in res["tables"]["decisions_all_protocols"])
    assert res["tables"]["hwcheck_summary"][0]["runs_compared"] == 4


def test_no_hardware_check_block_means_no_tables(tmp_path):
    d = build_fake_results(tmp_path)
    d.pop("hardware_check")
    an = Analysis(Config(d))
    assert hwcheck_pair_rows(an) == [] and hwcheck_run_rows(an) == []
