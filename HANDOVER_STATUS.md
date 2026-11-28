# HANDOVER STATUS: versiondrift-agent

Snapshot 2026-11-28. Every number below is read from the file named next to it. "NOT FOUND" = not in any repo file checked. Exploratory items are post hoc and labelled so.

Abbreviations: **D** = default protocol, **R** = robust protocol, **AA** = A/A control (a model vs a rerun of itself), **PC** = positive control, **pair** = adjacent upgrade (old -> new), **decision** = pair x suite.

---

## 1. Study design

| Item | Value | Source |
|---|---|---|
| Models | 16. Mistral 7B v0.1/v0.2/v0.3; Qwen2-7B, Qwen2.5-7B, Qwen3-8B; Llama 3-8B, 3.1-8B; Phi-3-mini, Phi-3.5-mini, Phi-4-mini; Granite 3.0/3.1/3.2 8B; Gemma-2-2b, Gemma-3-4b. Phi parameter counts: NOT FOUND | PLAN.md §2 |
| Format | GGUF, Q4_K_M (Q8_0 for F5, Q2_K for one PC), llama.cpp via llama-cpp-python | PLAN.md §2, §4; docs/model_manifest.md |
| Pairs | 10 adjacent pairs: 4 design (Mistral, Qwen), 6 held-out (Llama, Phi, Granite, Gemma). Size-changing: qwen25->qwen3, gemma2_2b->gemma3_4b | PLAN.md §2 |
| Decisions | 10 pairs x 3 suites = 30 | PLAN.md §8 |
| Suites | synthetic 100 (54 distinct baseline prompts); bfcl_simple 100; bfcl_multiple 100 | PLAN.md §3, PLAN_PHASE2.md W3 |
| W3 extended sets | bfcl_simple 191 (100 + 91), bfcl_multiple 109 (100 + 9); synthetic not extended; D and R only | PLAN_PHASE2.md W3 |
| Conditions | baseline, schema_drift (rename, drop, type mutation, unexpected field; enum drift on synthetic only), fault_reporting (JSON status ok/failed/incomplete + answer) | PLAN.md §3 |
| Stress conditions | schema_drift + fault_reporting, equal weight | DEVIATIONS 2026-10-08 "analysis conventions" |
| Scoring | per record pass/fail (`vdanalysis.loader.record_score`); schema_drift: all 5 components true; fault_reporting: `score` metric. Missing `answer` key = null (strict diagnostic score reported separately) | PLAN.md §3; DEVIATIONS (l) item 3 |
| Stress diff | mean paired success difference new - old over the stress conditions | PLAN.md §4 |
| Point gate | harmful if diff < -0.05, beneficial if > +0.05, else neutral | PLAN.md §4 |
| CI gate | task-level bootstrap, 10,000 reps, seed 1234; harmful if diff < -0.05 AND upper 95% bound < 0; beneficial mirrored | PLAN.md §8 |
| Four-class (S3) | harmful/beneficial = CI-gate label; neutral = 90% interval inside +/-0.05; else inconclusive | DEVIATIONS (e) |

**D vs R (exact differences).** D: max_tokens 256, constrained decoding off, point gate. R: max_tokens 1024 (truncation check), generic-JSON constrained decoding (tool-call conditions only), CI gate, format/semantic failure buckets, clean-ceiling check. Both: native chat template, shared JSON-in-prompt format, n_ctx 4096, Q4_K_M, temperature 0.0 for trial 0 and 0.7 for trials 1-9 (top_p 0.95, top_k 40, min_p 0.05). Sources: PLAN.md §4, §7; EXPLORATORY_flip_examples_full.md §1.

**Factors** (each changed alone from D; PLAN.md §5):

| | Factor | Levels | How |
|---|---|---|---|
| F1 | Output budget | 256 / 1024 | run |
| F2 | Thinking (Qwen3 only) | on / off | run |
| F3 | Prompt format | shared JSON / best per model (native tool template) | run |
| F4 | Constrained decoding | off / generic JSON (full schema cut: DEVIATIONS 2026-10-08) | run |
| F5 | Precision | Q4_K_M / Q8_0 (8B models on Kaggle) | run |
| F6 | Sampling | shared / each model's recommended | run |
| F7 | Parsing | strict / lenient | rescore |
| F8 | Intent rule | strict / relaxed | rescore |
| F9 | Gate rule | point / CI | rescore |
| F10 | Trials | 1 (greedy) / all | subsample |
| F11 | Chat wrapping | legacy / native (Mistral and Qwen only); classed misconfiguration/compound in S4 | run |

