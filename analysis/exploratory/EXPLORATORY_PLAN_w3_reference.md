# EXPLORATORY PLAN: wrong calls against a reference built from the W3 added tasks only

**Exploratory, post hoc, not pre-registered.** Written 2026-11-28, before any result of this analysis was computed. It is post hoc in one sense: the idea came after the wrong-call results against the A/A reference (`EXPLORATORY_wrong_calls.md`, `EXPLORATORY_wrong_calls_coverage.md`) had been seen. That analysis showed that the A/A reference shares the tasks, the prompts and the greedy trial with the scored calls. Existing data only, no reruns.

## Why

The A/A reference (D_AA2 / R_AA2) uses the same 100 tasks per suite, the same prompts and an identical greedy trial (9,600 of 9,600 stress records) as the main arm it scores. A reference built from **different tasks** removes that overlap. It asks whether a call made on the original 100 tasks agrees with the verdict the same upgrade gets on new tasks.

## Data

Facts checked 2026-11-28 from task IDs, folders and run metadata only; no scores were read.

| | bfcl_simple | bfcl_multiple | synthetic |
|---|---|---|---|
| Original tasks (scored calls) | 100 (`data/bfcl_tasks.jsonl`) | 100 (`data/bfcl_multiple_tasks.jsonl`) | 100 |
| W3 added tasks (reference) | 91 (`data/phase2/w3_added_bfcl_simple.jsonl`) | 9 (`data/phase2/w3_added_bfcl_multiple.jsonl`) | none (not extended, PLAN_PHASE2 W3) |
| Task-ID overlap original vs added | 0 | 0 | n/a |
| W3 runs | W3_D and W3_R: 16 models each, 10 trials | same | none |

- **W3 runs:** main arm only (no A/A arm on the added tasks). Trial seeds 1234-1243, trial 0 greedy (temperature 0.0), trials 1-9 at 0.7, run seed 1234 (the same settings as the main D and R runs).
- **Added-task records:** every W3 run holds only added tasks: 0 original task IDs in all 64 runs.

## Rule

1. **Decisions:** the 10 adjacent pairs x bfcl_simple, under D and under R (see "Interpretation rules": bfcl_simple only). W3 data also exist for bfcl_multiple, but with only 9 added tasks, so it is not analysed (rule 6). The 10 synthetic decisions cannot be covered.
2. **Reference verdict:** the study's four-class verdict (S3), computed on the **W3 added-task records only** of the main arm (W3_D or W3_R). Settings:
   - both models of the pair, all 10 trials, stress conditions (schema_drift, fault_reporting), equal weight;
   - CI gate on the 95% task-bootstrap interval for harmful/beneficial;
   - neutral if the 90% interval lies inside +/-0.05, otherwise inconclusive;
   - B = 10,000, seed 1234, rounding-safe comparisons (`scripts/exploratory/_common.py`);
   - the same code path as `wrong_calls_coverage.py` (`make_arrays`, `interval`, `classify`).
3. **Scored calls:** the main arm on the **original 100 tasks only** (results_v2 trials 0-2 + results_v3 trials 3-9), exactly the versions of `EXPLORATORY_wrong_calls_coverage.md`:
   - 1, 3, 5 and 10 trials per call, with the same trial groups;
   - forced (point gate +/-0.05) and inconclusive allowed (S3 on the pooled trials).
4. **Exclusions:** decisions whose reference is inconclusive are left out of every rate, and their number is reported per protocol and suite.
5. **Measures:**
   - reference decisions, calls, definite calls, coverage, wrong, wrong / all calls, wrong / definite calls, serious errors;
   - 95% percentile intervals from a bootstrap over upgrade pairs (B = 10,000, seed 1234);
   - all decisions, and without qwen25->qwen3.
6. **Suites:**
   - bfcl_simple (91 reference tasks) is the only suite analysed.
   - bfcl_multiple (9 reference tasks) is not analysed. At the study's own S6 estimate its MDE for the stress diff is far above 0.05 (S6: 0.066 at 100 tasks, so roughly 0.066 x sqrt(100/9), about 0.22, at 9 tasks), so its references would mostly be inconclusive. (Revised 2026-11-28, before any result: an earlier draft of this file reported bfcl_multiple as a labelled secondary suite.)
