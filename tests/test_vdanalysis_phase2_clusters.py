"""Cluster bootstrap for suites with repeated prompts: on FAKE data (suite s1 repeats its baseline prompt in pairs
of tasks, s2 never does). Descriptive only; the gate is unchanged."""

import pytest

from tests.fake_phase2 import N_TASKS
from tests.phase2_fixtures import controls, row, world  # noqa: F401  (fixtures)
from vdanalysis.phase2.analysis import Phase2Analysis
from vdanalysis.phase2.clusters import (baseline_clusters, cluster_map, cluster_rows, cluster_summary,
                                        compare_clustered)
from vdanalysis.phase2.run_phase2 import decision_protocols, read_csv_rows, run_phase2_mode
from vdanalysis.stats import compare


def test_clusters_are_the_tasks_that_share_a_baseline_prompt(world):
    cfg, _, an, _ = world
    m = cluster_map(an, "s1")
    assert len(set(m.values())) == N_TASKS // 2 and m["t000"] == m["t001"] != m["t002"]
    m2 = cluster_map(an, "s2")
    assert len(set(m2.values())) == N_TASKS                                   # no repeated prompt: every task its own cluster
    run = an.run_for("D", "a_old", "s1")
    assert baseline_clusters(run, "baseline") == m


def test_models_must_agree_on_the_prompt_partition(world):
    cfg, _, an, _ = world
    run = an.store.get("D", "a_old", "s1")
    saved = dict(run.prompts)
    try:
        for t in ("t004", "t005"):
            run.prompts[(t, "baseline")] = "x" + t              # a model that sees different baseline prompts
        with pytest.raises(ValueError, match="disagree"):
            cluster_map(an, "s1")
    finally:
        run.prompts.clear()
        run.prompts.update(saved)


def test_with_one_task_per_cluster_it_is_the_ordinary_bootstrap(world):
    cfg, _, an, _ = world
    old, new = an.run_for("F1", "a_old", "s2"), an.run_for("F1", "a_new", "s2")
    ordinary = compare(old, new, cfg.stress, cfg.threshold, cfg.reps, cfg.seed)
    c = compare_clustered(old, new, cfg.stress, cfg.threshold, cfg.reps, cfg.seed, cluster_map(an, "s2").get)
    assert (c["ci_lo"], c["ci_hi"], c["diff"]) == (ordinary.ci_lo, ordinary.ci_hi, ordinary.diff)
    assert c["label_ci"] == ordinary.label_ci and c["n_clusters"] == c["n_tasks"] == N_TASKS


def test_clusters_widen_the_interval_but_not_the_estimate(world):
    cfg, _, an, _ = world
    old, new = an.run_for("F1", "a_old", "s1"), an.run_for("F1", "a_new", "s1")
    ordinary = compare(old, new, cfg.stress, cfg.threshold, cfg.reps, cfg.seed)
    c = compare_clustered(old, new, cfg.stress, cfg.threshold, cfg.reps, cfg.seed, cluster_map(an, "s1").get)
    assert c["diff"] == pytest.approx(ordinary.diff) == pytest.approx(-0.30)
    assert c["n_clusters"] == 10 and c["largest_cluster"] == 2 and c["n_tasks"] == 20
    assert c["ci_hi"] - c["ci_lo"] > ordinary.ci_hi - ordinary.ci_lo       # 10 clusters carry less information than 20 tasks
    assert c["label_point"] == ordinary.label_point == "harmful"


