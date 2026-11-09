# Part 1: what the plan and code say (quotes) and Part 2: EXPLORATORY Phase 1 analysis

Made 2026-11-07. Part 1 quotes `PLAN_PHASE2.md` at tag `plan-v2` (`git diff plan-v2 -- PLAN_PHASE2.md` is empty, so the working-tree file is the same) and the analysis code. Part 2 uses only Phase 1 data (`results_v2/`, `analysis_out/`). No file under `results_v3/` and no Phase 2 result was opened. The code that makes the Part 2 numbers is `analysis/exploratory/phase1_power_and_failures.py`; its outputs are the CSV files in this folder.

---

# Part 1. From files

## 1.1 Phase 2 primary analyses P1–P7 (`PLAN_PHASE2.md` §4 and §5, verbatim)

```
## 4. Phase 2 hypotheses

| ID | Hypothesis | Threshold |
|---|---|---|
| P1 | At 10 trials, the share of the 30 decisions that flip under ≥1 factor is at least… | **20%** |
| P2 | Of Phase 1's 13 flipped decisions, the number that replicate at 10 trials (§5) is at least… | **7 of 13** |
| P3 | R-gate A/A false-alarm rate (W2, 48 decisions, 10 trials) is at most… | **5%** |
| P4 | Q2_K positive control (W2b) detected under R at 10 trials in at least… | **90%** |
| P5 | On the W2b no-description control, the full-score gate detects more decisions than the stress-only gate | yes / no |
| P6 | F5 (Q4_K_M → Q8_0), same-hardware comparison, replicates (§5) for at least… of the 8 decisions it flipped in Phase 1 | **4 of 8** |

**P7 (descriptive, only if W3 runs):** for D and for R, the share of the 20 BFCL decisions (10 per suite) whose
verdict on the original 100 tasks differs from the verdict on the full task set, per suite.
```

```
## 5. Definitions

- **Replicate (P2):** a Phase 1 flipped decision replicates if, at 10 trials, it flips under
  **at least one** of the factors that flipped it in Phase 1, with the **same label change**:
  its D label equals its Phase 1 D label, and its label under that factor equals the Phase 1
  label under that factor.
- **Replicate (P6):** the same rule, under F5 only, with the same-hardware D label as the
  starting label.
- **Same-hardware rule:** every factor effect is computed against a baseline run on the
  same hardware as the factor run. For F5 and R_F5 on Kaggle models, that is the Kaggle
  D / R baseline from W1. This applies to P1, P2 and P6.
- Anything not listed in §4 is **exploratory** and labeled so in the paper.
```

**Tests.** The plan names no significance test for P1–P7. Each is a threshold on a count or a share. The only interval and test-like rules in the plan are these two (verbatim):

- W2: "Report false-alarm rate with an exact (Clopper–Pearson) 95% CI. Note that the 3 suites of one model are not independent."
- §0 ground rules: "same gate rules and thresholds as PLAN.md, same CI bootstrap seed (1234)."

The label that P1/P2/P6 use is the gate label (point or CI gate, next section). In code the thresholds are in `configs/analysis_phase2.yaml` (`p1_threshold: 0.20`, `p2_min_replicated: 7`, `p3_max: 0.05`, `p4_min: 0.90`, `p6_min_replicated: 4`), and the hypothesis functions are `vdanalysis/phase2/hypotheses2.py` (`p1_rows`, `p2_p6_rows`, `p3_row`, `p4_row`, `p5_row`, `p7_rows`). The report writer (`vdanalysis/phase2/report.py`) says: "Intervals are exact Clopper-Pearson 95%."

## 1.2 Does any planned analysis compare factor flips to A/A flips?

**No analysis compares the factor flip rate (P1) to an A/A flip rate.** The plan has three A/A items; none of them is that comparison:

1. P3 compares the A/A false-alarm rate to a fixed number (verbatim): "| P3 | R-gate A/A false-alarm rate (W2, 48 decisions, 10 trials) is at most… | **5%** |".
2. Descriptive, no threshold (verbatim): "- D-gate A/A false-alarm rate (W2 under D)" and "- Secondary-gate false-alarm rate on A/A".
3. The one place where factor effects are put next to A/A noise is the F5 score shift, not flips (verbatim): "- Size of F5's per-model score shift, same-hardware, vs the A/A noise bound. **Headline bound: 95th percentile of |stress diff| over the W2 D A/A decisions**; the maximum is also reported."
   In code: `vdanalysis/phase2/descriptive.py` `f5_shift_vs_aa`, whose docstring says "next to the A/A noise (PLAN_PHASE2.md section 4)".

