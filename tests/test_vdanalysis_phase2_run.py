"""The whole Phase 2 run, its report, W6 agreement and the safety rules. FAKE data only.
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
from vdanalysis.phase2.descriptive import agreement_rows, read_labels
from vdanalysis.phase2.run_phase2 import assert_safe_output_dir_p2, read_csv_rows, run_phase2_mode


def test_human_agreement(tmp_path):
    p = tmp_path / "labels.csv"
    p.write_text("record_id,labeler,label\n" + "".join(
        f"{r},{who},{lab}\n" for r, (h1, h2, rule) in enumerate([("p", "p", "p"), ("p", "f", "p"), ("f", "f", "p"),
                                                                 ("f", "f", "f")])
        for who, lab in (("h1", h1), ("h2", h2), ("rule", rule))))
    rows = {(r["rater_a"], r["rater_b"]): r for r in agreement_rows(read_labels(p))}
    assert rows[("h1", "h2")]["n"] == 4 and rows[("h1", "h2")]["kappa"] == pytest.approx(0.5)
    assert rows[("h1", "rule")]["kind"] == "human_vs_rule"
    only_one = tmp_path / "one.csv"
    only_one.write_text("record_id,labeler,label\n0,h1,p\n1,h1,f\n")
    assert agreement_rows(read_labels(only_one)) == []                # no second labeler: no human-human number
    dup = tmp_path / "dup.csv"
    dup.write_text("record_id,labeler,label\n0,h1,p\n0,h1,f\n")
    with pytest.raises(ValueError, match="twice"):
        read_labels(dup)


# ---- whole run ----

def test_run_phase2_mode_end_to_end(world, tmp_path):
    cfg, paths, _, root = world
    out = tmp_path / "analysis_out_v3"
    res = run_phase2_mode(cfg, out, with_ci=True)
    names = {p.stem for p in out.glob("*.csv")}
    assert {"decisions_D", "decisions_all_protocols", "decisions_baselines", "factor_flips_long", "flip_rates_by_factor",
            "controls", "controls_summary", "hypotheses_p", "p2_p6_replication_variants", "views_flips",
            "views_controls", "views_flip_rates", "hw_noise_runs", "hw_noise_pairs", "f5_shift_vs_aa",
            "r_f5_same_hardware", "new_flips", "p7", "phase1_controls_secondary",
            "phase1_controls_secondary_summary"} <= names
    hyp = read_csv_rows(out / "hypotheses_p.csv")
    views = {r["view"] for r in hyp}
    assert views == {"all", "greedy", "sampled"}
    p1 = [r for r in hyp if r["hypothesis"] == "P1" and r["view"] == "all" and r["variant"] == "main/all_pairs"][0]
    assert p1["value"] == "0.750000" and p1["supported"] == "True"
    assert res["p7"] == "computed" and res["warnings"] == [] and res["missing"] == []
    assert [r["hypothesis"] for r in hyp if r["view"] == "all"].count("P2") == 1
    json.loads((out / "run_warnings.json").read_text())

def test_report_is_generated(world, tmp_path):
    from vdanalysis.phase2.report import write_report
    cfg, _, _, _ = world
    res = run_phase2_mode(cfg, tmp_path / "o", with_ci=True)
    path = write_report(cfg, res, tmp_path / "analysis" / "phase2" / "analysis_report.md")
    text = path.read_text(encoding="utf-8")
    assert "# Phase 2 analysis report" in text and "P1" in text and "P7" in text
    assert "Clopper-Pearson" in text

def test_output_inside_protected_folders_is_refused(tmp_path):
    for bad in ("results_v3", "results_v2", "results", "results_smoke"):
        with pytest.raises(ValueError, match="protected"):
            assert_safe_output_dir_p2(tmp_path / bad / "x")
    assert assert_safe_output_dir_p2(tmp_path / "analysis_out_v3")

def test_phase2_code_only_reads_the_record_trees(world):
    """Reading never writes: a Phase 2 run leaves every input file untouched."""
    cfg, paths, _, root = world
    before = {p: p.stat().st_mtime_ns for d in ("v2", "v3", "rescored", "rescored_v3") for p in paths[d].rglob("*") if p.is_file()}
    run_phase2_mode(cfg, root / "scratch_out", with_ci=False)
    after = {p: p.stat().st_mtime_ns for p in before}
    assert before == after


def test_secondary_gate_on_phase1_control_records_is_descriptive(world, tmp_path):
    """Phase 1 control records (3 trials), primary columns untouched, secondary columns added."""
    cfg, _, _, _ = world
    out = tmp_path / "o"
    run_phase2_mode(cfg, out, with_ci=True)
    rows = read_csv_rows(out / "phase1_controls_secondary.csv")
    nod = [r for r in rows if r["control"] == "P1_PC_NODESC_R"]
    assert len(nod) == 4 and all(r["n_records"] == str(N_TASKS * 2 * 3) for r in nod)   # 3 trials only
    assert all(r["label"] == "neutral" and r["full_label"] == "harmful" for r in nod)
    summ = {r["control"]: r for r in read_csv_rows(out / "phase1_controls_secondary_summary.csv")}
    assert summ["P1_PC_NODESC_R"]["detection_rate"] == "0.000000" and summ["P1_PC_NODESC_R"]["full_detection_rate"] == "1.000000"
    # not mixed into the hypotheses: P4/P5 read the 10-trial W2b controls
    hyp = [r for r in read_csv_rows(out / "hypotheses_p.csv") if r["view"] == "all" and r["hypothesis"] in ("P4", "P5")]
    assert {r["hypothesis"]: r["n_decisions"] for r in hyp} == {"P4": "8", "P5": "4"}
