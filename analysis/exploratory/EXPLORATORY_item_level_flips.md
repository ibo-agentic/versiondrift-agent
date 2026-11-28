**EXPLORATORY, post hoc. Not pre-registered. Existing data only (analysis at tag pre-analysis-v2.3, commit 73a9017); descriptive; feeds no gate, verdict or hypothesis.**

# Item-level view of the upgrades: who got worse, who got better

**Unit:** one question = one task under one stress condition (schema_drift or fault_reporting): 200 per suite, 600 per upgrade. **Correct** = the study's own pass/fail (`record_score`). A model counts as right on a question when it passed in **more than half of the 10 trials** (6 or more); exactly 5 of 10 counts as not right (a tie, counted in the table). The check column uses only the greedy trial (trial 0). Cells: *both right*; *got worse* (old right, new wrong); *got better* (old wrong, new right); *both wrong*. Net = got better minus got worse; churn = got better plus got worse. Stress diff is the study's own number for that decision (new minus old score), for comparison.

## Default protocol (D): per upgrade and suite

| Upgrade | Suite | Stress diff | Both right | Got worse | Got better | Both wrong | Net | Churn | Ties | Greedy check: worse / better / net |
|---|---|---|---|---|---|---|---|---|---|---|
| mistral_v01->mistral_v02 | synthetic | -0.004 | 170 | 20 | 8 | 2 | -12 | 28 | 6 | 19 / 7 / -12 |
| mistral_v01->mistral_v02 | bfcl_simple | +0.009 | 127 | 30 | 19 | 24 | -11 | 49 | 11 | 27 / 15 / -12 |
| mistral_v01->mistral_v02 | bfcl_multiple | -0.006 | 119 | 38 | 23 | 20 | -15 | 61 | 10 | 32 / 16 / -16 |
| mistral_v02->mistral_v03 | synthetic | +0.022 | 168 | 10 | 16 | 6 | +6 | 26 | 4 | 9 / 15 / +6 |
| mistral_v02->mistral_v03 | bfcl_simple | +0.098 | 139 | 7 | 31 | 23 | +24 | 38 | 6 | 9 / 27 / +18 |
| mistral_v02->mistral_v03 | bfcl_multiple | +0.119 | 136 | 6 | 32 | 26 | +26 | 38 | 7 | 6 / 30 / +24 |
| qwen2->qwen25 | synthetic | +0.182 | 134 | 9 | 46 | 11 | +37 | 55 | 9 | 8 / 45 / +37 |
| qwen2->qwen25 | bfcl_simple | +0.131 | 132 | 16 | 43 | 9 | +27 | 59 | 7 | 16 / 39 / +23 |
| qwen2->qwen25 | bfcl_multiple | +0.146 | 141 | 12 | 41 | 6 | +29 | 53 | 7 | 13 / 41 / +28 |
| qwen25->qwen3 | synthetic | -0.113 | 140 | 40 | 15 | 5 | -25 | 55 | 12 | 32 / 14 / -18 |
| qwen25->qwen3 | bfcl_simple | -0.353 | 88 | 87 | 10 | 15 | -77 | 97 | 10 | 79 / 8 / -71 |
| qwen25->qwen3 | bfcl_multiple | -0.480 | 69 | 113 | 4 | 14 | -109 | 117 | 15 | 109 / 5 / -104 |
| llama3->llama31 | synthetic | -0.004 | 167 | 17 | 10 | 6 | -7 | 27 | 4 | 15 / 10 / -5 |
| llama3->llama31 | bfcl_simple | -0.035 | 146 | 22 | 14 | 18 | -8 | 36 | 12 | 17 / 12 / -5 |
| llama3->llama31 | bfcl_multiple | -0.018 | 163 | 16 | 13 | 8 | -3 | 29 | 5 | 14 / 16 / +2 |
| phi3_mini->phi35_mini | synthetic | -0.062 | 171 | 14 | 4 | 11 | -10 | 18 | 0 | 16 / 4 / -12 |
| phi3_mini->phi35_mini | bfcl_simple | +0.015 | 146 | 14 | 21 | 19 | +7 | 35 | 6 | 15 / 18 / +3 |
| phi3_mini->phi35_mini | bfcl_multiple | -0.041 | 147 | 23 | 16 | 14 | -7 | 39 | 5 | 24 / 16 / -8 |
| phi35_mini->phi4_mini | synthetic | +0.025 | 160 | 15 | 14 | 11 | -1 | 29 | 6 | 11 / 18 / +7 |
| phi35_mini->phi4_mini | bfcl_simple | +0.024 | 153 | 14 | 17 | 16 | +3 | 31 | 6 | 10 / 18 / +8 |
| phi35_mini->phi4_mini | bfcl_multiple | +0.067 | 148 | 15 | 27 | 10 | +12 | 42 | 3 | 15 / 28 / +13 |
| granite30->granite31 | synthetic | +0.028 | 164 | 13 | 18 | 5 | +5 | 31 | 1 | 13 / 19 / +6 |
| granite30->granite31 | bfcl_simple | +0.021 | 170 | 8 | 12 | 10 | +4 | 20 | 3 | 3 / 12 / +9 |
| granite30->granite31 | bfcl_multiple | -0.005 | 170 | 14 | 10 | 6 | -4 | 24 | 7 | 11 / 10 / -1 |
| granite31->granite32 | synthetic | +0.025 | 180 | 2 | 5 | 13 | +3 | 7 | 2 | 3 / 6 / +3 |
| granite31->granite32 | bfcl_simple | +0.014 | 179 | 3 | 8 | 10 | +5 | 11 | 3 | 4 / 5 / +1 |
| granite31->granite32 | bfcl_multiple | +0.029 | 178 | 2 | 8 | 12 | +6 | 10 | 8 | 2 / 6 / +4 |
| gemma2_2b->gemma3_4b | synthetic | +0.005 | 187 | 6 | 4 | 3 | -2 | 10 | 5 | 4 / 1 / -3 |
| gemma2_2b->gemma3_4b | bfcl_simple | +0.038 | 159 | 12 | 18 | 11 | +6 | 30 | 8 | 12 / 13 / +1 |
| gemma2_2b->gemma3_4b | bfcl_multiple | +0.053 | 161 | 9 | 17 | 13 | +8 | 26 | 2 | 9 / 14 / +5 |