Phase 1 (`PLAN.md` §6) says: "A/A null pairs: a model compared against itself (rerun with a different sampling seed). ... Correct verdict is always neutral; measures false-alarm rate." It is used only for H5.

## 1.3 In `decisions_D.csv`, are D labels from the point gate or the CI gate?

**Both columns are in the file, and for all 30 D decisions they are identical** (checked: 0 of 30 differ). So the table cannot tell which gate "the" D label came from. In the flip analysis the D label is the **point gate**:

`vdanalysis/engine.py:148`
```python
                d_label = d["label_point"]
```
and the factor's label is the point-gate label except for F9 (`engine.py:133`):
```python
        return row["label_ci"] if factor_kind == "gate" else row["label_point"]
```
The gates (`upgradecanary/gates.py`):
```python
def point_gate(diff: float, threshold: float = GATE_THRESHOLD) -> str:
    if diff < -threshold:
        return "harmful"
    if diff > threshold:
        return "beneficial"
    return "neutral"
```
```python
def ci_gate(diff: float, ci_lower: float, ci_upper: float, threshold: float = GATE_THRESHOLD) -> str:
    if diff < -threshold and ci_upper < 0:
        return "harmful"
    if diff > threshold and ci_lower > 0:
        return "beneficial"
    return "neutral"
```
Both are set in `vdanalysis/stats.py` (`label_point=point_gate(diff, threshold), label_ci=label_ci`). Threshold 0.05 (`configs/analysis_official_folders.yaml`: `gate: {threshold: 0.05, reps: 10000, seed: 1234}`). `PLAN.md` §4 names the point gate as D's gate.

Note: in my status report of 2026-11-07 I wrote that the D labels in the decisions table were "from the CI gate". It would be more accurate to say that both gates agree on all 30; the flip analysis uses the point gate for D.

## 1.4 Which factor × decision cells use new generations and which are rescoring only?

From `configs/analysis_official_folders.yaml`, `PLAN.md` §5, and the cell counts in `analysis_out/factor_flips_long.csv` (one cell = one pair × suite; 30 cells per factor if it covers all pairs):

| Factor | Cells | Source of the factor-level data |
|---|---|---|
| F1 max_tokens 1024 | 30 | **New generations** (`F1`, 48 runs) |
| F2 Qwen3 thinking off | 3 (qwen25→qwen3 × 3 suites) | **New generations**, Qwen3 only (3 runs); the qwen25 side is taken from D (`Analysis.run_for` falls back to the base protocol) |
| F3 native tool template | 21 (7 pairs); 9 cells have both models native, 12 have one | **New generations** on the 8 models with a native template (`F3`, 24 runs; granite30 from `F3_rerun`); the other model of a pair comes from D |
| F4 generic-JSON grammar | 30 (3 cells, qwen25→qwen3, are confounded: grammar + thinking blocked) | **New generations** (`F4_json`, 48 runs) |
| F5 Q8_0 | 30 | **New generations** (`F5`, 48 runs; 33 on Kaggle, 15 on the laptop); compared against laptop D |
| F6 recommended sampling | 30 (12 cells where sampling changed for ≥1 model; 18 cells where it did not change) | **New generations** (`F6`, 48 runs); for models whose recommended preset equals D's, the F6 run repeats D's settings |
| F7 lenient parsing | 30 | **Rescoring only** (`rescored/F7`, written by `scripts/rescore_f7_lenient_parsing.py` from D records) |
| F8 relaxed intent | 30 | **Rescoring only** (`rescored/F8`, `scripts/rescore_f8_relaxed_intent.py`) |
| F9 CI gate | 30 | **No new data, no new files**: same D records, CI gate instead of point gate (`kind: gate`) |
| F10 greedy trial only | 30 | **Rescoring/subsample only** (`rescored/F10`, 300 records per run, `scripts/rescore_f10_one_trial.py`) |
| F11 legacy chat wrapping | 12 (4 pairs × 3 suites) | **New generations** on the 6 Mistral and Qwen models (`F11`, 18 runs) |

---

# Part 2. EXPLORATORY analysis of Phase 1 data