**Trials and seeds** (PLAN_PHASE2.md §2):
- Main runs use 10 trials: trial seeds 1234-1243 and temperatures [0.0, 0.7 x 9]. The run seed is 1234 for every run.
- Phase 1 had 3 trials (results_v2, trials 0-2). Phase 2 added trials 3-9 on the laptop (results_v3, merged with trial_offset 3); all 10 Kaggle trials were run fresh.
- Other seeds: A/A arm 2 uses trial seeds 5678-5687; W6 sampling 20261020; BFCL task selection 20260930.

**Controls:**
- A/A, Phase 2: D_AA2 and R_AA2, 16 models x 3 suites = 48 decisions each. Same run seed (same prompts), new trial seeds. Source: PLAN_PHASE2.md W2.
- A/A, Phase 1: R_AA, 18 runs.
- Positive controls (R_PC_Q2K, R_PC_NODESC): models granite32, llama31, mistral_v03, qwen25; 12 decisions each. Source: results_v3/R_PC_* folders.

**Runs and records on disk** (counted 2026-11-28 from `*/parsed_results.jsonl`, excluding `_` folders):

| Root | Runs | Records |
|---|---|---|
| results_v2 (Phase 1; includes audit-only F3/granite30 originals) | 438 | 394,200 |
| results_v3 (Phase 2) | 517 | 1,206,600 |
| **Total** | **955** | **1,600,800** |

results_v3 runs by protocol:

| Protocol | Runs |
|---|---|
| D | 48 |
| D_AA2 | 48 |
| D_KAGGLE | 33 |
| F1 | 48 |
| F2 | 3 |
| F3 | 24 |
| F4_json | 48 |
| F5 | 48 |
| F6 | 18 |
| R | 48 |
| R_AA2 | 48 |
| R_KAGGLE | 15 |
| R_PC_NODESC | 12 |
| R_PC_Q2K | 12 |
| W3_D | 32 |
| W3_R | 32 |

---

## 2. Pre-registration trail

### Tags

All tags are on origin (`git ls-remote --tags`). Hashes give the tag object and the commit where they differ.

| Tag | Commit | Date | What |
|---|---|---|---|
| plan-v1 | 746c67a -> 7a4620b | 2026-10-05 | PLAN.md v1 binding |
| runs-complete | ad78abd -> ab758f8 | 2026-10-15 | all Phase 1 runs complete |
| analysis-complete | 995d8b2 -> 692078d | 2026-10-15 | Phase 1 analysis record final |
| plan-v2 | 9ddd85e | 2026-10-19 | PLAN_PHASE2.md locked |
| plan-v2.1 | 4979c5e | 2026-11-08 | analysis addendum (S1-S9), before any Phase 2 analysis |
| pre-analysis-v2 | dc028d4 | 2026-11-13 | model restore script; code state before analysis |
| pre-analysis-v2.1 | 9654dbd | 2026-11-14 | fix (j); first Phase 2 analysis -> analysis_out_v3 |
| pre-analysis-v2.2 | 8e68388 | 2026-11-14 | fix (k); rerun -> analysis_out_v3_p7 |
| pre-analysis-v2.3 | 73a9017 | 2026-11-14 | fix (m); addendum rerun -> analysis_out_v3/addendum_v2 |
| labels-sample-v1 | 5c3139a | 2026-11-14 | W6 sampling design (l), before the draw |
| plan-granite-thinking | d58bf56 | 2026-11-28 | exploratory granite thinking plan + opt-in code |

### DEVIATIONS.md

**Phase 1 entries** (dated, unlettered). Full one-line list: analysis/exploratory/EXPLORATORY_deviations_table.md rows 1-23.

| Date | Entries |
|---|---|
| 10-06 | F1 qwen3/bfcl_multiple split in two halves; F3 parse-rate causes |
| 10-07 | Granite-3.0 parser fix (rerun into F3_rerun; 28 of 1,800 records change) and its follow-up; F6 per-trial overrides |
| 10-08 | F6 complete (1 greedy mismatch); F4 full-schema level cut; F6 reporting convention; Qwen3 grammar blocks thinking (F4/R confounded for qwen3); analysis conventions |
| 10-09 | F4 complete (qwen3 repetition loop); R_unconstrained mapped to F1; R config check |
| 10-11 | R complete; controls defined |
| 10-12 | controls complete; R_F6/R_F3/F11 defined and tested |
| 10-13 | F5/R_F5 8B on Kaggle; F11 manifest diffs; R_F6/R_F3/F11 complete |
| 10-14 | F5/R_F5 small models complete |
| 10-15 | pre-analysis fixes and one diagnostic quirk |

