# Prompt/seed report (read-only; numbers only, no decisions)

Scripts: `prompt_seed_report.py`; raw numbers: `prompt_seed_numbers.json`. No runs were made; `results_v2` was only read.

## 1. How schema_drift and fault_reporting use the seed

**One seed per run, not per trial.** The perturbation is drawn once per (task, condition) from the run's `seed` (config key `seed`), before the trial loop.

- `upgradecanary/runner.py:289` `seed = int(cfg["seed"])`
- `upgradecanary/runner.py:347` `rng = rng_for(seed, task.task_id, condition)`, built once per task x condition, outside the trial loop
- `upgradecanary/utils.py:13-21` `rng_for`: `random.Random("seed|task_id|condition")`
- `upgradecanary/runner.py:350-351` schema_drift: `apply_drift(task.tool, ..., rng, task.drift_type, schema=...)` -> `upgradecanary/perturbations/schema_drift.py:157-186` (`rng.choice(candidates)`: which field and which drift type)
- `upgradecanary/runner.py:356-357` fault_reporting: `choose_fault_with_ok(..., rng)` -> `upgradecanary/perturbations/runtime_faults.py:35-49` (`rng.choice([None, *faults])`: which fault, or none)
- `upgradecanary/runner.py:381` fault_reporting prompt = `build_fault_reporting_prompt(task, fault)` (`runner.py:61`), which depends only on task and fault
- The drifted schema -> prompt is built once at `runner.py:~362` (`build_prompt(task, schema, ...)`), also before the trial loop.
- The **per-trial seed** (`trial_seeds`, `runner.py:254-264`, used at `runner.py:370`, `389`, `430`) goes only into `client.generate(..., seed=trial_seed)`, i.e. sampling. It does not touch prompt construction.
- Consequence: arms with a different `cfg["seed"]` (R: 1234, R_AA: 5678) draw different drifts and faults, hence different prompts. Models compared under the same `cfg["seed"]` get the same ones.

## 2. Trials 0, 1, 2 within one Phase 1 run

**Same prompt.** Checked on all 48 D runs: 14,400 (task, condition) groups (4,800 each for baseline, schema_drift, fault_reporting); groups with more than one distinct `prompt_sha256` across trials 0-2: **0**.

## 3. Old vs new model, same protocol (D): byte-identical prompts?

**Yes, every record.** Checked all 10 pairs x 3 suites in `results_v2/D` (not only one pair per suite): 30/30 pair-suites have 900/900 matched records with byte-identical `prompt` text. The pair mistral_v01->mistral_v02 on synthetic, bfcl_simple and bfcl_multiple is 900/900 for each suite. Matching on (task_id, condition, trial_index).

## 4. A/A outlier: llama31 / bfcl_multiple, R (arm 1, seeds 1234-1236) vs R_AA (arm 2, seeds 5678-5680)

Stress diff = R_AA minus R, over schema_drift and fault_reporting. Reported pipeline value: -0.1108 (n_records 114, harmful label).

**(a) Records the analysis pipeline pairs** (key = task, condition, drift type, fault type, trial; this is what `analysis_out/controls.csv` uses):

| split | n records | mean diff (record level) | equal-weight over 2 conditions |
|---|---|---|---|
| identical prompt across arms | 114 | -0.1053 | -0.1108 |
| different prompt across arms | 0 | n/a | n/a |

By condition (identical-prompt): schema_drift n=75, -0.0933; fault_reporting n=39, -0.1282.
By trial: greedy (trial 0) n=38, mean diff 0.0000; sampled (trials 1-2) n=76, mean diff -0.1579.
The other 486 of the 600 stress records (900 minus baseline) are unpaired in the pipeline because drift type or fault type differs between arms.

**(b) All 600 stress records paired by (task, condition, trial), ignoring drift/fault type:**