**EXPLORATORY. Not pre-registered. Not part of the confirmatory results.** Everything here uses Phase 1 records only (3 trials per task-condition, 100 tasks per suite). It was produced after the Phase 1 results were known.

## 2.1 The 30 D decisions: stress diff, 95% CI, half-width

Source: `analysis_out/decisions_D.csv` (task-cluster bootstrap, 10,000 reps, seed 1234). Half-width = (hi − lo) / 2. CSV: `decisions_D_halfwidth.csv`.

| Pair | Suite | Stress diff | 95% CI | Half-width | Label (point = CI gate) |
|---|---|---|---|---|---|
| mistral_v01→v02 | synthetic | −0.0383 | [−0.0767, −0.0017] | 0.0375 | neutral |
| mistral_v01→v02 | bfcl_simple | −0.0583 | [−0.1133, −0.0050] | 0.0542 | harmful |
| mistral_v01→v02 | bfcl_multiple | −0.0833 | [−0.1433, −0.0233] | 0.0600 | harmful |
| mistral_v02→v03 | synthetic | +0.0283 | [−0.0133, +0.0700] | 0.0417 | neutral |
| mistral_v02→v03 | bfcl_simple | +0.1167 | [+0.0633, +0.1700] | 0.0533 | beneficial |
| mistral_v02→v03 | bfcl_multiple | +0.1417 | [+0.0950, +0.1900] | 0.0475 | beneficial |
| qwen2→qwen25 | synthetic | +0.1833 | [+0.1250, +0.2433] | 0.0592 | beneficial |
| qwen2→qwen25 | bfcl_simple | +0.1200 | [+0.0500, +0.1917] | 0.0708 | beneficial |
| qwen2→qwen25 | bfcl_multiple | +0.1383 | [+0.0700, +0.2033] | 0.0667 | beneficial |
| qwen25→qwen3 | synthetic | −0.0833 | [−0.1417, −0.0250] | 0.0583 | harmful |
| qwen25→qwen3 | bfcl_simple | −0.3400 | [−0.4133, −0.2650] | 0.0742 | harmful |
| qwen25→qwen3 | bfcl_multiple | −0.5000 | [−0.5667, −0.4317] | 0.0675 | harmful |
| llama3→llama31 | synthetic | −0.0083 | [−0.0583, +0.0400] | 0.0492 | neutral |
| llama3→llama31 | bfcl_simple | −0.0417 | [−0.0883, +0.0033] | 0.0458 | neutral |
| llama3→llama31 | bfcl_multiple | +0.0117 | [−0.0367, +0.0583] | 0.0475 | neutral |
| phi3_mini→phi35_mini | synthetic | −0.0533 | [−0.0950, −0.0133] | 0.0408 | harmful |
| phi3_mini→phi35_mini | bfcl_simple | +0.0133 | [−0.0400, +0.0683] | 0.0542 | neutral |
| phi3_mini→phi35_mini | bfcl_multiple | −0.0367 | [−0.0933, +0.0183] | 0.0558 | neutral |
| phi35_mini→phi4_mini | synthetic | +0.0200 | [−0.0300, +0.0717] | 0.0508 | neutral |
| phi35_mini→phi4_mini | bfcl_simple | +0.0333 | [−0.0133, +0.0800] | 0.0467 | neutral |
| phi35_mini→phi4_mini | bfcl_multiple | +0.0650 | [+0.0117, +0.1217] | 0.0550 | beneficial |
| granite30→granite31 | synthetic | +0.0217 | [−0.0283, +0.0733] | 0.0508 | neutral |
| granite30→granite31 | bfcl_simple | +0.0367 | [0.0000, +0.0750] | 0.0375 | neutral |
| granite30→granite31 | bfcl_multiple | +0.0033 | [−0.0383, +0.0450] | 0.0417 | neutral |
| granite31→granite32 | synthetic | +0.0217 | [0.0000, +0.0450] | 0.0225 | neutral |
| granite31→granite32 | bfcl_simple | +0.0133 | [−0.0083, +0.0367] | 0.0225 | neutral |
| granite31→granite32 | bfcl_multiple | +0.0283 | [+0.0050, +0.0550] | 0.0250 | neutral |
| gemma2_2b→gemma3_4b | synthetic | −0.0150 | [−0.0383, +0.0067] | 0.0225 | neutral |
| gemma2_2b→gemma3_4b | bfcl_simple | +0.0283 | [−0.0200, +0.0767] | 0.0483 | neutral |
| gemma2_2b→gemma3_4b | bfcl_multiple | +0.0483 | [+0.0033, +0.0917] | 0.0442 | neutral |