**Lettered entries:**

| | Date | One line |
|---|---|---|
| (a) | 11-08 (rev. 11-09) | W3 determinism condition = prompts and strict scores 100% identical (R split: parsed 99.67%, raw 99.33%) |
| (b) | 11-08 | S1/S2 under S3 use each decision's observed class |
| (c) | 11-08 | S1.4 p_i = share of task resamples where the two arms' labels differ |
| (d) | 11-08 | F5 noise floor = laptop D vs D_AA2, a proxy for Kaggle noise |
| (e) | 11-08 | S3 neutral = 90% task-cluster bootstrap interval inside +/-0.05 |
| (f) | 11-08 | S9 specification (statsmodels 0.15.0, BinomialBayesMixedGLM, fit_vb, seed 1234) |
| (g) | 11-08 | Kaggle upload order K02, K03, K07, K05, K09, K06, K01, K10, K08, K04 |
| (h) | 11-08 | W3 gate no longer waits for W1_kaggle |
| (i) | 11-08 | descriptive S3 row on synthetic with prompt-cluster bootstrap |
| (j) | 11-14 | audit-only ban on F3/granite30 scoped to Phase 1 roots |
| (k) | 11-14 | P7 skipped by a bug; now on w3.suites only (found after first results) |
| (l) | 11-14 | W6 design: frame, strata 33/33/33/33/34/34, verdict, unsure handling, blinding |
| (m) | 11-14 | S1 excl-qwen table: point estimates recomputed on reduced data |

No entry after (m) exists in DEVIATIONS.md.

---

## 3. Main pre-registered results

Main tables are in `analysis_out_v3_p7/` (report: `analysis_out_v3_p7/analysis_report.md`). The current addendum is `analysis_out_v3/addendum_v2/`.

### Verdict counts, 30 decisions

Sources: `analysis_out_v3_p7/decisions_all_protocols.csv` and `analysis_out_v3/addendum_v2/s3_classes.csv`.

| Protocol | Point gate (H / N / B) | CI gate (H / N / B) | Four-class (H / N / B / Inconclusive) |
|---|---|---|---|
| D | 4 / 19 / 7 | 4 / 19 / 7 | 4 / 9 / 7 / 10 |
| R | 3 / 18 / 9 | 3 / 18 / 9 | 3 / 8 / 9 / 10 |

The inconclusive share is 33.3% for both D and R (`s3_shares.csv`).

### Phase 2 hypotheses

Source: `analysis_out_v3_p7/analysis_report.md`.

| | Result | Verdict |
|---|---|---|
| P1 | 13/30 = 43.3% [25.5, 62.6] flip under >= 1 of F1-F10 (threshold 20%). Size-preserving 9/24, size-changing 4/6 | supported |
| P2 | 9 of 13 Phase 1 flips replicate (threshold 7) | supported |
| P3 | R A/A false alarm 2/48 = 4.2% [0.5, 14.3] (threshold 5%) | supported |
| P4 | Q2_K detected 10/12 = 83.3% (threshold 90%) | **not supported** |
| P5 | full-score gate 6 vs stress-only 3 on NODESC | supported |
| P6 | F5 same-hardware replicates 3 of 8 (threshold 4) | **not supported** |
| P7 | D: 0/20 differ. R: 1/20 (phi35_mini->phi4_mini bfcl_simple, neutral->beneficial) | descriptive |

**Descriptive results:**
- D A/A false-alarm rate: 1/48 = 2.1%.
- Hardware noise: laptop and Kaggle D labels agree in 21/21 pair decisions (`hw_noise_pairs.csv`).
- F5 shift exceeds the A/A 95th-percentile bound (0.0398) in 6/48 model-suite cells and exceeds the A/A maximum (0.052) in 3/48 (`f5_shift_vs_aa.csv`).
- 6 new flips not seen in Phase 1 (report section "New flips").

### Phase 1 hypotheses

Source: `analysis_out/hypotheses.csv`, 3 trials.

| | Result | Verdict |
|---|---|---|
| H1 | 13/30 | supported |
| H2 | format 11.1% vs other 14.8% | not supported |
| H3 | median \|diff\| of flipping vs non-flipping decisions: 0.038 vs 0.037 | not supported |
| H4 | R disagrees less than D, pooled 6/36 vs 14/36 | supported |
| H5 | AA 5.6%, PC detection 54.2% | not supported |

### Factor flip rates vs A/A