| split | n records | mean diff (record level) | equal-weight over 2 conditions | schema_drift (n, diff) | fault_reporting (n, diff) |
|---|---|---|---|---|---|
| identical prompt | 114 | -0.1053 | -0.1108 | 75, -0.0933 | 39, -0.1282 |
| different prompt | 486 | -0.0967 | -0.0897 | 225, +0.0044 | 261, -0.1839 |
| all | 600 | -0.0983 | -0.0983 | 300, -0.0200 | 300, -0.1767 |

## 5. GPU-hours (sum of `elapsed_seconds` in each run's `_status.json`)

Hardware per run: Kaggle if listed in `results_v2/_kaggle_import_log.jsonl` (Tesla T4), otherwise laptop.

**Phase 1 by protocol folder** (hours; runs):

| folder | laptop | Kaggle |
|---|---|---|
| D | 11.51 (48) | - |
| F1 | 13.44 (48) | - |
| F2 | 0.53 (3) | - |
| F3 | 7.96 (24) | - |
| F3_rerun | 1.05 (3) | - |
| F4_json | 20.19 (48) | - |
| F5 | 2.94 (15) | 17.28 (33) |
| F6 | 11.42 (48) | - |
| F11 | 5.49 (18) | - |
| R | 21.06 (48) | - |
| R_AA | 5.03 (18) | - |
| R_F3 | 4.36 (15) | - |
| R_F5 | 6.83 (15) | 6.47 (15) |
| R_F6 | 4.09 (9) | - |
| R_PC_NODESC | 4.64 (12) | - |
| R_PC_Q2K | 3.14 (12) | - |
| KAGGLE_HWCHECK | - | 1.66 (6) |

Totals: laptop 123.7 h; Kaggle 25.4 h (excluding the 3 W0 re-runs, which are in `results_v3`).

**W1 estimate**, protocols D, R, F1, F2, F3, F4, F5, F6 as listed in PLAN_PHASE2.md W1 (F4 = `F4_json` folder; F3 = F3 with granite30 taken from F3_rerun). Method: per run, Phase 1 elapsed x 7/3 on the laptop (7 new trials), x 10/3 on Kaggle (10 fresh trials). A Phase 1 run has 3 trials, so this assumes time is proportional to trial count.

| protocol | hardware | runs | Phase 1 h | W1 new h |
|---|---|---|---|---|
| D | laptop | 48 | 11.51 | 26.86 |
| R | laptop | 48 | 21.06 | 49.13 |
| F1 | laptop | 48 | 13.44 | 31.36 |
| F2 | laptop | 3 | 0.53 | 1.25 |
| F3 | laptop | 24 | 7.95 | 18.54 |
| F4_json | laptop | 48 | 20.19 | 47.12 |
| F5 | laptop | 15 | 2.94 | 6.87 |
| F5 | Kaggle | 33 | 17.28 | 57.60 |
| F6 | laptop | 48 | 11.42 | 26.64 |

New Kaggle baselines, 10 fresh trials, using the Phase 1 Kaggle Q8_0 run of the same model and suite as the time proxy:

| baseline | runs | proxy Phase 1 h | W1 h (x10/3) |
|---|---|---|---|
| D on Kaggle (11 models x 3 suites) | 33 | 17.28 (from F5) | 57.60 |
| R on Kaggle (5 models x 3 suites) | 15 | 6.47 (from R_F5) | 21.57 |

The proxy is Q8_0. The two Q4_K_M Kaggle runs in KAGGLE_HWCHECK took 0.936 (llama3) and 0.949 (llama31) of the corresponding F5 Q8_0 elapsed time.

**Totals:**
- Laptop: 207.8 h.
- Kaggle F5 rows: 57.6 h.
- Kaggle including the new D and R baselines: 136.8 h of single-GPU time. With 2 GPUs per Kaggle session this is about 68.4 h of session time. The notebook's session budget is 10.5 h of new-run starts.
- Not in W1's protocol list, so not counted: R_F5, R_F3, R_F6, F11, R_AA and the R_PC controls.