(CI values rounded to 4 decimals from the CSV.)

Half-width: min 0.0225, median 0.0488, mean 0.0484, max 0.0742. By suite (min / median / max): synthetic 0.022 / 0.045 / 0.059; bfcl_simple 0.022 / 0.051 / 0.074; bfcl_multiple 0.025 / 0.051 / 0.068. For **15 of the 30 decisions |stress diff| is smaller than the half-width**, i.e. the interval is about as wide as the effect itself (this is a rough reading: the intervals are not symmetric).

## 2.2 Minimum detectable effect (80% power, α = 0.05, paired, 100 tasks)

Method (my choice, exploratory): for each decision, take the per-task paired stress difference (new − old; mean over trials within a stress condition, then equal weight over schema_drift and fault_reporting), n = 100 tasks, SD of that per-task difference observed in the D runs. Suite number = SD pooled over the 10 pairs (root of the mean of the variances). MDE = (z₀.₉₇₅ + z₀.₈₀) × SD / √100 = 2.802 × SD / 10 (normal approximation). Check: the mean of the per-task differences equals the stress diff in `decisions_D.csv` to within 3.3e-7 for all 30 decisions. CSVs: `mde_by_suite.csv`, `mde_by_pair.csv`.

| Suite | Pooled SD of per-task diff | **MDE (80% power)** | Range over the 10 pairs |
|---|---|---|---|
| synthetic | 0.231 | **0.065** | 0.033 – 0.085 |
| bfcl_simple | 0.270 | **0.076** | 0.032 – 0.107 |
| bfcl_multiple | 0.271 | **0.076** | 0.037 – 0.097 |

Reading, with limits:
- The gate threshold is 0.05. With these SDs, a true difference of exactly 0.05 would be detected with about 58% power on synthetic and about 46% / 45% on bfcl_simple / bfcl_multiple (my arithmetic from the numbers above, same approximation). The study is therefore not powered to separate effects of the size of the gate threshold from zero at 100 tasks and 3 trials.
- The SD differs a lot by pair (granite31→granite32 and gemma2_2b→gemma3_4b synthetic have SD about 0.12; qwen25→qwen3 bfcl_simple 0.38), so the one number per suite hides that pairs with similar models need fewer tasks.
- Limits: the SD is estimated from the same data (noisy); normal approximation rather than the bootstrap used in the study; trials are averaged within task, so trial-level sampling noise is not modelled separately; the number is not an official power analysis.

## 2.3 Flips by type: sign reversals vs boundary crossings

Definition used here: a flip is a (factor, pair, suite) cell whose label differs from D's label (`flipped` in `analysis_out/factor_flips_long.csv`). **Sign reversal** = labels are harmful and beneficial in either order. **Boundary crossing** = one of the two labels is neutral. ("Sign reversal" here is about labels; the CSV's own `sign_flip` column is about the sign of the stress diff and is a different thing.) "main" = the variant used for the headline flip rates (not confounded; F3 needs both models native). CSV: `flip_types_by_factor.csv`.

| Factor | Variant | Cells | Flips | Sign reversals (harmful↔beneficial) | Boundary crossings (via neutral) | of which D label → neutral | of which neutral → non-neutral |
|---|---|---|---|---|---|---|---|
| F1 | main | 30 | 3 | 1 | 2 | 2 | 0 |
| F2 | main | 3 | 3 | 2 | 1 | 1 | 0 |
| F3 | main | 9 | 2 | 0 | 2 | 0 | 2 |
| F3 | all | 21 | 9 | 1 | 8 | 1 | 7 |
| F4 | main | 27 | 3 | 0 | 3 | 2 | 1 |
| F5 | main | 30 | 8 | 0 | 8 | 0 | 8 |
| F6 | main | 12 | 1 | 0 | 1 | 0 | 1 |
| F7 | main | 30 | 1 | 0 | 1 | 1 | 0 |
| F8 | main | 30 | 1 | 0 | 1 | 0 | 1 |
| F9 | main | 30 | 0 | 0 | 0 | 0 | 0 |
| F10 | main | 30 | 1 | 0 | 1 | 0 | 1 |
| F11 | main | 12 | 5 | 0 | 5 | 5 | 0 |