`flip_rates_by_factor.csv` (main variants):

| Factor | Flips / decisions |
|---|---|
| F1 | 3/30 |
| F2 | 3/3 |
| F3 | 3/9 (all variants: 10/21) |
| F4 | 3/27 |
| F5 | 5/30 |
| F6 | 0/12 |
| F7 | 0/30 |
| F8 | 0/30 |
| F9 | 0/30 |
| F10 | 4/30 |

Rerun (A/A) flips, from `s1_rerun_rates.csv`:

| Arm | Flips | 95% CI |
|---|---|---|
| D vs D_AA2 | 2/30 = 6.7% | [0.8, 22.1] |
| R vs R_AA2 | 5/30 = 16.7% | [5.6, 34.7] |

**S1 excess over rerun noise, Holm-corrected** (`addendum_v2/s1_factors.csv`, generation factors only):

| Factor | Excess e_F | 95% CI | Holm p |
|---|---|---|---|
| F1 | +0.033 | [-0.267, 0.233] | 1.0 |
| F2 | +1.000 | [1.000, 1.000] | **0.0011** |
| F3 | +0.333 | [0.000, 0.667] | 1.0 |
| F4 | +0.037 | [-0.233, 0.125] | 1.0 |
| F5 | +0.100 | [-0.100, 0.200] | 1.0 |
| F6 | 0.000 | [-0.200, 0.111] | 1.0 |
| F11 | +0.083 | [-0.333, 0.500] | 1.0 |

**Only F2 survives.** Excluding qwen25->qwen3 (`s1_factors_excl_qwen25_qwen3.csv`), no factor survives (all Holm p = 1.0) and F2 has 0 decisions.

### Headline, S1

| | Observed share with >= 1 generation flip | Expected noise share | Excess | Source |
|---|---|---|---|---|
| All decisions | 0.500 | 0.3215 | **+17.8 pts** | `addendum_v2/s1_headline.csv` |
| Excluding qwen25->qwen3 | 44.4% | 35.5% | +8.9 pts | EXPLORATORY_S1_headline_excl_qwen.md (exploratory) |

S4 headline (`s4_headline.csv`):

| Factor set | Flipped decisions |
|---|---|
| Reasonable factors F1-F10 | 13/30 (43.3%) |
| All factors incl. F11 | 15/30 (50.0%) |

### Power and variance (S6)

MDE at 80% power and power at delta 0.05, 10 trials and 100 tasks, from `s6_projection.csv` (B_between from all trials):

| Suite | MDE | Power at 0.05 |
|---|---|---|
| synthetic | 0.058 | 0.68 |
| synthetic, clusters (54) | 0.067 | 0.55 |
| bfcl_simple | 0.066 | 0.57 |
| bfcl_simple, 191 tasks | 0.047 | 0.84 |
| bfcl_multiple | 0.066 | 0.56 |
| bfcl_multiple, 109 tasks | 0.063 | 0.60 |

Variance split, from `s6_components.csv`:

| Suite | V_observed | sigma2_sampling | B_between |
|---|---|---|---|
| synthetic | 0.0427 | 0.0390 | 0.0392 |
| bfcl_simple | 0.0548 | 0.0520 | 0.0501 |
| bfcl_multiple | 0.0555 | 0.0512 | 0.0509 |

A split labelled "tasks vs reruns" as a share: NOT FOUND. Only these components exist.

### W3 extended-task effect

- P7 (pre-registered, descriptive): see the table above.
- Exploratory S3 on the full task set (EXPLORATORY_S3_W3_tasks.md):
  - inconclusive falls from 14/40 to 10/40;
  - 4 decisions move out of inconclusive;
  - none moves in.

### qwen3 dose-response

Source: EXPLORATORY_qwen3_dose.md (exploratory).

| Suite | D (think, 256) | F1 (think, 1024) | F2 (no think) |
|---|---|---|---|
| synthetic | -0.112 harmful | +0.039 neutral | +0.084 beneficial |
| bfcl_simple | -0.354 harmful | +0.013 neutral | +0.071 beneficial |
| bfcl_multiple | -0.480 harmful | -0.019 neutral | +0.054 beneficial |

qwen3 truncated share under D: 13.5% (synthetic), 39.0% (bfcl_simple), 55.1% (bfcl_multiple).

### Positive controls, 10 trials

Source: `analysis_out_v3_p7/analysis_report.md`.

| Control | Primary gate | Full-score gate |
|---|---|---|
| Q2_K | 10/12 (83.3%) | 9/12 |
| NODESC | 3/12 (25.0%) | 6/12 (50.0%) |

