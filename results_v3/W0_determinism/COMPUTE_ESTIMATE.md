# Compute estimate (read-only; numbers only, no decisions)

Source: `compute_estimate.py` -> `compute_estimate_numbers.json`. Base = sum of Phase 1 `_status.json` `elapsed_seconds` per run.
Scaling: laptop reuse of trials 1-3 = x7/3; fresh 10 trials = x10/3 (time assumed proportional to trial count; per-run model-load overhead not separated out).

## 1. F6 vs D, per model

Compared `results_v2/_generated_configs/F6__<model>__<suite>.yaml` with `<model>__<suite>.yaml` for all 16 models and all 3 suites (qwen3 via its half1 configs), ignoring `output_dir` and `experiment`.
Effective sampling per trial is what counts. F6 configs always add explicit per-trial lists and `sampling_preset`/`thinking` keys, which equal D's library defaults for the unchanged models.
Effective values are identical across the 3 suites for every model.

**F6 = D (10 models):** mistral_v01, mistral_v02, mistral_v03, phi3_mini, phi35_mini, phi4_mini, granite30, granite31, granite32, gemma2_2b.
All have temperatures [0.0, 0.7, 0.7], top_p 0.95, top_k 40, min_p 0.05, repeat_penalty 1.0, seeds [1234, 1235, 1236].
This matches DEVIATIONS.md 2026-10-08 (18,000/18,000 sampled-trial records byte-identical).

**F6 != D (6 models), sampled trials only (trial 0 is pinned to D's values):**

| model | temp | top_p | top_k | min_p | repeat_penalty |
|---|---|---|---|---|---|
| qwen2 | 0.7 | 0.8 | 20 | 0.05 | 1.05 |
| qwen25 | 0.7 | 0.8 | 20 | 0.05 | 1.05 |
| qwen3 | 0.6 | 0.95 | 20 | 0.0 | 1.0 |
| llama3 | 0.6 | 0.9 | 40 | 0.05 | 1.0 |
| llama31 | 0.6 | 0.9 | 40 | 0.05 | 1.0 |
| gemma3_4b | 0.7 | 0.95 | 64 | 0.05 | 1.0 |

## 2. W1 laptop hours without the F6 = D runs

| item | hours |
|---|---|
| F6 Phase 1, all 48 runs | 11.42 |
| F6 Phase 1, 30 runs with F6 = D | 5.20 |
| F6 Phase 1, 18 runs that differ | 6.22 |
| W1 F6 (x7/3), before | 26.64 |
| W1 F6 (x7/3), after | 14.52 |
| Saved | 12.12 |
| **W1 laptop total, before** | 207.76 |
| **W1 laptop total, after** | **195.64** |

W1 Kaggle is unchanged (F6 is all laptop): 57.60 (F5 rows) + 57.60 (new D baselines) + 21.57 (new R baselines) = 136.77 single-GPU hours.

## 3. W2 arm 2: 16 models x 3 suites, laptop, 10 fresh trials (x10/3)

| protocol | Phase 1 hours (48 runs) | W2 hours |
|---|---|---|
| R | 21.06 | **70.18** |
| D | 11.51 | **38.37** |

- qwen3 share of the Phase 1 hours: R 3.63 h, D 3.82 h.
- Run seed 1234 equals arm 1's, so drifts, faults and prompts are identical to arm 1. Only the sampled-trial seeds differ.
- The greedy trial (1 of 10) therefore repeats arm 1's greedy trial; it is included in the hours above and is 10% of each run.

## 4. W3: added tasks only, 10 trials, laptop

Added tasks: synthetic +200, bfcl_simple +91, bfcl_multiple +9. Hours per run = Phase 1 elapsed x (added/100) x 10/3, summed over 16 models.
This assumes added tasks cost the same per task as the original 100.

| protocol | synthetic | bfcl_simple | bfcl_multiple | total |
|---|---|---|---|---|
| D | 20.79 | 12.40 | 1.29 | **34.48** |
| R | 53.08 | 18.77 | 2.07 | **73.92** |

That is 48 separate added-task runs per protocol.
Optional, not in the totals below: if the same-hardware Kaggle baselines (D 11 models, R 5 models) also get W3 runs, using the Kaggle F5 and R_F5 times as the proxy, that adds D 51.83 h plus R 19.60 h = 71.43 Kaggle single-GPU hours.

### Is merging separate runs safe? (code check)

No blocking problem found in the experiment code. Points, with locations:

- **Randomness is keyed per task, not by position or run composition.**
  - Drift and fault come from `rng_for(seed, task_id, condition)` (`runner.py:347`, `utils.py:13`).
  - So a task gets the same drift, fault and prompt whether it runs in a 100-task or a 300-task run, provided the same `seed` (1234) is used.
  - Trial seeds are per call (`runner.py:370`; `llama_cpp_client.py:416` passes `seed=` to every `create_completion`), so sampling doesn't depend on call order.
- **Precedent:** the Qwen3 F1/F3/F4/F6 runs were run as halves and merged (`scripts/f1_qwen3_bfcl_multiple_split.py`).
  - `scripts/prove_split_equivalence.py` (DEVIATIONS item A) showed one run vs two halves gave byte-identical records.
  - That proof used only gemma2_2b, synthetic, 10 tasks, protocol D. It was not repeated for R (grammar-constrained) or for a Kaggle GPU.
- **Residual risk (not tested):** llama-cpp-python reuses the KV-cache prefix from the previous call (no cache reset in `llama_cpp_client.py`). The first call of each separate run starts from an empty cache, so numerics could differ at the margin.
  - W0 showed identical re-runs in the same order, not across a different split point.
- **Merge mechanics are not automatic:**
  - The analysis loader needs exactly one run directory per (protocol, model, suite). The first full analysis crashed on 2 run dirs (DEVIATIONS 2026-10-15).
  - The existing merge script is specific to Qwen3/F1.
  - `configs/analysis_official_folders.yaml` has `expected_records_per_run: 900`, which would be wrong for 300/191/109-task suites.
  - The run `data` path and `num_tasks` in the manifest differ between the original and the added-task run.
- **Task files:**
  - New task ids must not collide with existing ones.
  - Records are matched on (task_id, condition, drift type, fault type, trial_index), so ids must be unique across the merged set.
  - The 100 original tasks must be byte-identical in the combined file.

## 5. Totals

| workstream | laptop h | Kaggle single-GPU h |
|---|---|---|
| W1 (F6 = D runs left out) | 195.64 | 136.77 |
| W2 (R) | 70.18 | 0 |
| W2 (D) | 38.37 | 0 |
| W3 (D + R, added tasks, laptop only) | 108.40 | 0 |
| **All combined** | **412.58** | **136.77** |

With the optional W3 Kaggle baselines: Kaggle 208.21 h. With 2 GPUs per Kaggle session, wall-clock is about half the single-GPU hours.
