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

**Honest reading of why H5 fails, stated plainly:**

- **The A/A threshold (<=5%) is not reachable with 18 decisions.** With n=18, the only possible false-alarm rates are multiples of 1/18 = 5.56%: either exactly 0% (pass) or 5.56% (already a fail) -- there is no way to land *at* 5% with this sample size, and the single flip that occurred (llama31/bfcl_multiple) pushes the rate to the first non-zero value the test can produce. This doesn't make the flip itself less real (its CI sits cleanly below zero -- see the exploratory section below), but the *threshold's* 5% figure and this control's *achievable* rates don't actually overlap except at 0%.
- **The no-description control's real damage sits in `baseline`, not in the stress conditions the gate scores.** The stress diff (what H5's detection-rate test actually reads) only crosses -0.05 on 3/12 decisions, all `bfcl_multiple`. But the baseline-only diff (see exploratory section below) shows a real, substantial drop (|diff| >= 0.05) on 8/12 decisions -- the no-description damage is concentrated in the model's *baseline* tool-calling accuracy (worse at picking the right tool/arguments once descriptions are gone), which this control's own detection metric never looks at. A detection-rate test built on the stress diff structurally cannot see damage that shows up as a baseline-accuracy drop rather than a stress-condition-specific one.

Neither point changes the FAIL verdict -- both are pre-registered, unadjusted thresholds and the gate scored exactly what it was built to score. They explain *why* it failed, not that it shouldn't have.

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

## i. Exploratory follow-up: noise bounds, flip sizes, and where the no-description damage sits

**Everything in this section is exploratory** -- it re-queries the pipeline's own already-computed output (`controls.csv`, `flip_failure_decomposition.csv`, `hwcheck_pair.csv`) plus one direct re-derivation from the raw `results_v2/` JSONL for the two items the pipeline doesn't tabulate on its own (the per-task A/A breakdown and the per-suite/condition matched-record counts). No threshold, gate, or verdict is touched; nothing here changes section (a)-(h) or section 3.

### i.1. Full A/A noise distribution (18/18 decisions)

Source: `analysis_out/controls.csv`, rows where `control == AA_R`.

| Model | Suite | Split | Stress diff | CI (95%) | Label |
|---|---|---|---|---|---|
| mistral_v02 | synthetic | design | +0.0076 | [-0.0083, +0.0277] | neutral |
| mistral_v02 | bfcl_simple | design | +0.0000 | [-0.0774, +0.0728] | neutral |
| mistral_v02 | bfcl_multiple | design | +0.0333 | [-0.0123, +0.0849] | neutral |
| qwen2 | synthetic | design | -0.0042 | [-0.0399, +0.0325] | neutral |
| qwen2 | bfcl_simple | design | +0.0247 | [-0.0361, +0.0878] | neutral |
| qwen2 | bfcl_multiple | design | **+0.0456** | [-0.0116, +0.1055] | neutral |
| qwen25 | synthetic | design | +0.0024 | [-0.0376, +0.0325] | neutral |
| qwen25 | bfcl_simple | design | +0.0069 | [-0.0438, +0.0715] | neutral |
| qwen25 | bfcl_multiple | design | +0.0000 | [0.0000, 0.0000] | neutral |
| llama31 | synthetic | held-out | -0.0379 | [-0.0705, -0.0088] | neutral |
| llama31 | bfcl_simple | held-out | -0.0009 | [-0.0753, +0.0822] | neutral |
| llama31 | bfcl_multiple | held-out | **-0.1108** | [-0.1829, -0.0486] | **harmful** |
| phi35_mini | synthetic | held-out | +0.0033 | [-0.0246, +0.0333] | neutral |
| phi35_mini | bfcl_simple | held-out | -0.0128 | [-0.0417, 0.0000] | neutral |
| phi35_mini | bfcl_multiple | held-out | -0.0067 | [-0.0511, +0.0408] | neutral |
| granite31 | synthetic | held-out | +0.0009 | [-0.0289, +0.0313] | neutral |
| granite31 | bfcl_simple | held-out | -0.0444 | [-0.0897, -0.0052] | neutral |
| granite31 | bfcl_multiple | held-out | -0.0323 | [-0.0972, +0.0179] | neutral |