### Addendum S1-S9

All files in `analysis_out_v3/addendum_v2/`.

| | Result |
|---|---|
| S1 | Headline +17.8 pts; only F2 survives Holm (above) |
| S2 | Factor flips are boundary crossings, except F2, whose 3/3 flips are sign reversals. Rerun flips (D 2, R 5) are all boundary crossings (`s2_factor_flips.csv`, `s2_rerun_flips.csv`) |
| S3 | Inconclusive share: D 33.3%, R 33.3%, D_AA2 40.0%, R_AA2 50.0%. Under S3, rerun flips are D 6/30 and R 8/30 (`s3_shares.csv`, `s3_rerun_flips.csv`). Synthetic cluster row: D same class in 10/10 |
| S4 | F1-F10 classed reasonable; F11 misconfiguration_or_compound |
| S5 | Failure-type shares per protocol x model x suite x condition (`s5_shares.csv`); no single summary number |
| S6 | Power and MDE (above) |
| S7 | McNemar gate agrees with the point gate in D 93.3% and R 83.3% of decisions |
| S8 | Reference-verdict check on 9 decisions. Agreement: D 7/9, R 7/9, F10 8/9, F3 0/3 |
| S9 | 15 fits: 10 VB-converged; sign agrees with S1 direction in 14/15; F4 skipped ("protocol not in config") |

---

## 4. Exploratory results (all post hoc, not pre-registered, existing data only)

Files are in `analysis/exploratory/`.

### item_level_flips

Source: `EXPLORATORY_item_level_flips.md`.

Churn over 600 questions per pair:

| Pair | D net | D churn | R churn |
|---|---|---|---|
| mistral_v01->v02 | -38 | 23.0% | 18.7% |
| mistral_v02->v03 | +56 | 17.0% | 14.0% |
| qwen2->qwen25 | +93 | 27.8% | 27.8% |
| qwen25->qwen3 | -211 | 44.8% | 14.8% |
| llama3->llama31 | -18 | 15.3% | 16.0% |
| phi3->phi35 | -10 | 15.3% | 15.7% |
| phi35->phi4 | +14 | 17.0% | 17.7% |
| granite30->31 | +5 | 12.5% | 13.3% |
| granite31->32 | +14 | 4.7% | 5.2% |
| gemma2->gemma3 | +12 | 11.0% | 10.5% |

Failure types of the "got worse" questions:

| Protocol | Got worse | Unparsed | Wrong status | Wrong arguments | Wrong tool | Fabricated |
|---|---|---|---|---|---|---|
| D | 607 | 298 (234 of them qwen3) | 156 | 148 | 4 | 1 |
| R | 395 | 73 | 157 | 158 | 4 | 3 |

### flip_examples_full

Source: `EXPLORATORY_flip_examples_full.md`.
- `<think>` appears in qwen3 only: D 6,300/6,300 outputs; R 2,100/6,300 (fault_reporting only).
- Of the 240 qwen3 "got worse" questions, 208 hit the 256-token limit in at least 6 of 10 trials.
- Of their 1,938 failing trials, 1,889 (97%) were cut off.

### wrong_calls

Source: `EXPLORATORY_wrong_calls.md`. The reference verdict is the A/A arm's four-class verdict; inconclusive references are excluded (D 18 and R 15 decisions scored).

| Method | D wrong | R wrong |
|---|---|---|
| 1 trial, forced call | 18.3% | 19.3% |
| 3 trials pooled | 14.8% | 15.6% |
| 5 trials pooled | 13.9% | 13.3% |
| 10 trials pooled | 11.1% | 13.3% |
| 3 trials + inconclusive allowed | 5.6% (13.0% inconclusive) | 6.7% (13.3% inconclusive) |
| 10 trials + inconclusive allowed | 0.0% (11.1% inconclusive) | 6.7% (6.7% inconclusive) |

### threshold_sensitivity

Source: `EXPLORATORY_threshold_sensitivity.md`; the ±0.03 column was corrected 2026-11-24.

| | ±0.03 | ±0.05 | ±0.07 |
|---|---|---|---|
| Decisions with >= 1 factor flip | 19 | 13 | 9 |
| Factor flips in total | 33 | 21 | 13 |
| D rerun flips | 9 | 2 | 2 |
| R rerun flips | 9 | 5 | 0 |
| D inconclusive | 17 | 10 | 5 |
| R inconclusive | 15 | 10 | 8 |

### pseudo_aa

Source: `EXPLORATORY_pseudo_aa.md`.