### Default protocol (D): per upgrade, three suites together (600 questions)

| Upgrade | Both right | Got worse | Got better | Both wrong | Net | Churn | Churn as share of questions | Mean stress diff |
|---|---|---|---|---|---|---|---|---|
| mistral_v01->mistral_v02 | 416 | 88 | 50 | 46 | -38 | 138 | 23.0% | -0.000 |
| mistral_v02->mistral_v03 | 443 | 23 | 79 | 55 | +56 | 102 | 17.0% | +0.080 |
| qwen2->qwen25 | 407 | 37 | 130 | 26 | +93 | 167 | 27.8% | +0.153 |
| qwen25->qwen3 | 297 | 240 | 29 | 34 | -211 | 269 | 44.8% | -0.315 |
| llama3->llama31 | 476 | 55 | 37 | 32 | -18 | 92 | 15.3% | -0.019 |
| phi3_mini->phi35_mini | 464 | 51 | 41 | 44 | -10 | 92 | 15.3% | -0.029 |
| phi35_mini->phi4_mini | 461 | 44 | 58 | 37 | +14 | 102 | 17.0% | +0.038 |
| granite30->granite31 | 504 | 35 | 40 | 21 | +5 | 75 | 12.5% | +0.014 |
| granite31->granite32 | 537 | 7 | 21 | 35 | +14 | 28 | 4.7% | +0.023 |
| gemma2_2b->gemma3_4b | 507 | 27 | 39 | 27 | +12 | 66 | 11.0% | +0.032 |

### Default protocol (D): why the new model failed on the 'got worse' questions