("all" differs from "main" only for F3 (21 cells, 9 flips, shown), F4 (30 cells, the same 3 flips) and F6 (30 cells, the same 1 flip). The sign reversals: F1 once (qwen25→qwen3 synthetic, harmful→beneficial); F2 twice (qwen25→qwen3 synthetic and bfcl_simple, harmful→beneficial); F3 "all" once more (phi35_mini→phi4_mini bfcl_multiple, beneficial→harmful).)

Totals over the factors in the table above, main variants: 28 flips, of which **3 are sign reversals (all three in the qwen25→qwen3 pair: F1 once, F2 twice) and 25 are boundary crossings**. All 8 F5 flips and all 5 F11 flips cross only the neutral boundary. Caution: a boundary crossing can be a tiny score change near ±0.05 (for example mistral_v01→v02 synthetic, D diff −0.038), and with half-widths of about 0.05 (2.1) many of these crossings are within the noise of the measurement. They are not necessarily large effects.

## 2.4 Failure types per model × protocol

Data: `results_v2/<protocol>/<model>/<suite>/parsed_results.jsonl`, completed runs only, all 3 suites, 3 trials (granite30 F3 uses `F3_rerun`, as the pipeline does). Rescored folders (F7, F8, F10) are not included because they change scoring, not generations. Full table (143 model × protocol rows): `failure_types_by_model_protocol.csv`. No run was skipped.

Categories (first failing check, so each failure counts once):
- Tool-call conditions (`baseline` + `schema_drift`, 1800 records per model-protocol with all 3 suites): **malformed/unparsed** (`parse_ok` false); **wrong tool name** (`tool_name_ok` false); **wrong/invalid args** (`args_intent_match` or `args_valid_under_drift` false); **executor fail** (`executor_ok` false while all earlier checks pass); other.
- `fault_reporting` (900 records per model-protocol): **malformed/unparsed**; **wrong status** (`status_ok` false); **fabricated answer** (status correct but the answer should be empty and is not); other.
- "Executor fail" and "other" are 0 in every row: no record failed first at the executor, so the executor check adds nothing beyond the argument checks in this harness.

### D protocol, per model (% of that model's records)

| Model | Tool-call fail % | malformed | wrong tool | wrong/invalid args | Fault-reporting fail % | malformed | wrong status | fabricated |
|---|---|---|---|---|---|---|---|---|
| gemma2_2b | 16.9 | 1.4 | 0.0 | 15.5 | 0.6 | 0.6 | 0.0 | 0.0 |
| gemma3_4b | 9.1 | 0.1 | 0.0 | 8.9 | 5.6 | 4.0 | 1.6 | 0.0 |
| granite30 | 9.3 | 0.0 | 0.0 | 9.3 | 8.0 | 1.1 | 6.9 | 0.0 |
| granite31 | 4.7 | 0.0 | 0.0 | 4.7 | 10.9 | 4.9 | 5.9 | 0.1 |
| granite32 | 4.3 | 0.0 | 0.0 | 4.3 | 7.2 | 3.1 | 3.9 | 0.2 |
| llama3 | 16.2 | 6.5 | 0.0 | 9.7 | 7.7 | 5.2 | 2.4 | 0.0 |
| llama31 | 11.6 | 0.0 | 0.0 | 11.6 | 10.7 | 2.4 | 8.2 | 0.0 |
| mistral_v01 | 14.8 | 1.5 | 0.0 | 13.3 | 10.0 | 4.7 | 5.3 | 0.0 |
| mistral_v02 | 26.7 | 5.8 | 0.7 | 20.2 | 8.8 | 2.4 | 6.3 | 0.0 |
| mistral_v03 | 11.1 | 0.1 | 0.0 | 10.9 | 8.3 | 1.0 | 7.3 | 0.0 |
| phi3_mini | 9.2 | 0.2 | 0.0 | 9.0 | 14.4 | 3.8 | 10.7 | 0.0 |
| phi35_mini | 4.8 | 0.0 | 0.0 | 4.8 | 25.1 | 0.4 | 24.7 | 0.0 |
| phi4_mini | 6.9 | 0.0 | 0.0 | 6.9 | 14.9 | 2.1 | 12.8 | 0.0 |
| qwen2 | 9.8 | 0.0 | 0.0 | 9.8 | 34.0 | 18.0 | 16.0 | 0.0 |
| qwen25 | 4.9 | 0.0 | 0.3 | 4.6 | 14.8 | 0.7 | 14.1 | 0.0 |
| qwen3 | 33.3 | 31.5 | 0.0 | 1.8 | 41.1 | 37.3 | 3.8 | 0.0 |