**What it measures.** For each model x suite, the 20 trials of the main arm and the A/A arm are pooled, then split at random 2,000 times into two 10-trial arms; each arm keeps one greedy trial. The **pseudo-A/A flip rate** is the mean, over decisions, of the share of splits in which the two arms get different point-gate labels. This is trial noise only (no task resampling), seed 1234.

| Protocol | Pseudo-A/A flip rate | 95% CI over pairs | Observed rerun flips |
|---|---|---|---|
| D | 11.1% | 4.0-18.4% | 2/30 |
| R | 14.0% | 3.9-25.4% | 5/30 |

### Other analyses

| Analysis | Key numbers | File |
|---|---|---|
| equivalence_bounds | 95% upper bound on the excess flip rate, all pairs: F1 +16.7, F2 +100, F3 +50, F4 +10, F5 +16.7, F6 +6.7, F11 +41.7 pts. Excluding qwen: F1 -3.7 pts | `EXPLORATORY_equivalence_bounds.md` |
| headline_cluster | Pair bootstrap: +17.8 pts [-1.0, +41.6], P = 0.034. Excluding qwen: +8.9 [-4.1, +25.3] | `EXPLORATORY_headline_cluster.md` |
| flip_vs_threshold | Logistic slopes are n.s. except R rerun (-3.4, p = 0.029, near separation) | `EXPLORATORY_flip_vs_threshold.md` |
| r_vs_d_noise | Expected rerun flips D 15.1%, R 11.8%. Median distance to the boundary D 3.53, R 2.35 pts (Wilcoxon p = 0.012) | `EXPLORATORY_r_vs_d_noise.md` |
| S1_headline_excl_qwen | +17.8 [+2.0, +34.4] all; +8.9 [-5.1, +24.2] excluding qwen (decision bootstrap) | `EXPLORATORY_S1_headline_excl_qwen.md` |
| S3_W3_tasks | 4 of 14 inconclusive decisions become definite on the full task set; 0 classes change otherwise | `EXPLORATORY_S3_W3_tasks.md` |
| boundary check | 4,450 comparisons. At ±0.05: 58 on the boundary, 0 mislabelled. At ±0.07: 0. At ±0.03: 5 float artifacts (2 corrected in threshold table) | `NOTE_boundary_check.md` |
| deviations_table | Entries #0-36, one line each | `EXPLORATORY_deviations_table.md` |

### Granite thinking check

Plan: `EXPLORATORY_PLAN_granite_thinking.md` (tag plan-granite-thinking). Results: `EXPLORATORY_granite_thinking.md`. Arm think256, trials 0-2, 1,800 outputs; data in `results_exploratory/granite_thinking/think256/`.

| | granite32 thinking ON | qwen3 (D, trials 0-9) |
|---|---|---|
| Cut-off share (criterion a) | 0.4% (8/1,800) | 40.6% (2,439/6,000) |
| Median / 90th percentile / max tokens | 96 / 140 / 256 | 212 / 256 / 256 |

qwen3 trials 0-2 only: cut-off 40.0%, median 211 tokens.

Other granite32 numbers:
- Unparsed (secondary): 3.8%. 62 of the 69 are a number given as `answer`.
- Verdict granite31 -> granite32 (thinking ON): point gate neutral on all 3 suites; CI gate neutral on all 3.
- Four-class: synthetic and bfcl_simple inconclusive, bfcl_multiple neutral.
- Criterion (b): mean change -0.048, no suite moves toward harmful.
- **Branch: stop** (a fails). No 10-trial extension and no 1024 arm.

### qwen3 strict rescoring

- 12,000 stress records rescored (qwen25 + qwen3, D).
- Main rule reproduces the stored scores: 0 differences.
- Strict policy parses 86 qwen3 records differently; 83 of them change parse status or score. qwen25: 0.

| Suite | Main-rule diff | Strict diff | Labels (both rules, all gates) |
|---|---|---|---|
| synthetic | -0.112 | -0.124 | harmful |
| bfcl_simple | -0.354 | -0.368 | harmful |
| bfcl_multiple | -0.480 | -0.491 | harmful |

qwen3 unparsed share: main rule 39.2%, strict 40.6%.

### lm-evaluation-harness default

lm-evaluation-harness 0.4.13 uses `max_gen_toks` = 256 by default (HF, vLLM, API backends). Checked in the 0.4.13 wheel; stated in `EXPLORATORY_granite_thinking.md`.

---

## 5. Code and reproducibility

### Key folders