def test_rows_cover_every_decision_and_control_of_the_configured_suites(world):
    cfg, _, an, _ = world
    rows = cluster_rows(an, decision_protocols(cfg))
    dec = [r for r in rows if r["source"] == "decision"]
    for proto in ("D", "R", "F1", "F5", "F6"):
        assert len([r for r in dec if r["protocol"] == proto]) == len(an.rows(proto))      # 4 pairs x 2 suites
    ctl = {r["source"] for r in rows if r["source"].startswith("control:")}
    assert ctl == {"control:AA2_R", "control:AA2_D", "control:PC_Q2K_R", "control:PC_NODESC_R"}
    s2 = [r for r in rows if r["suite"] == "s2"]
    for r in s2:                                                            # no repeated prompt: identical to the task bootstrap
        assert r["n_clusters"] == r["n_tasks"] and not r["label_changes"]
        assert r["cluster_ci_lo"] == r["task_ci_lo"] and r["cluster_ci_hi"] == r["task_ci_hi"]
        assert r["ci_width_ratio"] is None or r["ci_width_ratio"] == pytest.approx(1.0)     # None: zero-width interval
    s1 = [r for r in rows if r["suite"] == "s1" and r["source"] == "decision"]
    assert all(r["n_clusters"] == 10 for r in s1) and any((r["ci_width_ratio"] or 0) > 1.0 for r in s1)
    # the main tables are untouched by this output: same estimate as the task-level row
    r1 = next(r for r in dec if r["protocol"] == "F1" and r["pair"] == "a_old->a_new" and r["suite"] == "s1")
    assert r1["stress_diff"] == pytest.approx(an.rows("F1")[("a_old->a_new", "s1")]["stress_diff"])
    assert r1["task_ci_lo"] == an.rows("F1")[("a_old->a_new", "s1")]["ci_lo"]


def test_a_label_can_change_when_clusters_are_used():
    """4 failing tasks of 20 = 2 failing clusters of 10: harmful per task, neutral per cluster (the descriptive point)."""
    from vdanalysis.loader import Run
    from pathlib import Path
    tasks = [f"t{i:02d}" for i in range(20)]
    mk = lambda fails: Run("D", "m", "s", Path("."), keys={(t, "schema_drift", None, None, 0): (0.0 if t in fails else 1.0, None)
                                                          for t in tasks})
    old, new = mk(set()), mk({"t00", "t01", "t02", "t03"})
    ordinary = compare(old, new, ("schema_drift",), 0.05, 2000, 1234)
    cluster_of = lambda t: f"c{int(t[1:]) // 2}"
    c = compare_clustered(old, new, ("schema_drift",), 0.05, 2000, 1234, cluster_of)
    assert c["diff"] == pytest.approx(ordinary.diff) == pytest.approx(-0.2)
    assert ordinary.label_ci == "harmful" and c["label_ci"] == "neutral" and c["label_point"] == "harmful"
    assert c["n_clusters"] == 10 and c["ci_hi"] == 0.0 > c["ci_lo"] and ordinary.ci_hi < 0


def test_summary_and_no_ci_mode(world):
    cfg, _, an, _ = world
    rows = cluster_rows(an, ["D", "F1"])
    summ = cluster_summary(rows)
    d = next(s for s in summ if s["source"] == "decision" and s["protocol"] == "D")
    assert d["n_decisions"] == 8 and d["n_clusters_min"] == 10 and d["n_clusters_max"] == 20 and d["n_label_changes"] == 0
    assert cluster_rows(Phase2Analysis(cfg, with_ci=False), ["D"]) == []                # needs the bootstrap
    cfg2 = type(cfg)({**cfg.raw, "phase2": {**cfg.p2, "cluster_bootstrap": {"suites": []}}}, base_dir=cfg.base_dir)
    assert cluster_rows(Phase2Analysis(cfg2), ["D"]) == []


def test_written_by_the_run(world, tmp_path):
    cfg, _, _, _ = world
    out = tmp_path / "o"
    run_phase2_mode(cfg, out, with_ci=True)
    rows = read_csv_rows(out / "cluster_bootstrap.csv")
    assert rows and {"n_clusters", "cluster_ci_lo", "label_ci_cluster_bootstrap", "label_changes"} <= set(rows[0])
    assert (out / "cluster_bootstrap_summary.csv").exists()
    from vdanalysis.phase2.report import build_report
    res = run_phase2_mode(cfg, tmp_path / "o2", with_ci=False)
    assert "cluster_bootstrap" not in res["tables"]
    assert "Cluster bootstrap" in build_report(cfg, run_phase2_mode(cfg, tmp_path / "o3", with_ci=True))
