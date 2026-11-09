# Addendum code dry run in Phase 1 mode (DRY RUN, EXPLORATORY)

Made 2026-11-08 with `python -m vdanalysis.phase2.addendum.run_addendum --config configs/analysis_phase1_regression.yaml --out analysis/addendum_dryrun_phase1 --rerun R:R_AA`. Phase 1 data only (`results_v2/`, 3 trials, 100 tasks per suite); no `results_v3` data was read. 10,000 bootstrap replicates, seed 1234, 513 s. All tables are CSV files in this folder.

**What this is and is not.** It runs every addendum analysis end to end to test the code. Phase 1 has no D_AA2 arm, so the rerun arm is **R vs R_AA** (Phase 1's A/A: a different run seed, 3 trials, matched on drift/fault type). R_AA exists for 6 models, and only one pair has both models in it (qwen2->qwen25), so the rerun comparison covers **3 of 30 decisions**. The factor flips are against D, not R. So the S1 rows below show the code works; they are **not** a valid noise floor and should not be read as one.

## S1 rerun flip rate

| arm | n_decisions | n_rerun_flips | rate | cp95_lo | cp95_hi |
|---|---|---|---|---|---|
| R vs R_AA | 3 | 0 | 0.000 | 0.000 | 0.708 |

## S1 excess flip rate per generation factor (3 decisions, not interpretable)

| factor | n_decisions | k_factor_flips | k_rerun_flips | f_F | r_on_same_decisions | e_F | e_F_ci95_lo | e_F_ci95_hi | p_one_sided_e_gt_0 | p_holm |
|---|---|---|---|---|---|---|---|---|---|---|
| F1 | 3 | 0 | 0 | 0.000 | 0.000 | 0.000 | -0.333 | 0.000 | 1.000 | 1.000 |
| F2 | 0 | 0 | 0 | nan | nan | nan | nan | nan | nan | nan |
| F3 | 0 | 0 | 0 | nan | nan | nan | nan | nan | nan | nan |
| F4 | 3 | 0 | 0 | 0.000 | 0.000 | 0.000 | -0.333 | 0.000 | 1.000 | 1.000 |
| F5 | 3 | 0 | 0 | 0.000 | 0.000 | 0.000 | -0.333 | 0.667 | 0.496 | 1.000 |
| F6 | 3 | 0 | 0 | 0.000 | 0.000 | 0.000 | -0.333 | 0.000 | 0.991 | 1.000 |
| F11 | 3 | 2 | 0 | 0.667 | 0.000 | 0.667 | 0.000 | 0.667 | 0.140 | 0.700 |

Without the qwen25->qwen3 pair the same table is `s1_factors_excl_qwen25_qwen3.csv` (this pair is not among the 3 rerun decisions, so it is identical here).

## S1.4 expected share of decisions with a noise flip next to the observed value

| expected_share_with_noise_flip | n_decisions_with_rerun | observed_share_with_generation_flip_all_decisions | n_decisions_observed | observed_share_on_rerun_decisions |
|---|---|---|---|---|
| 0.246 | 3 | 0.500 | 30 | 0.667 |

| decision | p_rerun_flip | k_generation_factors | p_at_least_one_noise_flip |
|---|---|---|---|
| qwen2->qwen25/synthetic | 0.000 | 5 | 0.000 |
| qwen2->qwen25/bfcl_simple | 0.032 | 5 | 0.152 |
| qwen2->qwen25/bfcl_multiple | 0.161 | 5 | 0.585 |

## S2 flip types (point gate, main variants, qwen25->qwen3 shown separately)

| factor | subset | n_decisions | n_flips | sign_reversal | boundary_crossing |
|---|---|---|---|---|---|
| F1 | all | 30 | 3 | 1 | 2 |
| F1 | excluding_pair | 27 | 0 | 0 | 0 |
| F1 | only_pair | 3 | 3 | 1 | 2 |
| F2 | all | 3 | 3 | 2 | 1 |
| F2 | only_pair | 3 | 3 | 2 | 1 |
| F3 | all | 9 | 2 | 0 | 2 |
| F3 | only_pair | 3 | 0 | 0 | 0 |
| F3 | excluding_pair | 6 | 2 | 0 | 2 |
| F4 | all | 27 | 3 | 0 | 3 |
| F4 | excluding_pair | 27 | 3 | 0 | 3 |
| F5 | all | 30 | 8 | 0 | 8 |
| F5 | excluding_pair | 27 | 8 | 0 | 8 |
| F5 | only_pair | 3 | 0 | 0 | 0 |
| F6 | all | 12 | 1 | 0 | 1 |
| F6 | excluding_pair | 9 | 1 | 0 | 1 |
| F6 | only_pair | 3 | 0 | 0 | 0 |
| F11 | all | 12 | 5 | 0 | 5 |
| F11 | excluding_pair | 9 | 4 | 0 | 4 |
| F11 | only_pair | 3 | 1 | 0 | 1 |

Rerun flips: all: 0 flips of 3; excluding_pair: 0 flips of 3.

These counts reproduce Phase 1 (F1 3, F2 3, F3 2, F4 3, F5 8, F6 1; sign reversals only in the qwen25->qwen3 pair).

## S3 four-class verdict: share of decisions per class

| protocol | n_decisions | harmful | beneficial | neutral | inconclusive |
|---|---|---|---|---|---|
| D | 30 | 0.200 | 0.200 | 0.200 | 0.400 |
| F1 | 30 | 0.100 | 0.233 | 0.200 | 0.467 |
| F11 | 12 | 0.167 | 0.250 | 0.083 | 0.500 |
| F2 | 3 | 0.000 | 0.667 | 0.000 | 0.333 |
| F3 | 21 | 0.333 | 0.286 | 0.143 | 0.238 |
| F4_json | 30 | 0.167 | 0.200 | 0.267 | 0.367 |
| F5 | 30 | 0.267 | 0.367 | 0.133 | 0.233 |
| F6 | 30 | 0.233 | 0.200 | 0.200 | 0.367 |
| R | 30 | 0.100 | 0.200 | 0.267 | 0.433 |
| R_AA | 3 | 0.000 | 1.000 | 0.000 | 0.000 |

Under D: 20% harmful, 20% beneficial, 20% neutral (equivalent), 40% inconclusive. So with 100 tasks the TOST margin of 0.05 certifies equivalence for only a fifth of the decisions.

S1/S2 repeated with this gate (observed flips, class differs from the baseline's class):

| factor | subset | n_decisions | n_flips | sign_reversal | boundary_crossing |
|---|---|---|---|---|---|
| F1 | all | 30 | 3 | 1 | 2 |
| F1 | excluding_pair | 27 | 0 | 0 | 0 |
| F1 | only_pair | 3 | 3 | 1 | 2 |
| F2 | all | 3 | 3 | 2 | 1 |
| F2 | only_pair | 3 | 3 | 2 | 1 |
| F3 | all | 9 | 4 | 0 | 4 |
| F3 | only_pair | 3 | 1 | 0 | 1 |
| F3 | excluding_pair | 6 | 3 | 0 | 3 |
| F4 | all | 27 | 7 | 0 | 7 |
| F4 | excluding_pair | 27 | 7 | 0 | 7 |
| F5 | all | 30 | 11 | 0 | 11 |
| F5 | excluding_pair | 27 | 10 | 0 | 10 |
| F5 | only_pair | 3 | 1 | 0 | 1 |
| F6 | all | 12 | 3 | 0 | 3 |
| F6 | excluding_pair | 9 | 3 | 0 | 3 |
| F6 | only_pair | 3 | 0 | 0 | 0 |
| F11 | all | 12 | 6 | 0 | 6 |
| F11 | excluding_pair | 9 | 5 | 0 | 5 |
| F11 | only_pair | 3 | 1 | 0 | 1 |

## S4 headline flip rate by factor class

| set | factors | n_decisions | n_flipped | share |
|---|---|---|---|---|
| reasonable only (headline) | F1,F2,F3,F4,F5,F6,F7,F8,F9,F10 | 30 | 13 | 0.433 |
| all factors incl. misconfiguration/compound | F1,F2,F3,F4,F5,F6,F7,F8,F9,F10,F11 | 30 | 15 | 0.500 |
| P1 set (config group h1) | F1,F2,F3,F4,F5,F6,F7,F8,F9,F10 | 30 | 13 | 0.433 |

## S5 failure types

`s5_shares.csv`: 1206 rows (model x protocol x suite x condition). `s5_flip_changes.csv`: 123 rows, the change in each failure-type share for every generation-side cell, descriptive only.

## S6 power and minimum detectable effect, with the variance split (EXPLORATORY)

| suite | unit | variance of unit mean (3 trials) | between-task part | sampling part (3 trials) | between share | sigma2 per sampled trial | between (sampled trials only est.) |
|---|---|---|---|---|---|---|---|
| synthetic | task | 0.0530 | 0.0466 | 0.0064 | 0.8790 | 0.0289 | 0.0411 |
| synthetic (clusters = tasks sharing a baseline prompt) | cluster | 0.0398 | 0.0361 | 0.0037 | 0.9074 | 0.0166 | 0.0329 |
| bfcl_simple | task | 0.0723 | 0.0634 | 0.0088 | 0.8777 | 0.0398 | 0.0561 |
| bfcl_multiple | task | 0.0728 | 0.0645 | 0.0082 | 0.8867 | 0.0371 | 0.0579 |

Per-decision centring: each decision's mean is removed first, so the variance is within-decision (as in the exploratory Phase 1 report). The between-task part is 88% of the variance of a task's 3-trial mean on synthetic and 88-89% on both BFCL suites.

Projection (normal approximation; assumes a task's greedy outcome has the same expectation as its sampled outcome; not tested):

| group | scenario | sd_of_unit_mean | mde_80 | power_at_delta |
|---|---|---|---|---|
| synthetic | Phase 1 layout (3 trials), 100 tasks | 0.2303 | 0.0645 | 0.5836 |
| synthetic | 10 trials, 100 tasks | 0.2219 | 0.0622 | 0.6155 |
| synthetic clusters | Phase 1 layout (3 trials), 54 clusters | 0.1996 | 0.0761 | 0.4528 |
| synthetic clusters | 10 trials, 54 clusters | 0.1940 | 0.0740 | 0.4738 |
| bfcl_simple | Phase 1 layout (3 trials), 100 tasks | 0.2688 | 0.0753 | 0.4603 |
| bfcl_simple | 10 trials, 100 tasks | 0.2588 | 0.0725 | 0.4888 |
| bfcl_simple | 10 trials, W3 task count 191 | 0.2588 | 0.0525 | 0.7611 |
| bfcl_multiple | Phase 1 layout (3 trials), 100 tasks | 0.2698 | 0.0756 | 0.4576 |
| bfcl_multiple | 10 trials, 100 tasks | 0.2605 | 0.0730 | 0.4837 |
| bfcl_multiple | 10 trials, W3 task count 109 | 0.2605 | 0.0699 | 0.5174 |

With the second estimate of the between-task part (sampled trials only) the MDEs are lower by 0.001-0.006 (full list in `s6_projection.csv`).

## S7 McNemar gate

| protocol | n_decisions | agree_with_point_gate | agree_with_ci_gate | agree_with_class4_neutral_and_inconclusive_merged | share_harmful | share_beneficial |
|---|---|---|---|---|---|---|
| D | 30 | 0.900 | 0.900 | 0.900 | 0.133 | 0.167 |
| R | 30 | 0.967 | 0.967 | 0.967 | 0.067 | 0.200 |

## S8 reference verdict check (F5 label as reference, 9 small-model decisions)

| protocol | n_compared | n_agree | share |
|---|---|---|---|
| D | 9 | 7 | 0.778 |
| F1 | 9 | 7 | 0.778 |
| F3 | 3 | 0 | 0.000 |
| F4_json | 9 | 7 | 0.778 |
| F6 | 9 | 7 | 0.778 |
| F7 | 9 | 7 | 0.778 |
| F8 | 9 | 7 | 0.778 |
| F10 | 9 | 7 | 0.778 |
| R | 9 | 7 | 0.778 |
| R_F3 | 9 | 5 | 0.556 |
| R_F5 | 9 | 9 | 1.000 |
| R_F6 | 9 | 7 | 0.778 |

## S9

Not implemented. Questions are in `vdanalysis/phase2/addendum/s9_hierarchical.py` and in the hand-over message.