**17 of 18 fall within +-0.046** (max |diff| = 0.0456, qwen2/bfcl_multiple). **One outlier at -0.1108** (llama31/bfcl_multiple), nearly 2.5x the next-largest magnitude and the only one of the 18 whose CI excludes zero -- this is the single decision that fails the A/A control. The other 17 look exactly like what a pure-noise distribution should look like: small, roughly symmetric around zero, CIs all straddling zero.

### i.2. The 13 H1 flips, sized against the A/A and hardware noise floors

Source: `analysis_out/flip_failure_decomposition.csv`, filtered to F1-F10 (H1's factor set; F11 excluded) with F3/F4/F6 main-scoping applied, deduplicated to the 13 unique (pair, suite) decisions -- reconciled to match `flip_rates_by_factor.csv`'s per-factor main counts exactly. "Noise bound" = the larger of the hwcheck pair-diff for that suite (synthetic 0.0017, bfcl_simple 0.0183, bfcl_multiple 0.0100) and the A/A 17-of-18 bound (0.0456); flagged if the flip's |delta| (factor diff minus D diff) is smaller than that bound.

Hwcheck bound by suite: synthetic 0.0017, bfcl_simple 0.0183, bfcl_multiple 0.0100. A/A bound (all suites): 0.0456.

| Pair | Suite | Factor | D diff | Factor diff | \|delta\| | Within hwcheck bound? | Within A/A bound? |
|---|---|---|---|---|---|---|---|
| qwen25->qwen3 | synthetic | F1 | -0.0833 | +0.0550 | 0.138 | No | No |
| qwen25->qwen3 | synthetic | F2 | -0.0833 | +0.0917 | 0.175 | No | No |
| qwen25->qwen3 | bfcl_simple | F1 | -0.3400 | +0.0183 | 0.358 | No | No |
| qwen25->qwen3 | bfcl_simple | F2 | -0.3400 | +0.0733 | 0.413 | No | No |
| qwen25->qwen3 | bfcl_multiple | F1 | -0.5000 | -0.0333 | 0.467 | No | No |
| qwen25->qwen3 | bfcl_multiple | F2 | -0.5000 | +0.0367 | 0.537 | No | No |
| granite30->granite31 | bfcl_simple | F3 (main) | +0.0367 | +0.1533 | 0.117 | No | No |
| granite30->granite31 | bfcl_simple | F5 | +0.0367 | +0.0667 | 0.030 | No | **Yes** |
| granite30->granite31 | bfcl_multiple | F3 (main) | +0.0033 | +0.1217 | 0.118 | No | No |
| granite30->granite31 | bfcl_multiple | F5 | +0.0033 | +0.0600 | 0.057 | No | No |
| mistral_v01->mistral_v02 | bfcl_simple | F4 (main) | -0.0583 | -0.0250 | 0.033 | No | **Yes** |
| mistral_v01->mistral_v02 | bfcl_simple | F7 | -0.0583 | -0.0450 | 0.013 | **Yes** | **Yes** |
| mistral_v01->mistral_v02 | bfcl_multiple | F4 (main) | -0.0833 | -0.0117 | 0.072 | No | No |
| llama3->llama31 | bfcl_simple | F4 | -0.0417 | -0.0667 | 0.025 | No | **Yes** |
| llama3->llama31 | bfcl_simple | F5 | -0.0417 | -0.0583 | 0.017 | **Yes** | **Yes** |
| llama3->llama31 | bfcl_simple | F6 (main) | -0.0417 | -0.0517 | 0.010 | **Yes** | **Yes** |
| llama3->llama31 | bfcl_simple | F8 | -0.0417 | -0.0550 | 0.013 | **Yes** | **Yes** |
| mistral_v01->mistral_v02 | synthetic | F5 | -0.0383 | -0.1050 | 0.067 | No | No |
| mistral_v01->mistral_v02 | synthetic | F10 | -0.0383 | -0.0600 | 0.022 | No | **Yes** |
| mistral_v02->mistral_v03 | synthetic | F3 | +0.0283 | +0.0650 | 0.037 | No | **Yes** |
| mistral_v02->mistral_v03 | synthetic | F5 | +0.0283 | +0.0833 | 0.055 | No | No |
| phi35_mini->phi4_mini | bfcl_simple | F5 | +0.0333 | +0.0700 | 0.037 | No | **Yes** |
| granite30->granite31 | synthetic | F5 | +0.0217 | +0.0683 | 0.047 | No | No (just above 0.0456) |
| gemma2_2b->gemma3_4b | synthetic | F5 | -0.0150 | -0.0517 | 0.037 | No | **Yes** |

**Reading:** 6 of the 13 flipped decisions (the three qwen25->qwen3 suites under F1/F2, granite30->granite31/bfcl_multiple and /synthetic under F3/F5, and mistral_v01->mistral_v02/bfcl_multiple under F4) have *every* contributing factor's shift clearly outside both noise bounds -- these are the clearest genuine flips. The other 7 have at least one contributing factor whose shift falls inside the looser A/A bound (0.0456); of those, 2 (mistral_v01->mistral_v02/bfcl_simple via F7, llama3->llama31/bfcl_simple via F5/F6/F8) have a factor inside the stricter hwcheck bound too -- these two are the weakest-evidence flips in the H1 count. This sizing exercise does not change H1's PASS verdict or its 13-decision count; it is reported only to show which flips sit closest to the noise floor.

### i.3. llama31/bfcl_multiple A/A case: schema_drift vs fault_reporting

Direct re-derivation from `results_v2/R/llama31/bfcl_multiple/` vs `results_v2/R_AA/llama31/bfcl_multiple/`, matched on `(task_id, condition, drift.type, fault.type, trial_index)`:

| Condition | Matched records | Mean diff |
|---|---|---|
| schema_drift | 75 (25 tasks x 3 trials) | -0.0933 |
| fault_reporting | 39 (13 tasks x 3 trials) | -0.1282 |

Both conditions pull the stress diff down -- this is not a single-condition artifact. No single task dominates either: the worst schema_drift tasks (`bfcl-multiple-multiple_190`, `_67`) and the worst fault_reporting task (`_82`) each lose exactly 2 of 3 trials (score drops of -2.0 summed across 3 trials, i.e. 1 trial still agrees); every other affected task loses at most 1 of 3. The flip comes from a broad, mild degradation across many tasks in both stress conditions, not one pathological task or one condition.

### i.4. No-description control: baseline-only diff, all 12 decisions

Source: `analysis_out/controls.csv`, rows where `control == PC_NODESC_R`, `baseline_diff` column (baseline-condition-only score change, R_PC_NODESC vs R).

| Model | Suite | Split | Stress diff | Baseline-only diff | Stress label | Detected? |
|---|---|---|---|---|---|---|
| mistral_v03 | synthetic | design | +0.0150 | +0.0267 | neutral | No |
| mistral_v03 | bfcl_simple | design | -0.0233 | **-0.0767** | neutral | No |
| mistral_v03 | bfcl_multiple | design | -0.0467 | **-0.1400** | neutral | No |
| qwen25 | synthetic | design | -0.0017 | 0.0000 | neutral | No |
| qwen25 | bfcl_simple | design | -0.0333 | **-0.0800** | neutral | No |
| qwen25 | bfcl_multiple | design | -0.0783 | **-0.1167** | harmful | **Yes** |
| llama31 | synthetic | held-out | +0.0050 | -0.0100 | neutral | No |
| llama31 | bfcl_simple | held-out | -0.0183 | **-0.1267** | neutral | No |
| llama31 | bfcl_multiple | held-out | -0.0800 | **-0.1533** | harmful | **Yes** |
| granite32 | synthetic | held-out | -0.0017 | -0.0167 | neutral | No |
| granite32 | bfcl_simple | held-out | -0.0233 | **-0.0500** | neutral | No |
| granite32 | bfcl_multiple | held-out | -0.0633 | **-0.1167** | harmful | **Yes** |

**8 of 12 decisions show a baseline-only drop of |diff| >= 0.05** (bolded above), including 5 decisions where the baseline damage is real and substantial (-0.05 to -0.15) but the *stress* diff never crosses the gate's threshold -- these are exactly the decisions the detection-rate test misses. All 3 decisions where the control *was* correctly detected are `bfcl_multiple`, where baseline damage and stress damage happen to coincide. Stripping descriptions clearly hurts these models' ability to pick the right tool/arguments even with no adversarial condition applied at all -- it is a real, measurable harm that this particular control (built on the stress diff) is structurally unable to see on most of the 12 decisions.

### i.5. Matched-record counts per suite and condition (A/A pairs, pooled over 6 models)

Direct count from `results_v2/R/<model>/<suite>/` vs `results_v2/R_AA/<model>/<suite>/`, matched on the same key as `compare()`, pooled over the 6 A/A models (mistral_v02, qwen2, qwen25, llama31, phi35_mini, granite31); "possible" = records present in the D-seed run for that condition (300/model x 6 = 1800).

| Suite | baseline matched | schema_drift matched | fault_reporting matched | stress total matched | stress total possible | % matched |
|---|---|---|---|---|---|---|
| synthetic | 1800 / 1800 | 1800 / 1800 | 396 / 1800 | 2196 | 3600 | 61.0% |
| bfcl_simple | 1800 / 1800 | 504 / 1800 | 234 / 1800 | 738 | 3600 | 20.5% |
| bfcl_multiple | 1800 / 1800 | 450 / 1800 | 234 / 1800 | 684 | 3600 | **19.0%** |

**`bfcl_multiple` has the fewest matched stress records of the three suites** (684/3600, 19.0%), with `bfcl_simple` close behind (738/3600, 20.5%); `synthetic` is much higher (2196/3600, 61.0%) because its `schema_drift` condition happens not to be seed-sensitive for this model set (100% matched), unlike the BFCL suites where both stress conditions lose the large majority of records to the A/A seed's reselection of drift/fault scenarios. This is a feature of how `fault_reporting` (and, for BFCL, `schema_drift` too) select which scenario applies per task -- re-seeding changes the selection, not the scoring -- and it is the structural cause of the `n_unmatched` column discussed in section 5 below.

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

## 5. Bugs found (flagged and documented, not fixed in scoring/gate code)

**1. Two pre-run blockers, fixed before this pass could even start (file-organization and config, not scoring code; both done with explicit approval):**

- `rescored/F7|F8|F10/` contained only Kaggle F5/R_F5 exploratory rescores from an earlier, unrelated task -- never a D-sourced rescore, which is what PLAN.md's actual F7/F8/F10 factors are and what the pipeline's `F7`/`F8`/`F10` protocol entries expect. For 10 of 16 models this caused a hard crash (`ValueError: ambiguous: 2 run directories`). Fixed by moving the exploratory rescores to `rescored/F7_kaggle_check/` etc. (preserved, not deleted) and running the canonical D-sourced rescore fresh.
- `R_F3`, `R_F6`, and `R_F5` had no `models:` restriction in `configs/analysis_official_folders.yaml`, even though all three are held-out-only factors (per `DEVIATIONS.md`, 2026-10-12/13). `Store.applies()` reads a missing `models:` key as "applies to everyone," so the engine's own documented fallback-to-D mechanism (already working correctly for F2's Qwen3-only scope) never triggered for the 6 design models under these three factors, and it tried to read data that was never produced for them. Fixed by adding the `models:` list (the 10 held-out models) to all three entries -- config only, no change to `engine.py`/`loader.py`/scoring.