7. **Also reported (descriptive):**
   - for each decision, the W3-task reference next to the A/A reference;
   - their agreement on decisions where both are definite.
8. **Pre-check before scores** (task metadata only): the parameter-type signature mix (the stratum used by the BFCL selection) of the 91 added bfcl_simple tasks vs the original 100. If the mixes differ clearly, this is reported as a limitation; nothing in the rule changes.
9. **Reporting:** results are reported whichever way they come out. No threshold, gate, hypothesis or pre-registered result changes. Script `scripts/exploratory/wrong_calls_w3_reference.py`, output `analysis/exploratory/EXPLORATORY_wrong_calls_w3_reference.md` (+ CSV).

## Interpretation rules (fixed 2026-11-28, before any result)

1. **Raw counts in every cell.** Every rate is shown with its counts: wrong / calls, wrong / definite calls, definite / calls, and the number of reference decisions. No rate appears without its numerator and denominator.
2. **Scope:** this is a **sensitivity check of the wrong-call analysis, on bfcl_simple only**. It does not replace `EXPLORATORY_wrong_calls.md` or `EXPLORATORY_wrong_calls_coverage.md` and does not change any pre-registered result.
3. **Minimum size:** if fewer than **8** of a protocol's 10 bfcl_simple reference decisions are definite, that protocol is reported **descriptively only**: counts and per-decision calls, with **no comparison between methods** (no paired differences and no statements that one method is better).
4. **"Better":** one method is called better than another only if the **paired** bootstrap 95% CI of the difference in wrong rate (pairs resampled once, both methods scored on the same resample, B = 10,000, seed 1234) **excludes 0**. Otherwise the report says the data do not distinguish them.
5. **Report whatever the direction:** the result is reported in full whether it supports, weakens or contradicts the earlier wrong-call findings, including a null result or a reversal.

## Disclosure: W3 records already analysed and seen (why this analysis is not blind)

Results that already used the W3 records (original 100 + added tasks merged) have been run and read:

- **P7, pre-registered and descriptive** (`analysis_out_v3_p7/p7.csv`, `analysis_out_v3_p7/analysis_report.md`, seen 2026-11-14). It compares point-gate (D) and CI-gate (R) labels on the original 100 tasks vs the full task set, for bfcl_simple and bfcl_multiple:
  - D: 0 of 20 differ.
  - R: 1 of 20 differs (phi35_mini->phi4_mini, bfcl_simple, neutral -> beneficial).
- **Exploratory S3 on the full task set** (`EXPLORATORY_S3_W3_tasks.md`, 2026-11-14). It gives four-class verdicts on the original 100 vs the full set (191 / 109 tasks) for all 40 BFCL decisions, with the stress diffs on both task sets:
  - 4 of 14 inconclusive decisions become definite on the full set;
  - for example, R bfcl_simple phi35_mini->phi4_mini goes from +0.032 to +0.054.
- **The boundary check** (`NOTE_boundary_check.md`) wrapped every comparison of the Phase 2 pipeline, which includes the P7 full-task-set comparisons. It reported only whether float and exact labels agree.
- **Not run so far:** no verdict on the **added tasks alone**.

**Why this is not blind:**
- The full-set stress diff is a weighted mix of the original-task diff and the added-task diff. Both are known for many decisions, so the direction and rough size of the added-task diff can be inferred for those decisions.
- The idea for this analysis came after the A/A-reference wrong-call results were seen.
- The rule above was fixed before any added-task-only verdict was computed. Its interpretation rules do not depend on which way the result goes. But the analysis is a post hoc sensitivity check, not a blind test.

## Churn sensitivity: trials 1-9 only (computed 2026-11-28; not a W3-reference result)

The noise check in `EXPLORATORY_item_level_flips.md` compares each model's main arm with its A/A arm. The two arms share trial 0 (greedy, identical in both arms: 9,600 of 9,600 stress records score the same), so the 10-trial majorities are not independent and the expected same-model churn may be too low.

**Recomputed here with trial 0 dropped from every arm:**
- right = passed in 5 or more of trials 1-9;
- same-model churn = main arm vs A/A arm, both on trials 1-9;
- upgrade churn = old vs new model, both on trials 1-9;
- expected = mean of the old and new model's same-model churn;
- excess = upgrade churn minus expected;
- 600 stress questions per upgrade (three suites).

