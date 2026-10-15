# Full analysis report (PLAN.md sections 8-9)

Pre-registered plan: `PLAN.md` sections 8-9. Deviations/analysis rules: `DEVIATIONS.md` (stress-diff definition, F6/F3 main-count scoping, Qwen3 F4/R labeling, control model lists, R_unconstrained==F1 mapping, parser decisions). Pipeline: `vdanalysis` (`python -m vdanalysis.run_analysis --config configs/analysis_official_folders.yaml --out analysis_out`), one pass, 17 tables, 0 warnings, 0 missing runs (after two pre-run fixes -- see "Bugs found" below). Gate: point ±0.05; CI gate cluster bootstrap, 10,000 reps, seed 1234. Stress conditions: schema_drift + fault_reporting, equal-weight average.

All 17 raw tables are in `analysis_out/*.csv` (plus `analysis_out/report.md`, the pipeline's own auto-generated summary, and `analysis_out/hwcheck/*.csv`). This document is the narrative report requested, in the requested order. **No upgrade verdicts beyond what the pre-registered gate itself computes; no pair differences invented beyond the pipeline's own output.**

---

## a. D verdicts: all 10 pairs x 3 suites

Stress diff = equal-weight average of the schema_drift and fault_reporting paired diffs. CI = 10,000-rep task-level cluster bootstrap. Source: `analysis_out/decisions_D.csv`.

| Pair | Suite | Stress diff | CI (95%) | Point label | CI label |
|---|---|---|---|---|---|
| mistral_v01->mistral_v02 | synthetic | -0.0383 | [-0.0767, -0.0017] | neutral | neutral |
| mistral_v01->mistral_v02 | bfcl_simple | -0.0583 | [-0.1133, -0.0050] | harmful | harmful |
| mistral_v01->mistral_v02 | bfcl_multiple | -0.0833 | [-0.1433, -0.0233] | harmful | harmful |
| mistral_v02->mistral_v03 | synthetic | +0.0283 | [-0.0133, +0.0700] | neutral | neutral |
| mistral_v02->mistral_v03 | bfcl_simple | +0.1167 | [+0.0633, +0.1700] | beneficial | beneficial |
| mistral_v02->mistral_v03 | bfcl_multiple | +0.1417 | [+0.0950, +0.1900] | beneficial | beneficial |
| qwen2->qwen25 | synthetic | +0.1833 | [+0.1250, +0.2433] | beneficial | beneficial |
| qwen2->qwen25 | bfcl_simple | +0.1200 | [+0.0500, +0.1917] | beneficial | beneficial |
| qwen2->qwen25 | bfcl_multiple | +0.1383 | [+0.0700, +0.2033] | beneficial | beneficial |
| qwen25->qwen3 **(size-changing)** | synthetic | -0.0833 | [-0.1417, -0.0250] | harmful | harmful |
| qwen25->qwen3 **(size-changing)** | bfcl_simple | -0.3400 | [-0.4133, -0.2650] | harmful | harmful |
| qwen25->qwen3 **(size-changing)** | bfcl_multiple | -0.5000 | [-0.5667, -0.4317] | harmful | harmful |
| llama3->llama31 | synthetic | -0.0083 | [-0.0583, +0.0400] | neutral | neutral |
| llama3->llama31 | bfcl_simple | -0.0417 | [-0.0883, +0.0033] | neutral | neutral |
| llama3->llama31 | bfcl_multiple | +0.0117 | [-0.0367, +0.0583] | neutral | neutral |
| phi3_mini->phi35_mini | synthetic | -0.0533 | [-0.0950, -0.0133] | harmful | harmful |
| phi3_mini->phi35_mini | bfcl_simple | +0.0133 | [-0.0400, +0.0683] | neutral | neutral |
| phi3_mini->phi35_mini | bfcl_multiple | -0.0367 | [-0.0933, +0.0183] | neutral | neutral |
| phi35_mini->phi4_mini | synthetic | +0.0200 | [-0.0300, +0.0717] | neutral | neutral |
| phi35_mini->phi4_mini | bfcl_simple | +0.0333 | [-0.0133, +0.0800] | neutral | neutral |
| phi35_mini->phi4_mini | bfcl_multiple | +0.0650 | [+0.0117, +0.1217] | beneficial | beneficial |
| granite30->granite31 | synthetic | +0.0217 | [-0.0283, +0.0733] | neutral | neutral |
| granite30->granite31 | bfcl_simple | +0.0367 | [0.0000, +0.0750] | neutral | neutral |
| granite30->granite31 | bfcl_multiple | +0.0033 | [-0.0383, +0.0450] | neutral | neutral |
| granite31->granite32 | synthetic | +0.0217 | [0.0000, +0.0450] | neutral | neutral |
| granite31->granite32 | bfcl_simple | +0.0133 | [-0.0083, +0.0367] | neutral | neutral |
| granite31->granite32 | bfcl_multiple | +0.0283 | [+0.0050, +0.0550] | neutral | neutral |
| gemma2_2b->gemma3_4b **(size-changing)** | synthetic | -0.0150 | [-0.0383, +0.0067] | neutral | neutral |
| gemma2_2b->gemma3_4b **(size-changing)** | bfcl_simple | +0.0283 | [-0.0200, +0.0767] | neutral | neutral |
| gemma2_2b->gemma3_4b **(size-changing)** | bfcl_multiple | +0.0483 | [+0.0033, +0.0917] | neutral | neutral |

Point and CI labels agree on all 30/30 D decisions (no CI-vs-point disagreement under D itself).

---

## b. Controls first (H5)

Source: `analysis_out/controls_summary.csv`, `controls.csv`.

| Control | Models | n decisions | Metric | Value | Threshold | Pass/fail |
|---|---|---|---|---|---|---|
| A/A (R vs R_AA) | mistral_v02, qwen2, qwen25 (design) + llama31, phi35_mini, granite31 (held-out) | 18 | False-alarm rate | **5.56%** (1/18) | <= 5% | **FAIL** (marginal -- exactly 1 decision, llama31/bfcl_multiple, flipped neutral->harmful) |
| Positive control, Q2_K (R vs R_PC_Q2K) | mistral_v03, qwen25 (design) + llama31, granite32 (held-out) | 12 | Detection rate | **83.3%** (10/12) | >= 90% | **FAIL** |
| Positive control, no-description (R vs R_PC_NODESC) | same 4 models | 12 | Detection rate | **25.0%** (3/12) | >= 90% | **FAIL** |
| **H5 overall** (pooled positive-control detection, per the pipeline's own hypothesis row) | | 18 (A/A) + 24 (pooled PC) | false-alarm 5.56%, pooled detection 54.17% | | both conditions | **FAIL** |

All three legs of H5 fail. The A/A failure is a single marginal decision (1/18); the positive-control failures are not marginal -- Q2_K catches 10/12 damaged pairs but misses 2, and no-description catches only 3/12, far short of 90%.

---

## c. H1

**13 of 30 (43.3%) decisions change label under at least one factor level (F1-F10).** Threshold: >= 20%. **PASS.**

By pair-subset variant (reported for completeness, not required for the headline): size-preserving pairs 9/24 (37.5%), size-changing pairs 4/6 (66.7%) -- both also pass 20% on their own.

---

## d. H2: format factors (F1, F2, F4, F7) vs the rest (F3, F5, F6, F8)

**Hypothesis: FAILS.** Format factors do not flip more than the others -- they flip less.

Per-factor flip counts/rates (main variant, all pairs; source: `analysis_out/flip_rates_by_factor.csv`):

| Factor | Group | n decisions | n flips | Flip rate |
|---|---|---|---|---|
| F1 | format | 30 | 3 | 10.0% |
| F2 | format | 3 | 3 | 100.0% (Qwen3-only, n=3) |
| F4 | format | 27 | 3 | 11.1% |
| F7 | format | 30 | 1 | 3.3% |
| F3 | other | 9 (main: both-native pairs) | 2 | 22.2% |
| F5 | other | 30 | 8 | 26.7% |
| F6 | other | 12 (main: sampling-changed pairs) | 1 | 8.3% |
| F8 | other | 30 | 1 | 3.3% |

Pooled (pipeline's own hypothesis-row numbers, `main/all_pairs`): format factors 11.1% (10/90, pooling the "main" n for F1/F2/F4/F7) vs other factors 14.8% (12/81) -- the "other" group flips *more*, the opposite of H2's claim. **FAIL.**

---

## e. H3: |effect| of flipping vs stable decisions

**Hypothesis: FAILS.** Flipping decisions have a slightly *larger*, not smaller, median |stress diff| under D.

Median |stress diff|, flipped (n=13): **0.0383**. Median |stress diff|, never-flipped (n=17): **0.0367**. H3 claims flipped decisions should have the *smaller* median -- the actual direction is reversed (though the two medians are close, 0.0383 vs 0.0367). **FAIL**, consistently across all 3 pair-subset variants (all_pairs, size_preserving, size_changing all fail).

---

## f. H4: R vs D disagreement on held-out pairs, per nuisance factor

**All H4 rows PASS** -- R disagrees less than D does, for every nuisance factor individually and pooled, in both the "primary" and "all held-out pairs" framing. Source: `analysis_out/hypotheses.csv`.

| Factor | Variant | R disagreement | D disagreement | Pass? |
|---|---|---|---|---|
| F3 | primary (both-native held-out pairs) | 25.0% (3/12) | 58.3% (7/12) | PASS |
| F3 | all held-out | 16.7% (3/18) | 58.3% (7/12) | PASS |
| F3 | both-native only | 0.0% (0/6) | 33.3% (2/6) | PASS |
| F5 | primary | 16.7% (3/18) | 33.3% (6/18) | PASS |
| F5 | all held-out | 16.7% (3/18) | 33.3% (6/18) | PASS |
| F6 | primary | 0.0% (0/6) | 16.7% (1/6) | PASS |
| F6 | all held-out | 0.0% (0/18) | 5.6% (1/18) | PASS |
| **Pooled** | primary | 16.7% (6/36) | 38.9% (14/36) | **PASS** |
| **Pooled** | all held-out | 11.1% (6/54) | 29.2% (14/48) | **PASS** |

H4 is the strongest-supported hypothesis in this study: R's robustness machinery (larger budget + constrained decoding) measurably and consistently reduces how often the nuisance factors (native-template prompting, Q8_0 quantization, recommended sampling) flip a verdict, for every one of F3/F5/F6 individually and pooled.

---

## g. Format vs. semantic failure split

Source: `analysis_out/failure_split.csv` (1,844 protocol/model/suite/condition rows; pooled here, not reproduced row-by-row).

**Under D, pooled over all 48 model/suite runs x 3 conditions (43,200 records):** format failures 3.87% (1,674), semantic failures 8.81% (3,808). By condition:
- baseline: format 2.42%, semantic 5.40%
- schema_drift: format 3.47%, semantic 12.90%
- fault_reporting: format 5.74%, semantic 8.14%

Semantic failure is consistently the larger bucket under D, most pronounced under schema_drift (where a model parses the call correctly but gets the drift-adapted arguments wrong). Across *all* protocols pooled (524,700 records, every factor level included): format 3.17%, semantic 9.46% -- the same pattern holds once F3's native-template and F4/R's grammar-constrained runs are included (format failures drop slightly as a share, since constrained decoding structurally prevents most of them; semantic failures are untouched by that mechanism and so become relatively larger).

No anomalous rows (0 cases of format+semantic exceeding the record count, 0 negative counts -- checked directly across all 1,844 rows).

---

## h. Special-case items

**Size-changing pairs**, reported separately throughout (`analysis_out/size_changing_decisions.csv`): qwen25->qwen3 and gemma2_2b->gemma3_4b. qwen25->qwen3 is harmful under D on all 3 suites (and under most other protocols -- F2/thinking-off is the one exception, flipping it beneficial/neutral, consistent with Qwen3's known thinking-budget sensitivity). gemma2_2b->gemma3_4b is neutral under D on all 3 suites and stays neutral almost everywhere else.

**Qwen3 F4/R labeling** (`analysis_out/qwen3_f4_vs_f2.csv`): Qwen3's F4_json and R results are confounded (`grammar+thinking_blocked`) and were never folded into the main per-factor flip-rate numbers above as if they were a clean one-thing-changed comparison for Qwen3 specifically. Decomposition vs F2 (thinking-off only): the grammar-plus-thinking-blocked effect (F4-D) is a mean score change of roughly -0.05 to +0.40 depending on suite/condition, while the thinking-off-only effect (F2-D) is uniformly positive (+0.01 to +0.54) -- the grammar component alone (F4-F2) is substantially negative everywhere (-0.03 to -0.26), meaning **the grammar constraint, not the loss of thinking, is what drives most of Qwen3's F4/R effect.**

**Hardware-check noise bound next to F5**: the Kaggle hardware check (llama3->llama31, D config re-run on 2x T4) found a maximum |hardware_diff| of **0.0183** (bfcl_simple) across the 3 suites, with 1/3 suites showing a label change (neutral->harmful) purely from the hardware-check's own pair-level recompute, despite every individual run passing the 0.03 per-run tolerance (6/6 runs passed; see `analysis_out/hwcheck_summary.csv`/`hwcheck_pair.csv`/`hwcheck_runs.csv`). Any F5 flip smaller than ~0.018 for this pair, or comparably sized for others, should be read with that noise floor in mind -- none of F5's own flip counts above were re-filtered by it (not requested), but it is reported here as context.

**F6 main number**: computed on sampling-changed pairs only (qwen2->qwen25, qwen25->qwen3, llama3->llama31, gemma2_2b->gemma3_4b -- the pairs touching at least one of the 6 models whose sampling actually changes), n=12, 1 flip (8.3%) -- see table in (d). The all-pairs number (n=30, 1 flip, 3.3%) is reported alongside, never as the headline.

**F3 main count**: computed on both-native pairs only (qwen25->qwen3, granite30->granite31, granite31->granite32), n=9, 2 flips (22.2%) -- see table in (d). The all-pairs/mixed number (n=21, 9 flips, 42.9%) is reported alongside, never as the headline.

---

## 3. Hypotheses: plain pass/fail statement

| Hypothesis | Result |
|---|---|
| **H1** (>=20% of decisions flip under >=1 factor) | **SUPPORTED** -- 43.3% |
| **H2** (format factors flip more than others) | **NOT SUPPORTED** -- format factors flip *less* (11.1% vs 14.8%) |
| **H3** (flipping decisions have smaller median \|stress diff\|) | **NOT SUPPORTED** -- medians are close but flipped is slightly *larger* (0.0383 vs 0.0367) |
| **H4** (R disagrees less than D on held-out nuisance pairs) | **SUPPORTED** -- for F3, F5, F6 individually and pooled, both variants |
| **H5** (A/A false-alarm <=5% AND positive-control detection >=90%) | **NOT SUPPORTED** -- A/A fails marginally (5.56%), both positive controls fail outright (83.3% and 25.0%) |

A failed hypothesis is a result, not a problem. Nothing above was adjusted, re-run, or re-parameterized to change an outcome -- the pipeline ran once, over the pre-registered config and rules, and these are its numbers as produced.

---

## 4. Tables

All 17 tables are saved under `analysis_out/*.csv` (`controls`, `controls_summary`, `decisions_D`, `decisions_all_protocols`, `disagreement`, `factor_flips_long`, `failure_split`, `flip_failure_decomposition`, `flip_rates_by_factor`, `hwcheck_pair`, `hwcheck_runs`, `hwcheck_summary`, `hypotheses`, `qwen3_f4_vs_f2`, `qwen3_pair_labels`, `robust_protocol_checks`, `size_changing_decisions`), plus the pipeline's own `analysis_out/report.md` and `analysis_out/run_warnings.json` (0 warnings, 0 missing). This document is the narrative companion, not a replacement.

---

## 5. Bugs found (flagged, not fixed in scoring/gate code)

**1. Two pre-run blockers, fixed before this pass could even start (file-organization and config, not scoring code; both done with explicit approval):**

- `rescored/F7|F8|F10/` contained only Kaggle F5/R_F5 exploratory rescores from an earlier, unrelated task -- never a D-sourced rescore, which is what PLAN.md's actual F7/F8/F10 factors are and what the pipeline's `F7`/`F8`/`F10` protocol entries expect. For 10 of 16 models this caused a hard crash (`ValueError: ambiguous: 2 run directories`). Fixed by moving the exploratory rescores to `rescored/F7_kaggle_check/` etc. (preserved, not deleted) and running the canonical D-sourced rescore fresh.
- `R_F3`, `R_F6`, and `R_F5` had no `models:` restriction in `configs/analysis_official_folders.yaml`, even though all three are held-out-only factors (per `DEVIATIONS.md`, 2026-10-12/13). `Store.applies()` reads a missing `models:` key as "applies to everyone," so the engine's own documented fallback-to-D mechanism (already working correctly for F2's Qwen3-only scope) never triggered for the 6 design models under these three factors, and it tried to read data that was never produced for them. Fixed by adding the `models:` list (the 10 held-out models) to all three entries -- config only, no change to `engine.py`/`loader.py`/scoring.

**2. Still present, not fixed, reported as asked:** the `n_unmatched` column (`decisions_D.csv`, `decisions_all_protocols.csv`, `controls.csv`, `size_changing_decisions.csv`) is computed as `max(n_old, n_new) - n_records`, where `n_old`/`n_new` count a run's *entire* record set (all 3 conditions, 900 records) but `n_records` only counts matched *stress-condition* records (schema_drift + fault_reporting, up to 600). This means `n_unmatched` is inflated by at least 300 (baseline's full count, which is correctly excluded from the stress-diff calculation by design, not "unmatched") for literally every row in every table -- confirmed directly: all 30 D-protocol rows show exactly `n_records=600, n_unmatched=300`, with zero real mismatch. For same-seed D pairs this 300 fully explains the number. For the A/A control (different global seed) there is a second, *real* source of non-overlap on top of that 300: the seed also reseeds which runtime fault gets chosen per task for `fault_reporting` (confirmed directly: only 66/300 fault_reporting records shared the same fault type between `R/mistral_v02` and `R_AA/mistral_v02` on `synthetic`, vs. 300/300 agreement on `schema_drift`'s drift type, which turned out not to be seed-sensitive for this suite). The displayed `n_unmatched=534` for that row is `300 (baseline, by design) + 234 (real fault_reporting mismatch)` -- a real 234-record effective-sample reduction for A/A's fault_reporting leg, buried inside a column whose face value (534) looks almost twice as bad as that. **The stress_diff/label values themselves are computed correctly, from only the genuinely-matched stress keys** -- this is a diagnostic-column labeling/computation issue, not a correctness bug in any verdict, but it could mislead a reader of the raw CSVs about how much real data underlies the A/A and positive-control rows specifically. Not fixed, per instruction.

No other anomalies found: scanned all 17 output CSVs for out-of-range rates, impossible format+semantic sums, and empty/missing pairs -- none found beyond the one item above.

---

## 6. Setup note

Canonical F7/F8/F10 rescore (sourced from D, all 16 models) was run for the first time in this checkout as part of getting this analysis to run -- see `rescored/F7/`, `rescored/F8/`, `rescored/F10/`. The earlier Kaggle-F5/R_F5-sourced lenient-parsing/relaxed-intent/1-trial check (requested separately, unrelated to this pipeline) is preserved at `rescored/F7_kaggle_check/`, `rescored/F8_kaggle_check/`, `rescored/F10_kaggle_check/`.
