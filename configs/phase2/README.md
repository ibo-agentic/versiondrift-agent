# Phase 2 run manifests (PLAN_PHASE2.md v4)

One manifest per workstream. Every run lists protocol folder, model, suite, hardware, run seed, trial
seeds, temperatures, output folder under `results_v3/`, expected records and estimated hours.

| manifest | runs | est. hours | hardware | trials run |
|---|---|---|---|---|
| `W1_laptop.json` | 252 | 195.6 | laptop | trials 4-10 (seeds 1237-1243); Phase 1 trials 1-3 reused |
| `W1_kaggle.json` | 81 | 136.8 | Kaggle 2x T4 | all 10 (seeds 1234-1243), assuming no reuse; may change after W0 Part C |
| `W2_R.json` | 48 | 70.2 | laptop | A/A arm 2 under R: run seed 1234, trial seeds 5678-5687, 10 fresh |
| `W2_D.json` | 48 | 38.4 | laptop | A/A arm 2 under D, same |
| `W2b.json` | 24 | 18.2 | laptop | Q2_K and no-description controls under R: trials 4-10 |
| `W3.json` | 96 | 108.4 | laptop | conditional: added tasks only, 10 fresh; task files not generated yet (`data_status: pending`) |

Estimates: Phase 1 run time of the same run x 7/3 (add-on), x 10/3 (fresh); W3 x (added tasks / 100) x 10/3.
F6 runs only for the 6 models whose sampling differs from D (qwen2, qwen25, qwen3, llama3, llama31, gemma3_4b);
their sampled trials use the model's own preset temperature. `D_KAGGLE` / `R_KAGGLE` are the Q4_K_M same-hardware
baselines; their time is estimated from the Q8_0 Kaggle run of the same model and suite.

## Rebuild / check

    python -m scripts.phase2.plan                              # rewrite the manifests from results_v2 timings
    python -m scripts.phase2.check_configs --phase1-root results_v2

`check_configs` builds all configs (the laptop's own `build_config` + trial keys only), proves each equals its
Phase 1 config outside experiment / output_dir / trial keys (W3: also the task file), and cross-checks the
manifests with `configs/analysis_phase2.yaml`: same folders, first trial index (`trial_offset`), trial seeds
(`seed_base` + index), trial count, greedy/sampled pattern, and exactly the runs the analysis reads.

## Laptop

    python -m scripts.phase2.run_laptop --dry-run              # queue, hours, what is already done
    python -m scripts.phase2.run_laptop                        # run it; resumable
    python -m scripts.phase2.run_one W1_laptop D/gemma2_2b/synthetic   # one run

Order: W1 (D and R first, then F1, F2, F3, F4, F5, F6) > W2 (R) > W2b > W2 (D); W3 last, only with `--include-w3`
and only if W1, W2, W2b are complete by 20 Nov 2026, the split-equivalence check for R passed
(`results_v3/W0_determinism/split_test/R_result.json`) and the added-task files exist. No run starts after
10 Dec 2026. Interrupted runs are moved to `results_v3/_failed_attempts/` and redone. Results are zipped
(staged outside the results folders) to `C:\Users\Ibo\OneDrive\upgradecanary_backups\` every 8 runs and at the end.

## Kaggle

`kaggle/phase2/p2_runner.ipynb` runs one batch (`K01` ... `K10`, two lanes of at most ~9 h, one lane per T4) of
`W1_kaggle.json`. It asserts two Tesla T4, builds the same environment as Phase 1 (Python 3.12.12,
llama-cpp-python 0.3.35, SHA-256-checked GGUF files), and exports `p2__<folder>__<model>__<suite>.zip`.
Import on the laptop with `python -m scripts.phase2.import_kaggle <folder> --apply` (verifies, never overwrites).