| Folder | Contents |
|---|---|
| `upgradecanary/` | Harness: runner, parsing, evaluator, perturbations, llama.cpp client |
| `vdanalysis/` | Analysis: Phase 1, `phase2/`, `phase2/addendum/` S1-S9 |
| `scripts/phase2/` | Run tooling: run_laptop, Kaggle worker and import, W6 sample/build/merge |
| `scripts/exploratory/` | 14 analyses + `_common.py` + `run_all.py` + `boundary_check.py` + granite_thinking_run/analyze |
| `configs/` | `analysis_phase2.yaml`, `analysis_phase1_regression.yaml`, `phase2/*.json` manifests |
| `tests/` | Test suite |

### Tests

493 passed. This comes from a full pytest run on 2026-11-28 in this working tree; no file records it.

### Commands

From `analysis/phase2/README.md` and `run_addendum.py`.

```
python -m vdanalysis.phase2.rescore_v3 --config configs/analysis_phase2.yaml --factor F7   (and F8)
python -m vdanalysis.phase2.run_phase2 --config configs/analysis_phase2.yaml --out <folder> [--report <md>] [--labels <csv>]
python -m vdanalysis.phase2.addendum.run_addendum --config configs/analysis_phase2.yaml --out <folder> --rerun D:D_AA2 --rerun R:R_AA2
python -m vdanalysis.phase2.regression --config configs/analysis_phase1_regression.yaml --reference analysis_out --out <folder>
python -m scripts.exploratory.run_all          # regenerates exploratory files into temp and compares (granite_thinking not included)
python -m scripts.exploratory.boundary_check --out <folder>
python -m scripts.exploratory.granite_thinking_analyze --arm think256 --out analysis/exploratory
```

On this machine, `analysis/audit/_dll_preload.py` must run before `import llama_cpp` (the run/analyze scripts do it).

### Output folders

| Folder | Holds |
|---|---|
| `analysis_out/` | Phase 1 analysis (H1-H5) |
| `analysis_out_v3/` | First Phase 2 run (tag pre-analysis-v2.1; P7 missing by bug (k)) + `regression_phase1/` |
| `analysis_out_v3/addendum/` | First addendum run (pre-analysis-v2.2). Differs from addendum_v2 only in `s1_factors_excl_qwen25_qwen3.csv` and `_meta.csv` |
| `analysis_out_v3/addendum_v2/` | **Current addendum** (pre-analysis-v2.3, fix (m)) |
| `analysis_out_v3_p7/` | **Current main Phase 2 tables + report** (pre-analysis-v2.2). Differs from `analysis_out_v3/` only in `p7.csv` |
| `rescored_v3/` | F7/F8 rescoring of Phase 2 records |
| `analysis/exploratory/` | Exploratory reports |
| `results_exploratory/` | Granite thinking runs (pilot, think256) |

### OneDrive backups

