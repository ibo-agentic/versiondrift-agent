# Regression check: Phase 2 code in Phase 1 mode vs the frozen Phase 1 tables

Run on 2026-10-19 (first build) and re-run on 2026-10-19 after the update to PLAN_PHASE2.md v4 (same result both times),
on Phase 1 data only (`results_v2/`, `rescored/`), 3 trials, primary gate only,
old A/A (different run seed, records matched on drift/fault type), no F6 trimming, no same-hardware
baselines. Command:

    python -m vdanalysis.phase2.regression --config configs/analysis_phase1_regression.yaml \
        --reference analysis_out --out analysis_out_v3/regression_phase1

Every cell of each table was compared as text with the table written by the original
`vdanalysis.run_analysis` (`analysis_out/`).

| table | rows (new / reference) | differences |
|---|---|---|
| decisions_D | 30 / 30 | 0 |
| decisions_all_protocols | 360 / 360 | 0 |
| factor_flips_long | 276 / 276 | 0 |
| flip_rates_by_factor | 68 / 68 | 0 |
| controls | 42 / 42 | 0 |
| controls_summary | 3 / 3 | 0 |
| hypotheses (H1-H5, all variants) | 19 / 19 | 0 |

**Total differences: 0.** Run time 2 min 25 s (first run), 2 min 01 s (re-run after the v4 update), 2 min 01 s (re-run after the cluster-bootstrap
and W3-suites changes; again 0 differences). No loader warnings, no missing runs.

Side result: the merge checks (prompts byte-identical across the trials of every (task, condition),
no duplicate (task, condition, trial), seeds equal to 1234 + trial index, one temperature per trial)
passed on every Phase 1 run that has raw outputs, including the R_AA runs (seed base 5678).