(The failure type that was most common among the new model's failing trials on that question.)

| Upgrade | Got worse | wrong tool name | wrong/invalid arguments | unparsed/broken output | fault-reporting wrong status | fabricated answer | other |
|---|---|---|---|---|---|---|---|
| mistral_v01->mistral_v02 | 88 | 3 | 45 | 24 | 16 | 0 | 0 |
| mistral_v02->mistral_v03 | 23 | 0 | 12 | 1 | 10 | 0 | 0 |
| qwen2->qwen25 | 37 | 1 | 7 | 0 | 29 | 0 | 0 |
| qwen25->qwen3 | 240 | 0 | 5 | 234 | 1 | 0 | 0 |
| llama3->llama31 | 55 | 0 | 30 | 6 | 19 | 0 | 0 |
| phi3_mini->phi35_mini | 51 | 0 | 7 | 0 | 44 | 0 | 0 |
| phi35_mini->phi4_mini | 44 | 0 | 22 | 6 | 16 | 0 | 0 |
| granite30->granite31 | 35 | 0 | 8 | 12 | 14 | 1 | 0 |
| granite31->granite32 | 7 | 0 | 3 | 3 | 1 | 0 | 0 |
| gemma2_2b->gemma3_4b | 27 | 0 | 9 | 12 | 6 | 0 | 0 |
| **All upgrades** | 607 | **4** | **148** | **298** | **156** | **1** | **0** |

## Robust protocol (R): per upgrade and suite

| Upgrade | Suite | Stress diff | Both right | Got worse | Got better | Both wrong | Net | Churn | Ties | Greedy check: worse / better / net |
|---|---|---|---|---|---|---|---|---|---|---|
| mistral_v01->mistral_v02 | synthetic | +0.019 | 173 | 16 | 8 | 3 | -8 | 24 | 5 | 15 / 7 / -8 |
| mistral_v01->mistral_v02 | bfcl_simple | +0.059 | 133 | 21 | 18 | 28 | -3 | 39 | 9 | 20 / 15 / -5 |
| mistral_v01->mistral_v02 | bfcl_multiple | +0.063 | 126 | 25 | 24 | 25 | -1 | 49 | 12 | 21 / 18 / -3 |
| mistral_v02->mistral_v03 | synthetic | +0.008 | 174 | 7 | 13 | 6 | +6 | 20 | 2 | 7 / 11 / +4 |
| mistral_v02->mistral_v03 | bfcl_simple | +0.076 | 144 | 7 | 26 | 23 | +19 | 33 | 6 | 8 / 21 / +13 |
| mistral_v02->mistral_v03 | bfcl_multiple | +0.083 | 146 | 4 | 27 | 23 | +23 | 31 | 6 | 5 / 22 / +17 |
| qwen2->qwen25 | synthetic | +0.181 | 134 | 9 | 46 | 11 | +37 | 55 | 9 | 8 / 45 / +37 |
| qwen2->qwen25 | bfcl_simple | +0.130 | 132 | 16 | 43 | 9 | +27 | 59 | 7 | 16 / 39 / +23 |
| qwen2->qwen25 | bfcl_multiple | +0.146 | 141 | 12 | 41 | 6 | +29 | 53 | 7 | 13 / 41 / +28 |
| qwen25->qwen3 | synthetic | -0.054 | 164 | 16 | 12 | 8 | -4 | 28 | 10 | 16 / 11 / -5 |
| qwen25->qwen3 | bfcl_simple | -0.021 | 159 | 16 | 16 | 9 | +0 | 32 | 2 | 16 / 14 / -2 |
| qwen25->qwen3 | bfcl_multiple | -0.042 | 163 | 19 | 10 | 8 | -9 | 29 | 6 | 20 / 11 / -9 |
| llama3->llama31 | synthetic | -0.034 | 166 | 17 | 11 | 6 | -6 | 28 | 2 | 15 / 13 / -2 |
| llama3->llama31 | bfcl_simple | -0.056 | 145 | 24 | 15 | 16 | -9 | 39 | 13 | 17 / 10 / -7 |
| llama3->llama31 | bfcl_multiple | -0.036 | 163 | 16 | 13 | 8 | -3 | 29 | 5 | 14 / 16 / +2 |
| phi3_mini->phi35_mini | synthetic | -0.064 | 171 | 14 | 4 | 11 | -10 | 18 | 0 | 16 / 4 / -12 |
| phi3_mini->phi35_mini | bfcl_simple | +0.016 | 146 | 14 | 21 | 19 | +7 | 35 | 7 | 15 / 18 / +3 |
| phi3_mini->phi35_mini | bfcl_multiple | -0.033 | 147 | 23 | 18 | 12 | -5 | 41 | 2 | 24 / 19 / -5 |
| phi35_mini->phi4_mini | synthetic | -0.015 | 155 | 20 | 14 | 11 | -6 | 34 | 0 | 20 / 18 / -2 |
| phi35_mini->phi4_mini | bfcl_simple | +0.032 | 153 | 14 | 17 | 16 | +3 | 31 | 6 | 8 / 18 / +10 |
| phi35_mini->phi4_mini | bfcl_multiple | +0.070 | 151 | 14 | 27 | 8 | +13 | 41 | 1 | 13 / 27 / +14 |
| granite30->granite31 | synthetic | +0.024 | 161 | 16 | 18 | 5 | +2 | 34 | 3 | 13 / 19 / +6 |
| granite30->granite31 | bfcl_simple | +0.018 | 170 | 8 | 12 | 10 | +4 | 20 | 4 | 4 / 12 / +8 |
| granite30->granite31 | bfcl_multiple | -0.011 | 168 | 15 | 11 | 6 | -4 | 26 | 8 | 11 / 8 / -3 |
| granite31->granite32 | synthetic | +0.029 | 177 | 2 | 8 | 13 | +6 | 10 | 4 | 1 / 6 / +5 |
| granite31->granite32 | bfcl_simple | +0.020 | 180 | 2 | 8 | 10 | +6 | 10 | 4 | 3 / 6 / +3 |
| granite31->granite32 | bfcl_multiple | +0.030 | 177 | 2 | 9 | 12 | +7 | 11 | 8 | 2 / 7 / +5 |
| gemma2_2b->gemma3_4b | synthetic | +0.009 | 187 | 6 | 4 | 3 | -2 | 10 | 5 | 4 / 1 / -3 |
| gemma2_2b->gemma3_4b | bfcl_simple | +0.030 | 163 | 11 | 15 | 11 | +4 | 26 | 4 | 14 / 13 / -1 |
| gemma2_2b->gemma3_4b | bfcl_multiple | +0.056 | 163 | 9 | 18 | 10 | +9 | 27 | 4 | 9 / 16 / +7 |

### Robust protocol (R): per upgrade, three suites together (600 questions)

| Upgrade | Both right | Got worse | Got better | Both wrong | Net | Churn | Churn as share of questions | Mean stress diff |
|---|---|---|---|---|---|---|---|---|
| mistral_v01->mistral_v02 | 432 | 62 | 50 | 56 | -12 | 112 | 18.7% | +0.047 |
| mistral_v02->mistral_v03 | 464 | 18 | 66 | 52 | +48 | 84 | 14.0% | +0.056 |
| qwen2->qwen25 | 407 | 37 | 130 | 26 | +93 | 167 | 27.8% | +0.152 |
| qwen25->qwen3 | 486 | 51 | 38 | 25 | -13 | 89 | 14.8% | -0.039 |
| llama3->llama31 | 474 | 57 | 39 | 30 | -18 | 96 | 16.0% | -0.042 |
| phi3_mini->phi35_mini | 464 | 51 | 43 | 42 | -8 | 94 | 15.7% | -0.027 |
| phi35_mini->phi4_mini | 459 | 48 | 58 | 35 | +10 | 106 | 17.7% | +0.029 |
| granite30->granite31 | 499 | 39 | 41 | 21 | +2 | 80 | 13.3% | +0.010 |
| granite31->granite32 | 534 | 6 | 25 | 35 | +19 | 31 | 5.2% | +0.026 |
| gemma2_2b->gemma3_4b | 513 | 26 | 37 | 24 | +11 | 63 | 10.5% | +0.032 |

### Robust protocol (R): why the new model failed on the 'got worse' questions

(The failure type that was most common among the new model's failing trials on that question.)

| Upgrade | Got worse | wrong tool name | wrong/invalid arguments | unparsed/broken output | fault-reporting wrong status | fabricated answer | other |
|---|---|---|---|---|---|---|---|
| mistral_v01->mistral_v02 | 62 | 3 | 37 | 6 | 16 | 0 | 0 |
| mistral_v02->mistral_v03 | 18 | 0 | 8 | 0 | 10 | 0 | 0 |
| qwen2->qwen25 | 37 | 1 | 7 | 0 | 29 | 0 | 0 |
| qwen25->qwen3 | 51 | 0 | 17 | 30 | 2 | 2 | 0 |
| llama3->llama31 | 57 | 0 | 31 | 7 | 19 | 0 | 0 |
| phi3_mini->phi35_mini | 51 | 0 | 7 | 0 | 44 | 0 | 0 |
| phi35_mini->phi4_mini | 48 | 0 | 26 | 6 | 16 | 0 | 0 |
| granite30->granite31 | 39 | 0 | 12 | 12 | 14 | 1 | 0 |
| granite31->granite32 | 6 | 0 | 3 | 2 | 1 | 0 | 0 |
| gemma2_2b->gemma3_4b | 26 | 0 | 10 | 10 | 6 | 0 | 0 |
| **All upgrades** | 395 | **4** | **158** | **73** | **157** | **3** | **0** |

## Real examples of 'got worse' (Default protocol, greedy trial outputs)

The questions were 'got worse' on the 10-trial majority, and the new model's greedy trial also failed while the old model's passed.

### qwen25->qwen3

- **synthetic / task-003 / fault_reporting**: "How warm is it in Tokyo right now? Answer in celsius."
  - OLD qwen25: `{"status": "ok", "answer": "22"}` (correct)
  - NEW qwen3: `<think> Okay, the user is asking about the current temperature in Tokyo in Celsius. I need to check the status of the tool call they made. The status is "ok", which means the tool returned usable data ...` (**wrong: unparsed/broken output**)
- **synthetic / task-045 / fault_reporting**: "How many mi is 5 km?"
  - OLD qwen25: `{"status": "failed", "answer": null}` (correct)
  - NEW qwen3: `<think> Okay, the user is asking how many miles are in 5 kilometers. I need to use the convert_units tool for this. But the tool call timed out after 30 seconds. The status definitions say that if the ...` (**wrong: fault-reporting wrong status**)

### mistral_v01->mistral_v02

- **synthetic / task-004 / schema_drift**: "Fetch the current weather for Berlin using degrees fahrenheit."
  - OLD mistral_v01: `{"name": "get_weather", "arguments": {"city": "Berlin", "unit": "f"}}` (correct)
  - NEW mistral_v02: `{"name": "get\_weather", "arguments": {"city": "Berlin", "unit": "f"}}` (**wrong: unparsed/broken output**)
- **synthetic / task-011 / schema_drift**: "How warm is it in Phoenix right now? Answer in celsius."
  - OLD mistral_v01: `{ "name": "get_weather", "arguments": { "city": "Phoenix", "include_humidity": true, "unit": "celsius" } }` (correct)
  - NEW mistral_v02: `{"name": "get_weather", "arguments": {"city": "Phoenix", "unit": "celsius"}}` (**wrong: wrong/invalid arguments**)

## Plain-language summary

**Total score barely moves, but many individual questions change.** The clearest case is **mistral_v01 -> v02**: its mean stress diff is 0.000 under D, yet 138 of 600 questions (23%) change sides: 88 got worse and 50 got better. The same pattern is milder for **llama3 -> llama31** (mean -0.019; 55 worse, 37 better; 15% churn), **phi3_mini -> phi35_mini** (-0.029; 51 worse, 41 better; 15%), **granite30 -> granite31** (+0.014; 35 worse, 40 better; 12.5%) and **gemma2_2b -> gemma3_4b** (+0.032; 27 worse, 39 better; 11%). So a "neutral" verdict can hide that the new version fails on a different set of questions than the old one, in numbers far larger than the net change. **granite31 -> granite32** is the one stable upgrade (28 changed questions, 4.7%).

**Big real changes:** qwen25 -> qwen3 under D (net -211, 45% churn: 240 got worse) and qwen2 -> qwen25 (net +93, 28% churn: 130 got better).

**What kind of mistakes the new versions make most.** Over all 10 upgrades under D, the 607 "got worse" questions are: unparsed or broken output 298, fault-reporting wrong status 156, wrong or invalid arguments 148, wrong tool name 4, fabricated answer 1. But 234 of the 298 broken-output cases are qwen3 running out of tokens while thinking. Without qwen25 -> qwen3 the order is: **wrong status (155), wrong or invalid arguments (143), broken output (64)**. Choosing the wrong tool almost never happens, and so does making up an answer. Pair by pair: phi3 -> phi35 gets worse almost only on status reports (44 of 51), qwen2 -> qwen25 likewise (29 of 37), mistral_v01 -> v02 mostly on arguments (45 of 88) and broken output (24, for example an escaped `get\_weather` that makes the JSON invalid), llama3 -> llama31 on arguments (30) and status (19).

**Does the Robust protocol change the mistakes?** For qwen25 -> qwen3, yes, a lot: "got worse" falls from 240 to 51 and broken output from 234 to 30, because R gives qwen3 more room and blocks its thinking (R is confounded for qwen3). For the other nine upgrades R changes little: the same kinds of mistakes in about the same numbers (all upgrades under R: wrong arguments 158, wrong status 157, broken output 73), and churn stays 5% to 28%. So R removes the thinking cut-off problem but not the ordinary version-to-version differences.

## Notes and limits

- **Majority rule:** right = passed in 6 or more of 10 trials. Questions where either model passed exactly 5 of 10 count as not right, which slightly favours "got better" when the old model ties and "got worse" when the new model ties: 190 of the 6,000 D questions and 161 of the R questions have such a tie in at least one model (a question can be counted under two upgrades).
- **Greedy check:** using only the greedy trial gives the same picture with slightly lower counts: D 557 got worse and 488 got better in total (majority: 607 and 524), R 368 and 486 (majority: 395 and 527).
- **Failure type:** the type that was most common among the new model's failing trials on that question. Schema-drift answers that fail several checks are put under the first of: unparsed, wrong tool name, wrong or invalid arguments. A reply that is valid JSON but in the wrong form (for example a number where text is required) counts as "unparsed/broken output".
- **Files:** `EXPLORATORY_item_level_flips_summary.csv` (per protocol, upgrade, suite and basis) and `EXPLORATORY_item_level_flips_questions.csv` (12,000 rows, one per question and protocol).
- **Caveat:** 600 questions per upgrade, not independent (the same tasks appear in both conditions, and a model belongs to two upgrades).

## Noise check (added 2026-11-28)

**EXPLORATORY, post hoc, existing data only.** Script: `scripts/exploratory/_item_level_noise.py` (called by `item_level_flips.py`). Files: `EXPLORATORY_item_level_flips_noise.csv`, `EXPLORATORY_item_level_flips_reconcile.csv`, `EXPLORATORY_item_level_flips_worse_by_condition.csv`.

### 1. Same-model churn: does a model 'churn' against a rerun of itself?

For every model, its main arm (D or R, trials 0-9) is compared with its A/A arm (D_AA2 or R_AA2: the same model, the same tasks and prompts, trial seeds 5678-5687) on the same 600 stress questions, with the same rule as the upgrade table: right = passed in 6 or more of 10 trials. Right->wrong and wrong->right count questions that change sides between the two arms of the **same** model; churn = their sum. For each upgrade: **expected same-model churn** = the mean of the old and the new model's same-model churn (all three suites, 600 questions); **excess** = upgrade churn minus that. The greedy-only rows use trial 0 of each arm.

**Read the greedy rows with care:** trial 0 is greedy in both arms, with the same prompts, and greedy decoding does not depend on the trial seed, so the A/A arm's trial 0 repeats the main arm's trial 0; same-model greedy churn is therefore close to zero by construction and is not a usable noise floor for a greedy comparison (see the counts).

#### D, 10-trial majority

| Upgrade | Upgrade churn (worse / better) | Old model same-model churn (r->w / w->r) | New model same-model churn (r->w / w->r) | Expected same-model churn | Excess churn | Excess as share of 600 |
|---|---|---|---|---|---|---|
| mistral_v01->mistral_v02 | 138 (88 / 50) | 39 (19 / 20) | 31 (19 / 12) | 35.0 | **+103.0** | +17.2% |
| mistral_v02->mistral_v03 | 102 (23 / 79) | 31 (19 / 12) | 15 (8 / 7) | 23.0 | **+79.0** | +13.2% |
| qwen2->qwen25 | 167 (37 / 130) | 28 (12 / 16) | 6 (1 / 5) | 17.0 | **+150.0** | +25.0% |
| qwen25->qwen3 | 269 (240 / 29) | 6 (1 / 5) | 43 (19 / 24) | 24.5 | **+244.5** | +40.8% |
| llama3->llama31 | 92 (55 / 37) | 33 (14 / 19) | 31 (14 / 17) | 32.0 | **+60.0** | +10.0% |
| phi3_mini->phi35_mini | 92 (51 / 41) | 4 (2 / 2) | 9 (7 / 2) | 6.5 | **+85.5** | +14.2% |
| phi35_mini->phi4_mini | 102 (44 / 58) | 9 (7 / 2) | 21 (2 / 19) | 15.0 | **+87.0** | +14.5% |
| granite30->granite31 | 75 (35 / 40) | 10 (9 / 1) | 17 (4 / 13) | 13.5 | **+61.5** | +10.2% |
| granite31->granite32 | 28 (7 / 21) | 17 (4 / 13) | 6 (2 / 4) | 11.5 | **+16.5** | +2.8% |
| gemma2_2b->gemma3_4b | 66 (27 / 39) | 11 (4 / 7) | 2 (1 / 1) | 6.5 | **+59.5** | +9.9% |
| **All 10 upgrades** | 1131 |  |  | 184.5 | **+946.5** | +15.8% |
| **Without qwen25->qwen3** | 862 |  |  | 160.0 | **+702.0** | +13.0% |

#### D, greedy trial only

| Upgrade | Upgrade churn (worse / better) | Old model same-model churn (r->w / w->r) | New model same-model churn (r->w / w->r) | Expected same-model churn | Excess churn | Excess as share of 600 |
|---|---|---|---|---|---|---|
| mistral_v01->mistral_v02 | 116 (78 / 38) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+116.0** | +19.3% |
| mistral_v02->mistral_v03 | 96 (24 / 72) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+96.0** | +16.0% |
| qwen2->qwen25 | 162 (37 / 125) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+162.0** | +27.0% |
| qwen25->qwen3 | 247 (220 / 27) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+247.0** | +41.2% |
| llama3->llama31 | 84 (46 / 38) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+84.0** | +14.0% |
| phi3_mini->phi35_mini | 93 (55 / 38) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+93.0** | +15.5% |
| phi35_mini->phi4_mini | 100 (36 / 64) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+100.0** | +16.7% |
| granite30->granite31 | 68 (27 / 41) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+68.0** | +11.3% |
| granite31->granite32 | 26 (9 / 17) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+26.0** | +4.3% |
| gemma2_2b->gemma3_4b | 53 (25 / 28) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+53.0** | +8.8% |
| **All 10 upgrades** | 1045 |  |  | 0.0 | **+1045.0** | +17.4% |
| **Without qwen25->qwen3** | 798 |  |  | 0.0 | **+798.0** | +14.8% |

#### R, 10-trial majority

| Upgrade | Upgrade churn (worse / better) | Old model same-model churn (r->w / w->r) | New model same-model churn (r->w / w->r) | Expected same-model churn | Excess churn | Excess as share of 600 |
|---|---|---|---|---|---|---|
| mistral_v01->mistral_v02 | 112 (62 / 50) | 38 (19 / 19) | 19 (7 / 12) | 28.5 | **+83.5** | +13.9% |
| mistral_v02->mistral_v03 | 84 (18 / 66) | 19 (7 / 12) | 8 (6 / 2) | 13.5 | **+70.5** | +11.8% |
| qwen2->qwen25 | 167 (37 / 130) | 28 (12 / 16) | 6 (1 / 5) | 17.0 | **+150.0** | +25.0% |
| qwen25->qwen3 | 89 (51 / 38) | 6 (1 / 5) | 24 (11 / 13) | 15.0 | **+74.0** | +12.3% |
| llama3->llama31 | 96 (57 / 39) | 27 (14 / 13) | 31 (14 / 17) | 29.0 | **+67.0** | +11.2% |
| phi3_mini->phi35_mini | 94 (51 / 43) | 6 (3 / 3) | 6 (5 / 1) | 6.0 | **+88.0** | +14.7% |
| phi35_mini->phi4_mini | 106 (48 / 58) | 6 (5 / 1) | 13 (2 / 11) | 9.5 | **+96.5** | +16.1% |
| granite30->granite31 | 80 (39 / 41) | 4 (3 / 1) | 13 (2 / 11) | 8.5 | **+71.5** | +11.9% |
| granite31->granite32 | 31 (6 / 25) | 13 (2 / 11) | 8 (3 / 5) | 10.5 | **+20.5** | +3.4% |
| gemma2_2b->gemma3_4b | 63 (26 / 37) | 10 (2 / 8) | 3 (1 / 2) | 6.5 | **+56.5** | +9.4% |
| **All 10 upgrades** | 922 |  |  | 144.0 | **+778.0** | +13.0% |
| **Without qwen25->qwen3** | 833 |  |  | 129.0 | **+704.0** | +13.0% |

#### R, greedy trial only

| Upgrade | Upgrade churn (worse / better) | Old model same-model churn (r->w / w->r) | New model same-model churn (r->w / w->r) | Expected same-model churn | Excess churn | Excess as share of 600 |
|---|---|---|---|---|---|---|
| mistral_v01->mistral_v02 | 96 (56 / 40) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+96.0** | +16.0% |
| mistral_v02->mistral_v03 | 74 (20 / 54) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+74.0** | +12.3% |
| qwen2->qwen25 | 162 (37 / 125) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+162.0** | +27.0% |
| qwen25->qwen3 | 88 (52 / 36) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+88.0** | +14.7% |
| llama3->llama31 | 85 (46 / 39) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+85.0** | +14.2% |
| phi3_mini->phi35_mini | 96 (55 / 41) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+96.0** | +16.0% |
| phi35_mini->phi4_mini | 104 (41 / 63) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+104.0** | +17.3% |
| granite30->granite31 | 67 (28 / 39) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+67.0** | +11.2% |
| granite31->granite32 | 25 (6 / 19) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+25.0** | +4.2% |
| gemma2_2b->gemma3_4b | 57 (27 / 30) | 0 (0 / 0) | 0 (0 / 0) | 0.0 | **+57.0** | +9.5% |
| **All 10 upgrades** | 854 |  |  | 0.0 | **+854.0** | +14.2% |
| **Without qwen25->qwen3** | 766 |  |  | 0.0 | **+766.0** | +14.2% |

#### Same-model churn per model (10-trial majority, 600 questions; D / R)

| Model | D: r->w / w->r (churn) | R: r->w / w->r (churn) |
|---|---|---|
| gemma2_2b | 4 / 7 (11, 1.8%) | 2 / 8 (10, 1.7%) |
| gemma3_4b | 1 / 1 (2, 0.3%) | 1 / 2 (3, 0.5%) |
| granite30 | 9 / 1 (10, 1.7%) | 3 / 1 (4, 0.7%) |
| granite31 | 4 / 13 (17, 2.8%) | 2 / 11 (13, 2.2%) |
| granite32 | 2 / 4 (6, 1.0%) | 3 / 5 (8, 1.3%) |
| llama3 | 14 / 19 (33, 5.5%) | 14 / 13 (27, 4.5%) |
| llama31 | 14 / 17 (31, 5.2%) | 14 / 17 (31, 5.2%) |
| mistral_v01 | 19 / 20 (39, 6.5%) | 19 / 19 (38, 6.3%) |
| mistral_v02 | 19 / 12 (31, 5.2%) | 7 / 12 (19, 3.2%) |
| mistral_v03 | 8 / 7 (15, 2.5%) | 6 / 2 (8, 1.3%) |
| phi35_mini | 7 / 2 (9, 1.5%) | 5 / 1 (6, 1.0%) |
| phi3_mini | 2 / 2 (4, 0.7%) | 3 / 3 (6, 1.0%) |
| phi4_mini | 2 / 19 (21, 3.5%) | 2 / 11 (13, 2.2%) |
| qwen2 | 12 / 16 (28, 4.7%) | 12 / 16 (28, 4.7%) |
| qwen25 | 1 / 5 (6, 1.0%) | 1 / 5 (6, 1.0%) |
| qwen3 | 19 / 24 (43, 7.2%) | 11 / 13 (24, 4.0%) |

### 2. Why the stress diff and the majority count can disagree

**What the stress diff measures.** For one decision (upgrade x suite) and protocol: for each stress condition, the new model's pass rate minus the old model's pass rate over all matched records (every task, every one of the 10 trials); then the plain mean of the two conditions (schema_drift and fault_reporting weigh the same). Each condition has 100 questions here, so it is the mean, over the 200 questions, of (new passes - old passes) / 10. It counts **every trial** of every question. The majority table counts only **questions that cross the 6-of-10 line**; a question that moves from 9/10 to 6/10, or from 5/10 to 0/10, changes the stress diff but not the count, and a move from 6/10 to 5/10 counts as a full 'got worse' while changing the stress diff by only 0.1 / 200. (Check: recomputed from the records, the stress diff equals the study's value in all 60 decisions, largest difference 6.2e-17.)

The stress diff splits exactly into the contributions of the four majority cells: contribution = sum over the cell's questions of (new passes - old passes) / 10, weighted as in the stress diff. 'Got worse' questions always contribute a negative amount and 'got better' a positive one; 'both right' and 'both wrong' questions move the stress diff without moving the count.

#### mistral_v01 -> mistral_v02

| Protocol | Decision | Stress diff | Old / new mean pass rate | Majority: worse / better / net | Contribution to the stress diff: got worse / got better / both right / both wrong | Ties at 5/10 (old / new) |
|---|---|---|---|---|---|---|
| D | mistral_v01->mistral_v02, three suites (mean of the suites' diffs; counts summed) | -0.0005 | 0.7728 / 0.7723 | 88 / 50 / -38 | -0.0948 / +0.0487 / +0.0503 / -0.0047 | 19 / 8 |
| D | mistral_v01->mistral_v02 / synthetic | -0.0045 | 0.8890 / 0.8845 | 20 / 8 / -12 | -0.0735 / +0.0240 / +0.0465 / -0.0015 | 4 / 2 |
| D | mistral_v01->mistral_v02 / bfcl_simple | +0.0095 | 0.7180 / 0.7275 | 30 / 19 / -11 | -0.0910 / +0.0540 / +0.0505 / -0.0040 | 8 / 3 |
| D | mistral_v01->mistral_v02 / bfcl_multiple | -0.0065 | 0.7115 / 0.7050 | 38 / 23 / -15 | -0.1200 / +0.0680 / +0.0540 / -0.0085 | 7 / 3 |
| R | mistral_v01->mistral_v02, three suites (mean of the suites' diffs; counts summed) | +0.0472 | 0.7558 / 0.8030 | 62 / 50 / -12 | -0.0650 / +0.0523 / +0.0668 / -0.0070 | 17 / 9 |
| R | mistral_v01->mistral_v02 / synthetic | +0.0190 | 0.8865 / 0.9055 | 16 / 8 / -8 | -0.0585 / +0.0230 / +0.0565 / -0.0020 | 4 / 1 |
| R | mistral_v01->mistral_v02 / bfcl_simple | +0.0595 | 0.6940 / 0.7535 | 21 / 18 / -3 | -0.0615 / +0.0560 / +0.0780 / -0.0130 | 6 / 3 |
| R | mistral_v01->mistral_v02 / bfcl_multiple | +0.0630 | 0.6870 / 0.7500 | 25 / 24 / -1 | -0.0750 / +0.0780 / +0.0660 / -0.0060 | 7 / 5 |

**Questions by number of passes out of 10 (mistral_v01 -> mistral_v02, three suites, 600 questions):**

| Protocol | Model | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Mean passes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D | mistral_v01 (old) | 27 | 11 | 10 | 20 | 9 | 19 | 54 | 87 | 23 | 102 | 238 | 7.728 |
| D | mistral_v02 (new) | 63 | 15 | 12 | 14 | 22 | 8 | 13 | 39 | 16 | 34 | 364 | 7.723 |
| R | mistral_v01 (old) | 30 | 12 | 8 | 20 | 19 | 17 | 54 | 86 | 38 | 104 | 212 | 7.558 |
| R | mistral_v02 (new) | 66 | 12 | 5 | 15 | 11 | 9 | 5 | 27 | 13 | 31 | 406 | 8.030 |

#### Every decision where the sign of the stress diff and the sign of the majority net disagree (7 of 60: D 3, R 4)

| Protocol | Decision | Stress diff | Old / new mean pass rate | Majority: worse / better / net | Contribution to the stress diff: got worse / got better / both right / both wrong | Ties at 5/10 (old / new) |
|---|---|---|---|---|---|---|
| D | mistral_v01->mistral_v02 / bfcl_simple | +0.0095 | 0.7180 / 0.7275 | 30 / 19 / -11 | -0.0910 / +0.0540 / +0.0505 / -0.0040 | 8 / 3 |
| D | phi35_mini->phi4_mini / synthetic | +0.0250 | 0.8630 / 0.8880 | 15 / 14 / -1 | -0.0460 / +0.0665 / +0.0020 / +0.0025 | 0 / 6 |
| D | gemma2_2b->gemma3_4b / synthetic | +0.0055 | 0.9545 / 0.9600 | 6 / 4 / -2 | -0.0155 / +0.0115 / +0.0110 / -0.0015 | 3 / 2 |
| R | mistral_v01->mistral_v02 / synthetic | +0.0190 | 0.8865 / 0.9055 | 16 / 8 / -8 | -0.0585 / +0.0230 / +0.0565 / -0.0020 | 4 / 1 |
| R | mistral_v01->mistral_v02 / bfcl_simple | +0.0595 | 0.6940 / 0.7535 | 21 / 18 / -3 | -0.0615 / +0.0560 / +0.0780 / -0.0130 | 6 / 3 |
| R | mistral_v01->mistral_v02 / bfcl_multiple | +0.0630 | 0.6870 / 0.7500 | 25 / 24 / -1 | -0.0750 / +0.0780 / +0.0660 / -0.0060 | 7 / 5 |
| R | gemma2_2b->gemma3_4b / synthetic | +0.0090 | 0.9530 / 0.9620 | 6 / 4 / -2 | -0.0155 / +0.0115 / +0.0135 / -0.0005 | 3 / 2 |

#### Upgrade level (three suites together): sign disagreements, and upgrades with |mean stress diff| < 0.001

| Protocol | Decision | Stress diff | Old / new mean pass rate | Majority: worse / better / net | Contribution to the stress diff: got worse / got better / both right / both wrong | Ties at 5/10 (old / new) |
|---|---|---|---|---|---|---|
| D | mistral_v01->mistral_v02, three suites | -0.0005 | 0.7728 / 0.7723 | 88 / 50 / -38 | -0.0948 / +0.0487 / +0.0503 / -0.0047 | 19 / 8 |
| R | mistral_v01->mistral_v02, three suites | +0.0472 | 0.7558 / 0.8030 | 62 / 50 / -12 | -0.0650 / +0.0523 / +0.0668 / -0.0070 | 17 / 9 |

Per-decision pass-count distributions (0..10) for both models of every decision are in `EXPLORATORY_item_level_flips_reconcile.csv`.

### 3. 'Got worse' failure types by stress condition

Same questions and the same failure-type rule as the tables above (most common failure type among the new model's failing trials), split by the stress condition of the question.

#### Default protocol (D)

| Upgrades | Condition | Got worse | wrong tool name | wrong/invalid arguments | unparsed/broken output | fault-reporting wrong status | fabricated answer | other |
|---|---|---|---|---|---|---|---|---|
| all 10 | fault_reporting | 316 | 0 | 0 | 159 | 156 | 1 | 0 |
| all 10 | schema_drift | 291 | 4 | 148 | 139 | 0 | 0 | 0 |
| without qwen25->qwen3 | fault_reporting | 203 | 0 | 0 | 47 | 155 | 1 | 0 |
| without qwen25->qwen3 | schema_drift | 164 | 4 | 143 | 17 | 0 | 0 | 0 |
| qwen25->qwen3 only | fault_reporting | 113 | 0 | 0 | 112 | 1 | 0 | 0 |
| qwen25->qwen3 only | schema_drift | 127 | 0 | 5 | 122 | 0 | 0 | 0 |

#### Robust protocol (R)

| Upgrades | Condition | Got worse | wrong tool name | wrong/invalid arguments | unparsed/broken output | fault-reporting wrong status | fabricated answer | other |
|---|---|---|---|---|---|---|---|---|
| all 10 | fault_reporting | 216 | 0 | 0 | 56 | 157 | 3 | 0 |
| all 10 | schema_drift | 179 | 4 | 158 | 17 | 0 | 0 | 0 |
| without qwen25->qwen3 | fault_reporting | 199 | 0 | 0 | 43 | 155 | 1 | 0 |
| without qwen25->qwen3 | schema_drift | 145 | 4 | 141 | 0 | 0 | 0 | 0 |
| qwen25->qwen3 only | fault_reporting | 17 | 0 | 0 | 13 | 2 | 2 | 0 |
| qwen25->qwen3 only | schema_drift | 34 | 0 | 17 | 17 | 0 | 0 | 0 |

### Plain-language summary of the noise check

- **The item-level churn is real, not rerun noise.** A model compared with a rerun of itself changes sides on few questions: 0.3% to 7.2% of its 600 questions under D (qwen3 the most, 43), 0.5% to 6.3% under R. Every upgrade churns far more than that. Over all 10 upgrades, D churn is 1,131 questions against an expected 184.5 from same-model noise (excess +946.5, 15.8% of the questions); without qwen25 -> qwen3 it is 862 against 160 (excess +702, 13.0%). R gives the same picture (excess +778 overall, +704 without qwen25 -> qwen3). The smallest case, granite31 -> granite32, still has 28 changed questions against about 11.5 expected.
- **Caveats on that noise floor.**
  - The two arms of a model share trial 0, the greedy trial, which is identical in both arms (9,600 of 9,600 stress records have the same score). So 1 of the 10 trials is not an independent draw, and the same-model churn slightly understates fully independent rerun noise.
  - For the same reason, the greedy-only rows have a same-model churn of exactly 0 and **cannot serve as a noise floor**. Their "excess" is just the upgrade churn.
  - The expected churn uses the mean of the two models' own churn, as asked. It is a rough yardstick, not a model of how the noise of two different models combines.
- **Why mistral_v01 -> mistral_v02 shows a 'neutral' stress diff but a net of -38 questions under D.**
  - The two numbers measure different things. The stress diff averages **every trial** of every question: mean pass rate 0.7728 vs 0.7723, a diff of -0.0005. The majority count only records **questions that cross the 6-of-10 line**.
  - mistral_v02 is much more all-or-nothing than mistral_v01. It has 364 questions at 10/10 (v01: 238) and 63 at 0/10 (v01: 27), while v01 has 266 questions sitting at 6-9 of 10 (v02: 102).
  - The 88 questions that drop below the line ('got worse') cost 0.095 of stress diff. The 50 that cross upward ('got better') add +0.049.
  - The 'both right' questions, which the count ignores, add +0.050 on balance. This fits v02 pushing many questions that v01 passed 6-9 times up to 10/10 (see the distribution), and it cancels the loss.
  - The 6-of-10 rule also treats a tie at 5/10 as wrong; v01 has 19 such questions, v02 has 8.
  - So "no net change" and "38 more questions lost than gained" are both true. The net count is not an alternative estimate of the score change.
- **The same pattern explains every sign disagreement** (7 of 60 decisions: D 3, R 4). In each one the 'both right' cell (questions moving up toward 10/10) carries the positive stress diff, while the crossing counts lean negative. Under R, mistral_v01 -> v02 has a clearly positive stress diff on bfcl_simple and bfcl_multiple (+0.060 and +0.063) and a still negative majority net (-3 and -1).
- **What this weakens:** the item-level tables' "net" and "got worse" counts depend on the 6-of-10 threshold, and they lean negative when the new model is more all-or-nothing. They should not be read as the direction of the upgrade; the stress diff is the study's measure. The churn claim (many questions change sides under a near-zero net score) stands, and the noise check makes it stronger.
- **Failure types by condition:**
  - Without qwen25 -> qwen3, 'got worse' under D is mostly wrong status on fault_reporting (155 of 203 fault_reporting questions) and wrong or invalid arguments on schema_drift (143 of 164). Broken output accounts for 47 fault_reporting and 17 schema_drift questions.
  - qwen25 -> qwen3 under D is almost all broken output on both conditions (112 of 113 fault_reporting, 122 of 127 schema_drift).
  - Under R, broken output on schema_drift drops to 0 without qwen25 -> qwen3, as expected with the JSON grammar.