**2. Still present, not fixed (no code or threshold change made); documented precisely here, per instruction.** What `n_unmatched` actually counts, exactly:

`n_unmatched = max(n_old, n_new) - n_records`, where:
- `n_old`/`n_new` = the *entire* record count of each run (all 3 conditions: baseline + schema_drift + fault_reporting -- every suite is structurally identical here, 100 tasks x 3 trials x 3 conditions = 900 records; confirmed directly against the raw `parsed_results.jsonl` for all 3 suites -- see `Run.__len__`).
- `n_records` = the count of *matched* keys restricted to the two stress conditions only (`compare()` filters `k[1] in conditions` to `{schema_drift, fault_reporting}` before counting) -- baseline is excluded from `n_records` by design, since the stress diff never uses baseline.

So `n_unmatched` always has two components baked into one number: **(a)** baseline's full record count, always exactly 300 regardless of suite (always excluded from `n_records` by design, not a real mismatch -- this component alone is the entire explanation for D-protocol rows, where `n_records=600` and `n_unmatched=300` on every single one of the 30 rows, with zero real mismatch), and **(b)** for any comparison where the two runs don't share a seed (A/A, Q2_K, no-description), a *second, genuine* reduction: re-seeding changes which fault (`fault_reporting`) and, on the BFCL suites, which drift scenario (`schema_drift`) gets selected per task, so fewer stress-condition keys actually overlap between the two runs.