### All protocols, pooled over the models that have that protocol

The model sets differ by protocol (F2: Qwen3 only; F3: 8 models; F11: 6 models; R_F3, R_F5: held-out models; R_AA: 6 models; controls: 4 models), so rows are **not** comparable to each other as protocol effects.

| Protocol | Models | Tool-call records | Fail % | malformed | wrong tool | wrong/invalid args | Fault-rep. records | Fail % | malformed | wrong status | fabricated |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D | 16 | 28,800 | 12.1 | 2.9 | 0.1 | 9.1 | 14,400 | 13.9 | 5.7 | 8.1 | 0.0 |
| F1 | 16 | 28,800 | 10.3 | 1.1 | 0.1 | 9.1 | 14,400 | 11.9 | 3.5 | 8.2 | 0.1 |
| F2 | 1 | 1,800 | 3.4 | 0.0 | 0.0 | 3.4 | 900 | 2.7 | 0.0 | 2.7 | 0.0 |
| F3 | 8 | 14,400 | 33.6 | 16.6 | 0.5 | 16.6 | 7,200 | 14.6 | 6.4 | 8.1 | 0.0 |
| F4_json | 16 | 28,800 | 10.2 | 0.5 | 0.1 | 9.7 | 14,400 | 13.9 | 5.7 | 8.1 | 0.0 |
| F5 | 16 | 28,800 | 12.4 | 3.6 | 0.0 | 8.8 | 14,400 | 13.2 | 5.6 | 7.7 | 0.0 |
| F6 | 16 | 28,800 | 11.8 | 2.7 | 0.1 | 9.1 | 14,400 | 14.1 | 6.1 | 8.0 | 0.0 |
| F11 | 6 | 10,800 | 14.3 | 4.0 | 0.1 | 10.2 | 5,400 | 20.7 | 10.0 | 10.7 | 0.0 |
| R | 16 | 28,800 | 10.2 | 0.5 | 0.1 | 9.7 | 14,400 | 11.9 | 3.5 | 8.2 | 0.1 |
| R_AA | 6 | 10,800 | 8.9 | 0.0 | 0.2 | 8.8 | 5,400 | 19.1 | 4.6 | 14.5 | 0.1 |
| R_F3 | 5 | 9,000 | 20.3 | 0.0 | 0.6 | 19.7 | 4,500 | 10.1 | 2.3 | 7.8 | 0.1 |
| R_F5 | 10 | 18,000 | 8.8 | 0.0 | 0.0 | 8.8 | 9,000 | 8.1 | 2.4 | 5.7 | 0.0 |
| R_F6 | 3 | 5,400 | 10.0 | 0.0 | 0.0 | 10.0 | 2,700 | 7.9 | 3.8 | 4.1 | 0.0 |
| R_PC_NODESC | 4 | 7,200 | 14.4 | 0.0 | 0.1 | 14.2 | 3,600 | 9.9 | 1.5 | 8.4 | 0.1 |
| R_PC_Q2K | 4 | 7,200 | 11.2 | 0.0 | 0.1 | 11.1 | 3,600 | 31.1 | 9.1 | 21.9 | 0.1 |

What the tables show, and what they do not:
- Most tool-call failures are wrong or invalid arguments (9.1 of 12.1 points under D); wrong tool name is rare everywhere (at most 0.7% for any model in D). Unparsed output is concentrated in a few models under D: Qwen3 (31.5%), Llama 3 (6.5%), Mistral v0.2 (5.8%). Pooled over all 16 models it falls from 2.9% under D to 0.5% under R.
- In fault_reporting, "wrong status" is the larger share for most models; Qwen3 and Qwen2 have mostly unparsed output; fabricated answers are almost absent (≤ 0.2%).
- These counts are failures by the first failing check. They do not say why the model failed (for example whether wrong arguments are a real mistake or a scoring-strictness issue; the human spot-check in `analysis/audit/intent_strictness.md` found 8 of 40 rule-false records that a human accepted).
- The F3 pooled row (33.6% tool-call failures) is not "F3 is worse than D" since it covers only the 8 models that have a native template; compare per model in the CSV.
