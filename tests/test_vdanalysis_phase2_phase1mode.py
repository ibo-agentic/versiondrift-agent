"""Phase 1 mode of the Phase 2 code must reproduce the Phase 1 pipeline exactly.
Checked here on the Phase 1 FAKE study; the real-data check is
vdanalysis/phase2/regression.py."""

import copy

import pytest

from tests.fake_study import build_fake_results, fake_config_dict
from vdanalysis.config import Config
from vdanalysis.phase2.config import Phase2Config
from vdanalysis.phase2.regression import COMPARED, compare_tables
from vdanalysis.phase2.run_phase2 import run_phase1_mode
from vdanalysis.run_analysis import run_all


@pytest.fixture(scope="module")
def both(tmp_path_factory):
    root = tmp_path_factory.mktemp("fake_results")
    raw = build_fake_results(root)
    old_out = tmp_path_factory.mktemp("old_out")
    run_all(Config(copy.deepcopy(raw)), old_out)
    p1 = copy.deepcopy(raw)
    p1["phase2"] = {"mode": "phase1", "n_trials": 3, "seed_base": 1234,
                    "default_parts": [{"root": "auto", "require_prompts": False}]}
    new_out = tmp_path_factory.mktemp("new_out")
    run_phase1_mode(Phase2Config(p1, base_dir=root), new_out)
    return old_out, new_out


def test_tables_are_identical_to_phase1(both):
    old_out, new_out = both
    cmp = compare_tables(new_out, old_out)
    assert set(cmp) == set(COMPARED)
    for name, v in cmp.items():
        assert v["n_diffs"] == 0, (name, v["diffs"][:3])
        assert v["rows_new"] == v["rows_ref"] > 0


def test_h1_to_h5_are_in_the_compared_set():
    assert "hypotheses" in COMPARED and "decisions_D" in COMPARED and "controls" in COMPARED


def test_comparison_detects_a_difference(both, tmp_path):
    old_out, new_out = both
    import shutil
    bad = tmp_path / "bad"
    shutil.copytree(new_out, bad)
    p = bad / "hypotheses.csv"
    text = p.read_text(encoding="utf-8").replace("True", "False", 1)
    p.write_text(text, encoding="utf-8")
    cmp = compare_tables(bad, old_out)
    assert cmp["hypotheses"]["n_diffs"] >= 1
    # a different header or row count is a difference too
    q = bad / "decisions_D.csv"
    q.write_text(q.read_text(encoding="utf-8").replace("stress_diff", "stressdiff", 1), encoding="utf-8")
    assert compare_tables(bad, old_out)["decisions_D"]["n_diffs"] >= 1
    r = bad / "controls.csv"
    lines = r.read_text(encoding="utf-8").splitlines()
    r.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    assert any(d["where"] == "row count" for d in compare_tables(bad, old_out)["controls"]["diffs"])
