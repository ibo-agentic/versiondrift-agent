"""scripts/exploratory: the rounding helper, the output-folder guard, and a smoke test of run_all (no real data is read here)."""

import importlib
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from scripts.exploratory import _common, run_all
from upgradecanary.gates import ci_gate as raw_ci_gate
from upgradecanary.gates import point_gate as raw_point_gate

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- rounding helper
def test_rd_removes_float_noise():
    assert 0.1 + 0.2 != 0.3                               # the premise: float noise exists
    assert _common.rd(0.1 + 0.2) == 0.3
    assert _common.rd(0.030000000000000002) == 0.03
    assert _common.rd(-0.030000000000000002) == -0.03


@pytest.mark.parametrize("delta", [0.03, 0.05, 0.07])
def test_exact_boundary_is_neutral_even_when_the_float_is_a_hair_over(delta):
    over = float(np.nextafter(delta, 1))                  # 1 ulp above the threshold, as a float average can be
    under = float(np.nextafter(-delta, -1))
    assert raw_point_gate(over, delta) == "beneficial" and raw_point_gate(under, delta) == "harmful"      # the plain gate is fooled
    assert _common.point_label(over, delta) == "neutral" and _common.point_label(under, delta) == "neutral"
    assert _common.point_label(delta + 1e-6, delta) == "beneficial" and _common.point_label(-delta - 1e-6, delta) == "harmful"
    assert list(_common.point_code(np.array([over, under, 0.0, delta + 1e-6, -delta - 1e-6]), delta)) == [0, 0, 0, 1, -1]


def test_ci_gate_and_classify_use_the_rounded_diff():
    over = float(np.nextafter(0.05, 1))
    assert raw_ci_gate(over, 0.01, 0.1) == "beneficial"                    # plain gate: wrong at the boundary
    assert _common.ci_gate(over, 0.01, 0.1) == "neutral"
    assert _common.ci_gate(0.06, 0.01, 0.1) == "beneficial" and _common.ci_gate(-0.06, -0.1, -0.01) == "harmful"
    assert _common.classify(over, -0.04, 0.04, "neutral") == "neutral"      # the 90% interval inside +/-0.05
    assert _common.classify(0.0, -0.2, 0.2, "neutral") == "inconclusive"
    assert _common.classify(0.06, 0.01, 0.1, "beneficial") == "beneficial"


# ---------------------------------------------------------------- output-folder guard
@pytest.mark.parametrize("name", ["results_v3/x", "results_v2", "results", "analysis_out_v3/addendum", "analysis_out_v3_p7", "data", "configs/phase2"])
def test_protected_folders_are_refused(name):
    with pytest.raises(SystemExit):
        _common.check_out_dir(REPO / name)
    assert not (REPO / name / "should_not_exist").exists()


def test_a_scratch_folder_is_accepted_and_created(tmp_path):
    p = _common.check_out_dir(tmp_path / "new" / "folder")
    assert p.is_dir()


def test_static_paragraphs_exist():
    for name in ("item_level_flips_tail", "wrong_calls_where_errors", "wrong_calls_more_summary", "threshold_correction", "s3_w3_moves_note", "s3_w3_caveats",
                 "item_level_noise_summary", "wrong_calls_coverage_summary"):
        assert len(_common.static(name)) > 100


def test_same_model_churn_counts_majority_and_greedy():
    from scripts.exploratory._item_level_noise import _churn
    right, wrong = (True, None), (False, "x")
    # question q1: 6/10 vs 5/10 (right -> wrong by majority; greedy both right); q2: 0/10 vs 10/10 (wrong -> right both ways)
    a = {"q1": {t: right if t < 6 else wrong for t in range(10)}, "q2": {t: wrong for t in range(10)}}
    b = {"q1": {t: right if t < 5 else wrong for t in range(10)}, "q2": {t: right for t in range(10)}}
    assert _churn(a, b, "majority") == (2, 1, 1)
    assert _churn(a, b, "greedy") == (2, 0, 1)


def test_wrong_call_kinds():
    from scripts.exploratory.wrong_calls_coverage import kind
    assert kind("neutral", "neutral") == "right"
    assert kind("inconclusive", "harmful") == "inconclusive"
    assert kind("harmful", "beneficial") == "serious"
    assert kind("neutral", "beneficial") == "mild"


# ---------------------------------------------------------------- run_all
def test_every_analysis_module_imports_and_has_run():
    for name in run_all.ANALYSES + ["boundary_check"]:
        mod = importlib.import_module(f"scripts.exploratory.{name}")
        assert callable(mod.run), name


def test_run_all_help_runs():
    r = subprocess.run([sys.executable, "-m", "scripts.exploratory.run_all", "--help"], cwd=REPO, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "--only" in r.stdout


def test_compare_file_reports_identical_numbers_and_differences(tmp_path):
    (tmp_path / "a.md").write_text("x 1 2.50 -3\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("x 1 2.50 -3\n", encoding="utf-8")
    (tmp_path / "c.md").write_text("y 1 2.5 -3\n", encoding="utf-8")
    (tmp_path / "d.md").write_text("x 1 2.51 -3\n", encoding="utf-8")
    assert run_all.compare_file(tmp_path / "b.md", tmp_path / "a.md")[0] == "identical"
    assert run_all.compare_file(tmp_path / "c.md", tmp_path / "a.md")[0] == "text differs, all numbers equal"
    status, shown = run_all.compare_file(tmp_path / "d.md", tmp_path / "a.md")
    assert status.startswith("DIFFERENT: 1 of 3") and "2.50 -> regenerated 2.51" in shown[0]


def test_run_all_smoke_with_fake_analyses(tmp_path, monkeypatch, capsys):
    """run_all imports each analysis, calls run(out), and compares the files with the current folder; a failing analysis is reported, not fatal."""
    def good_run(out):
        (out / "EXPLORATORY_fake.md").write_text("value 1.5\n", encoding="utf-8")
        return ["EXPLORATORY_fake.md"]

    def bad_run(out):
        raise RuntimeError("boom")

    fakes = {"fake_good": types.SimpleNamespace(run=good_run), "fake_bad": types.SimpleNamespace(run=bad_run)}
    real_import = importlib.import_module
    monkeypatch.setattr(run_all, "ANALYSES", list(fakes))
    monkeypatch.setattr(run_all.importlib, "import_module", lambda n: fakes[n.rsplit(".", 1)[1]] if n.rsplit(".", 1)[1] in fakes else real_import(n))
    current = tmp_path / "current"
    current.mkdir()
    (current / "EXPLORATORY_fake.md").write_text("value 1.5\n", encoding="utf-8")
    rc = run_all.main(["--out", str(tmp_path / "out"), "--current", str(current)])
    text = capsys.readouterr().out
    assert rc == 1                                           # one analysis failed
    assert "[ok]     fake_good" in text and "[FAILED] fake_bad" in text and "EXPLORATORY_fake.md: identical" in text
    current.joinpath("EXPLORATORY_fake.md").write_text("value 1.6\n", encoding="utf-8")
    run_all.main(["--only", "fake_good", "--out", str(tmp_path / "out2"), "--current", str(current)])
    assert "DIFFERENT: 1 of 1 numbers differ" in capsys.readouterr().out


def test_run_all_refuses_a_protected_output_folder():
    with pytest.raises(SystemExit):
        run_all.main(["--out", str(REPO / "results_v3" / "regen")])