Scratch script, read only: existing records, no reruns. The 10-trial rows reproduce the report exactly.

| Upgrade | D: 10 trials (churn / expected / excess) | D: trials 1-9 | R: 10 trials | R: trials 1-9 |
|---|---|---|---|---|
| mistral_v01->mistral_v02 | 138 / 35.0 / +103.0 | 134 / 40.5 / +93.5 | 112 / 28.5 / +83.5 | 110 / 31.5 / +78.5 |
| mistral_v02->mistral_v03 | 102 / 23.0 / +79.0 | 99 / 29.0 / +70.0 | 84 / 13.5 / +70.5 | 84 / 14.5 / +69.5 |
| qwen2->qwen25 | 167 / 17.0 / +150.0 | 156 / 17.5 / +138.5 | 167 / 17.0 / +150.0 | 156 / 17.5 / +138.5 |
| qwen25->qwen3 | 269 / 24.5 / +244.5 | 248 / 25.5 / +222.5 | 89 / 15.0 / +74.0 | 89 / 13.5 / +75.5 |
| llama3->llama31 | 92 / 32.0 / +60.0 | 96 / 38.0 / +58.0 | 96 / 29.0 / +67.0 | 97 / 31.0 / +66.0 |
| phi3_mini->phi35_mini | 92 / 6.5 / +85.5 | 91 / 7.5 / +83.5 | 94 / 6.0 / +88.0 | 91 / 7.5 / +83.5 |
| phi35_mini->phi4_mini | 102 / 15.0 / +87.0 | 99 / 15.5 / +83.5 | 106 / 9.5 / +96.5 | 107 / 10.0 / +97.0 |
| granite30->granite31 | 75 / 13.5 / +61.5 | 73 / 13.0 / +60.0 | 80 / 8.5 / +71.5 | 81 / 8.5 / +72.5 |
| granite31->granite32 | 28 / 11.5 / +16.5 | 30 / 11.5 / +18.5 | 31 / 10.5 / +20.5 | 33 / 12.5 / +20.5 |
| gemma2_2b->gemma3_4b | 66 / 6.5 / +59.5 | 66 / 8.0 / +58.0 | 63 / 6.5 / +56.5 | 63 / 7.0 / +56.0 |
| **All 10** | 1131 / 184.5 / +946.5 | 1092 / 206.0 / +886.0 | 922 / 144.0 / +778.0 | 911 / 153.5 / +757.5 |
| **Without qwen25->qwen3** | 862 / 160.0 / +702.0 | 844 / 180.5 / +663.5 | 833 / 129.0 / +704.0 | 822 / 140.0 / +682.0 |

**Reading:**
- Dropping the shared trial raises the expected same-model churn, as predicted:
  - D 184.5 -> 206.0 (+12%), R 144.0 -> 153.5 (+7%);
  - for single upgrades by up to 6.0 questions.
- Every upgrade's excess stays clearly positive. The smallest is granite31->granite32: +18.5 (D) and +20.5 (R).
- So the shared greedy trial makes the noise floor somewhat too low, but it does not change the conclusion that upgrade churn far exceeds rerun noise.
- Caveat: a 9-trial majority has no ties (5+ of 9), while the 10-trial rule counts 5/10 as wrong, so the two bases differ slightly in definition as well as in trials.

## Known limits (stated now)

- **No synthetic decisions;** bfcl_multiple is effectively uncovered (9 tasks).
- **Selection of the added tasks:** they are all eligible items that the Phase 1 seeded stratified selection did not pick (same eligibility filters; PLAN_PHASE2 W3). They were fixed before W3 ran and do not depend on any result. They are the complement of a stratified sample, not a fresh random sample, and bfcl_multiple eligibility already favours shorter tasks (PLAN.md §3).
- **What still overlaps:** the reference and the scored calls share the models, the protocol settings and the trial seeds. A model's systematic behaviour is shared by design; that is what the reference should capture.
- **A different question:** a reference on different tasks also contains task-to-task variation. Disagreement can mean "the call was wrong" or "the upgrade behaves differently on these tasks". The analysis cannot separate the two.