Location: `C:\Users\Ibo\OneDrive\upgradecanary_backups\` (98 files):
- results_v2 incremental zips, 2026-10-05 to 10-15 (last: `results_v2_backup_2026-10-15_runs_complete.zip`);
- results_v3 laptop zips up to run436 (2026-11-12) and 6 Kaggle session zips (81 runs);
- W0 determinism zip;
- 3 analysis zips (v2.1, v2.2/p7, addendum_v2);
- granite thinking pilot and think256 zips (2026-11-28).

No backup was found for `analysis/exploratory/`; those files are in git, except the uncommitted granite files.

---

## 6. W6 human labels

| Item | State |
|---|---|
| Design | DEVIATIONS (l): D and R main runs, stress conditions, 16 models, 10 trials. 6 strata (suite x pass/fail), 200 items (33/33/33/33/34/34). Seed 20261020. Two raters, blind. Labels correct / wrong / unsure; kappa with unsure as a class and with unsure excluded |
| Code | `scripts/phase2/w6_sample.py`, `w6_build.py`, `w6_merge.py`; tests `tests/test_phase2_w6_sample.py` |
| Rater files (tracked) | `w6_labels/for_raters/LABELING_GUIDE.md`, `labels_rater1.xlsx`, `labels_rater2.xlsx` |
| Rater files (untracked) | `labels_rater1.csv`, `labels_rater2.csv` (dated 2026-11-22), 200 rows each. **Label column filled: 0 of 200 in both** |
| Private (git-ignored, never shown to raters) | `w6_labels/private/labels_key.csv`, `sample.json`, `leak_check.json`. The leak check finds 1 vendor-name hit ("Google", W6-047, in the request text) |
| Merge | `python -m scripts.phase2.w6_merge --key w6_labels/private/labels_key.csv --rater rater1=<filled xlsx> --rater rater2=<filled xlsx> --out-dir w6_labels/merged`, then `run_phase2 ... --labels <file>` for each output |
| Status | Sample drawn and files built; no labels returned. Second rater: "TBD" in PLAN_PHASE2.md; no file names one |

---

## 7. Git state

| Item | State |
|---|---|
| Branch | main, in sync with origin/main (no unpushed commits) |
| Last commit | d58bf56 "Exploratory plan and opt-in thinking support for granite32 thinking-on check" |
| Last tag | plan-granite-thinking (d58bf56); all 11 tags on origin |
| Modified | `scripts/exploratory/granite_thinking_run.py` (`--trials` option) |
| Untracked | `scripts/exploratory/granite_thinking_analyze.py`; `analysis/exploratory/EXPLORATORY_granite_thinking.md`, `..._records.csv`, `..._qwen3_records.csv`; `results_exploratory/` (not git-ignored); `w6_labels/for_raters/labels_rater1.csv`, `labels_rater2.csv`; `HANDOVER_STATUS.md` |

---

## 8. Known issues and caveats (from the files)

- **Parser takes the first valid JSON anywhere in the output.** It does this even inside thinking; no D or R config strips thinking. For qwen3 D, the strict policy parses 86 records differently, with no label change (`EXPLORATORY_granite_thinking.md`).
- **R and F4 are confounded for qwen3.** The JSON grammar blocks thinking on tool-call conditions (DEVIATIONS 2026-10-08). R thinking: 0/4,200 tool-call outputs vs 2,100/2,100 fault_reporting outputs (`EXPLORATORY_flip_examples_full.md`).
- **qwen25->qwen3 drives the headline.** Without it, the excess is +8.9 pts with a CI that includes 0, and no factor survives Holm.
- **F3/granite30 in results_v2 is audit-only** (pre-fix parser). The analysis reads `F3_rerun` / results_v3. 28 records differ from the rescore (DEVIATIONS 2026-10-07, (j)).
- **F5 noise floor is a laptop proxy for Kaggle** (DEVIATIONS (d)).
- **Phase 1 F5 confounded quantization with hardware.** Phase 2 uses same-hardware baselines.
- **Exploratory scripts were first run as scratch scripts** and later rewritten into `scripts/exploratory/` (commit 884044b). `run_all.py` regenerates and compares them. Hand-written paragraphs in `scripts/exploratory/_text/` are not checked against data.
- **Floating-point boundary:** pipeline labels at ±0.05 are exact (0 of 4,450 differ). Any other threshold needs rounding (`NOTE_boundary_check.md`).
- **BFCL-multiple selection is biased** toward shorter multi-tool tasks (3500-char budget; PLAN.md §3).
- **Synthetic has 54 distinct baseline prompts for 100 tasks.** The cluster bootstrap is reported descriptively.
- **Decisions are not independent** (pairs share models). Several exploratory intervals ignore task-level uncertainty, as each file's caveat states.
- **Model files were deleted 2026-11-13** (`docs/deleted_models_2026-11-13.md`). granite32 and Qwen3-8B were restored 2026-11-28 with `scripts/restore_models.py` (SHA-256 verified).
- **Commit `d58bf56` contains opt-in code** (`parsing.thinking_policy`, `model.chat_template_kwargs`). Defaults are unchanged; a regression check of all stored records found 0 differences vs HEAD. No file records that check: the result is in session output only.

---

## 9. Open items

1. **W6:** labels not filled (0/200 per rater); second rater not named; merge and kappa not run.
2. **W5 (closed-model pairs, $40 cap):** no run files exist. The STATUS_REPORT_2026-11-07 says "not run"; no later file changes that.
3. **PLAN_PHASE2.md §8 checklist:** 4 of 5 boxes unchecked in the file (tests/configs match, plan-v2 tag, OSF deposit, DEVIATIONS pointer). The plan-v2 tag and the DEVIATIONS pointer commit exist in git. OSF deposit status: NOT FOUND (an `osf_deposit/` folder exists).
4. **Granite thinking:** the plan's stop branch applies. Write-up and commit of the uncommitted files are pending.
5. **W0 Part C** (optional Kaggle F5 re-run, descriptive): not found as done.
6. **GPU deadline 2026-12-10** (PLAN_PHASE2.md §6). Unfinished GPU work is reported as not done.
7. **Paper:** `paper_story.md` exists; manuscript status NOT FOUND.