Component (b) is exactly quantified by the new matched-record table in section i.5 above: pooled over the 6 A/A models, `synthetic` loses only the `fault_reporting` leg (396/1800 matched, `schema_drift` is 100% matched, i.e. not seed-sensitive for this suite), while both BFCL suites lose the majority of *both* stress conditions (`bfcl_simple`: 504/1800 schema_drift, 234/1800 fault_reporting; `bfcl_multiple`: 450/1800, 234/1800). Concretely, for a single A/A row such as `mistral_v02/synthetic` (`n_records=366`, `n_unmatched=534` in `controls.csv`): of the 534, 300 is component (a) and the remaining 234 is component (b) -- a real reduction in `synthetic`'s `fault_reporting` leg specifically (the row's `n_records=366` is `300 matched schema_drift + 66 matched fault_reporting`, out of a possible 300+300).

**The stress_diff/label values themselves are computed correctly, from only the genuinely-matched stress keys in every row** -- no verdict changes as a result of this writeup. This is a diagnostic-column labeling issue: the column's face value conflates an intentional, by-design exclusion (baseline) with a real, seed-driven sample-size reduction (re-selected fault/drift scenarios), and a reader of the raw CSVs alone, without this note, would not be able to tell the two apart or know that `bfcl_multiple` and `bfcl_simple` carry the larger real reduction of the three suites. Not fixed in code, per instruction; the table in section i.5 is the authoritative per-suite/condition breakdown of component (b).

No other anomalies found: scanned all 17 output CSVs for out-of-range rates, impossible format+semantic sums, and empty/missing pairs -- none found beyond the one item above.

---

## 6. Setup note

Canonical F7/F8/F10 rescore (sourced from D, all 16 models) was run for the first time in this checkout as part of getting this analysis to run -- see `rescored/F7/`, `rescored/F8/`, `rescored/F10/`. The earlier Kaggle-F5/R_F5-sourced lenient-parsing/relaxed-intent/1-trial check (requested separately, unrelated to this pipeline) is preserved at `rescored/F7_kaggle_check/`, `rescored/F8_kaggle_check/`, `rescored/F10_kaggle_check/`.
