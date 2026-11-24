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

