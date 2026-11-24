**EXPLORATORY, post hoc. Not pre-registered. Existing data only, no reruns; descriptive.** Analysis state: tag pre-analysis-v2.3 (commit 73a9017). Stress conditions (schema_drift + fault_reporting), 10 upgrades x 3 suites = 30 decisions, protocols D and R reported separately.

# How often does a one-run upgrade test give the wrong ship / don't-ship call?

## Definitions (what was compared with what)

- **Reference verdict ('truth').** For each decision and protocol, the verdict of the **A/A rerun arm** (D_AA2 for D, R_AA2 for R) over all 10 trials, using the pre-registered CI gate for harmful/beneficial and the 90% equivalence test (TOST, +/-0.05) for neutral, otherwise *inconclusive* (the study's four-class verdict, S3). The main runs are not used for the reference. Where the reference itself is *inconclusive* the truth is undetermined, so **those decisions are left out of every error rate** and counted separately.
- **Naive test.** One trial of the main run (each of trials 0 to 9 on its own: 10 naive calls per decision), stress diff = new minus old model score, point gate at +/-0.05, forced to say harmful, neutral or beneficial.
- **Error kinds.** *Serious* = harmful called beneficial or the reverse. *Mild* = neutral called harmful or beneficial, or harmful/beneficial called neutral.
- **Calibrated method.** The main run over all 10 trials with the study's four-class verdict (S3): CI gate for harmful/beneficial, TOST for neutral, *inconclusive* allowed. 'Calibrated' means the gate's error behaviour was measured on A/A reruns (false-alarm rate 4.2% for the R gate, 2.1% for the D point gate). A separate rule that additionally required |stress diff| to exceed an A/A noise bound is not used: under D that bound (the 95th percentile of |diff| over the A/A decisions, 0.040, from the F5 table of the main analysis) is below the 0.05 gate, so it would change no D verdict (not checked for R). Its verdicts are compared with the reference only where it is definite; 'wrong' = a definite call that differs from a definite reference.
- **Broken-output check.** Per model x suite x protocol: the share of stress-condition outputs (all 10 trials) that are unparsed or broken (the scorer found no valid reply) **or** hit the token limit. A decision is flagged 'don't trust' if the share for either model is **above** the threshold (5%, 10% or 20%).

## Results, protocol D

### D: all 30 decisions

Decisions: 30; reference definite: 18; reference inconclusive (left out): 12.

| Method | Calls or decisions | Wrong | Serious | Mild | Inconclusive |
|---|---|---|---|---|---|
| **Naive, one trial** | 180 calls (18 decisions x 10 trials) | **18.3%** (33) | 2.2% (4) | 16.1% (29) | not allowed |
| **Calibrated, 10 trials** | 18 decisions | **0.0%** (0; 0.0% of its 16 definite calls) | 0.0% (0) | 0.0% (0) | **11.1%** (2) |

- **The 10 single-trial naive calls disagree with each other** for 55.6% of the decisions (10 of 18: not all 10 calls identical); on average 21.7% of pairs of calls for the same decision differ.
- **Broken-output check:** decisions flagged 'don't trust' (of all decisions with a definite reference): above 5%: **61.1%** (11); above 10%: **16.7%** (3); above 20%: **11.1%** (2).
- After dropping the flagged decisions: calibrated wrong at 5%: 0.0% of 6 definite calls; at 10%: 0.0% of 13 definite calls; at 20%: 0.0% of 14 definite calls; naive wrong at 5%: 24.3% of 70 calls; at 10%: 21.3% of 150 calls; at 20%: 20.6% of 160 calls.

### D: without qwen25->qwen3 (27)

Decisions: 27; reference definite: 15; reference inconclusive (left out): 12.

| Method | Calls or decisions | Wrong | Serious | Mild | Inconclusive |
|---|---|---|---|---|---|
| **Naive, one trial** | 150 calls (15 decisions x 10 trials) | **21.3%** (32) | 2.7% (4) | 18.7% (28) | not allowed |
| **Calibrated, 10 trials** | 15 decisions | **0.0%** (0; 0.0% of its 13 definite calls) | 0.0% (0) | 0.0% (0) | **13.3%** (2) |

- **The 10 single-trial naive calls disagree with each other** for 60.0% of the decisions (9 of 15: not all 10 calls identical); on average 24.7% of pairs of calls for the same decision differ.
- **Broken-output check:** decisions flagged 'don't trust' (of all decisions with a definite reference): above 5%: **53.3%** (8); above 10%: **0.0%** (0); above 20%: **0.0%** (0).
- After dropping the flagged decisions: calibrated wrong at 5%: 0.0% of 6 definite calls; at 10%: 0.0% of 13 definite calls; at 20%: 0.0% of 13 definite calls; naive wrong at 5%: 24.3% of 70 calls; at 10%: 21.3% of 150 calls; at 20%: 21.3% of 150 calls.

### D: which decisions the broken-output check flags

| Threshold | Flagged decisions (share of old / new model outputs broken or at the limit) |
|---|---|
| above 5% (17 of 30) | mistral_v01->mistral_v02 / bfcl_simple (5% / 6%); mistral_v01->mistral_v02 / bfcl_multiple (4% / 8%); mistral_v02->mistral_v03 / bfcl_simple (6% / 1%); mistral_v02->mistral_v03 / bfcl_multiple (8% / 0%); qwen2->qwen25 / synthetic (9% / 0%); qwen2->qwen25 / bfcl_simple (9% / 0%); qwen2->qwen25 / bfcl_multiple (9% / 0%); qwen25->qwen3 / synthetic (0% / 20%); qwen25->qwen3 / bfcl_simple (0% / 46%); qwen25->qwen3 / bfcl_multiple (0% / 57%); llama3->llama31 / synthetic (6% / 1%); llama3->llama31 / bfcl_simple (6% / 4%); llama3->llama31 / bfcl_multiple (5% / 3%); phi3_mini->phi35_mini / bfcl_simple (3% / 8%); phi3_mini->phi35_mini / bfcl_multiple (2% / 9%); phi35_mini->phi4_mini / bfcl_simple (8% / 2%); phi35_mini->phi4_mini / bfcl_multiple (9% / 1%) |
| above 10% (3 of 30) | qwen25->qwen3 / synthetic (0% / 20%); qwen25->qwen3 / bfcl_simple (0% / 46%); qwen25->qwen3 / bfcl_multiple (0% / 57%) |
| above 20% (2 of 30) | qwen25->qwen3 / bfcl_simple (0% / 46%); qwen25->qwen3 / bfcl_multiple (0% / 57%) |

## Results, protocol R

### R: all 30 decisions

Decisions: 30; reference definite: 15; reference inconclusive (left out): 15.

| Method | Calls or decisions | Wrong | Serious | Mild | Inconclusive |
|---|---|---|---|---|---|
| **Naive, one trial** | 150 calls (15 decisions x 10 trials) | **19.3%** (29) | 0.0% (0) | 19.3% (29) | not allowed |
| **Calibrated, 10 trials** | 15 decisions | **6.7%** (1; 7.1% of its 14 definite calls) | 0.0% (0) | 6.7% (1) | **6.7%** (1) |

- **The 10 single-trial naive calls disagree with each other** for 73.3% of the decisions (11 of 15: not all 10 calls identical); on average 27.1% of pairs of calls for the same decision differ.
- **Broken-output check:** decisions flagged 'don't trust' (of all decisions with a definite reference): above 5%: **33.3%** (5); above 10%: **6.7%** (1); above 20%: **0.0%** (0).
- After dropping the flagged decisions: calibrated wrong at 5%: 10.0% of 10 definite calls; at 10%: 7.7% of 13 definite calls; at 20%: 7.1% of 14 definite calls; naive wrong at 5%: 18.0% of 100 calls; at 10%: 17.1% of 140 calls; at 20%: 19.3% of 150 calls.

### R: without qwen25->qwen3 (27)

Decisions: 27; reference definite: 13; reference inconclusive (left out): 14.

| Method | Calls or decisions | Wrong | Serious | Mild | Inconclusive |
|---|---|---|---|---|---|
| **Naive, one trial** | 130 calls (13 decisions x 10 trials) | **13.8%** (18) | 0.0% (0) | 13.8% (18) | not allowed |
| **Calibrated, 10 trials** | 13 decisions | **7.7%** (1; 7.7% of its 13 definite calls) | 0.0% (0) | 7.7% (1) | **0.0%** (0) |

- **The 10 single-trial naive calls disagree with each other** for 69.2% of the decisions (9 of 13: not all 10 calls identical); on average 22.9% of pairs of calls for the same decision differ.
- **Broken-output check:** decisions flagged 'don't trust' (of all decisions with a definite reference): above 5%: **23.1%** (3); above 10%: **0.0%** (0); above 20%: **0.0%** (0).
- After dropping the flagged decisions: calibrated wrong at 5%: 10.0% of 10 definite calls; at 10%: 7.7% of 13 definite calls; at 20%: 7.7% of 13 definite calls; naive wrong at 5%: 18.0% of 100 calls; at 10%: 13.8% of 130 calls; at 20%: 13.8% of 130 calls.

### R: which decisions the broken-output check flags

| Threshold | Flagged decisions (share of old / new model outputs broken or at the limit) |
|---|---|
| above 5% (8 of 30) | qwen2->qwen25 / synthetic (9% / 0%); qwen2->qwen25 / bfcl_simple (9% / 0%); qwen2->qwen25 / bfcl_multiple (9% / 0%); qwen25->qwen3 / synthetic (0% / 12%); qwen25->qwen3 / bfcl_simple (0% / 7%); qwen25->qwen3 / bfcl_multiple (0% / 6%); phi3_mini->phi35_mini / bfcl_simple (3% / 6%); phi35_mini->phi4_mini / bfcl_simple (6% / 2%) |
| above 10% (1 of 30) | qwen25->qwen3 / synthetic (0% / 12%) |
| above 20% (0 of 30) | none |

## Plain-language summary

- **D, all 30 decisions:** A one-run test gave the wrong call **18.3%** of the time (2.2% serious); the calibrated method was wrong **0.0%** of the time and said 'inconclusive' **11.1%** of the time (broken-output check flags 16.7% of decisions at a 10% threshold).
- **D, without qwen25->qwen3 (27):** A one-run test gave the wrong call **21.3%** of the time (2.7% serious); the calibrated method was wrong **0.0%** of the time and said 'inconclusive' **13.3%** of the time (broken-output check flags 0.0% of decisions at a 10% threshold).
- **R, all 30 decisions:** A one-run test gave the wrong call **19.3%** of the time (0.0% serious); the calibrated method was wrong **6.7%** of the time and said 'inconclusive' **6.7%** of the time (broken-output check flags 6.7% of decisions at a 10% threshold).
- **R, without qwen25->qwen3 (27):** A one-run test gave the wrong call **13.8%** of the time (0.0% serious); the calibrated method was wrong **7.7%** of the time and said 'inconclusive' **0.0%** of the time (broken-output check flags 0.0% of decisions at a 10% threshold).

## Where the errors come from

- **Reference verdicts (A/A arm):** D: 8 beneficial, 5 neutral, 5 harmful, **12 inconclusive**. R: 6 beneficial, 6 neutral, 3 harmful, **15 inconclusive**. The calibrated method's own verdicts on the main run are D: 7 beneficial, 9 neutral, 4 harmful, 10 inconclusive; R: 9 beneficial, 8 neutral, 3 harmful, 10 inconclusive.
- **The 4 serious naive errors under D** (a one-trial call that swapped harmful and beneficial) all come from two decisions: *mistral_v01 -> v02 on bfcl_multiple* (reference harmful; three single-trial calls said beneficial) and *mistral_v02 -> v03 on synthetic* (reference beneficial; one single-trial call said harmful).
- **The one calibrated error under R:** *mistral_v01 -> v02 on bfcl_simple*, where the reference says neutral and the main run's CI gate says beneficial. Under D the calibrated method made no definite call that differed from a definite reference.
- **Important selection effect:** the decisions whose reference is inconclusive (12 under D, 15 under R) cannot be scored, and they are the borderline decisions where a one-run test is most likely to be wrong. The naive error rates above are therefore measured on the easier decisions and are probably an underestimate of how often a one-run test is wrong on a typical borderline upgrade.

## Caveats

- The 'truth' is itself an estimate: the A/A arm is another noisy 10-trial run of the same models, so the reference can share some noise with the main run (they are separate trials, same prompts) and is inconclusive for several decisions; the error rates are errors against that reference, not against an unknowable true quality.
- 30 decisions (27 without qwen25->qwen3), not independent (a model belongs to two upgrades; D and R use the same tasks); the 10 naive calls per decision are not independent either, so the percentages carry no confidence interval and should be read as rough.
- The naive test is the harshest simple version (one trial, point gate, no inconclusive); a naive test that used the same 10 trials with the point gate would be the 'main run' D verdict.
- Broken-output shares use the scorer's `parse_ok` plus the stored token-limit flag over stress conditions only; they include qwen3's long thinking that hits the 256 limit under D.
- Files: `EXPLORATORY_wrong_calls_decisions.csv` (60 rows: reference, calibrated verdict, the 10 naive calls, errors, flags), `EXPLORATORY_wrong_calls_bad_output_shares.csv` (model x suite x protocol).

## More runs vs. the method

**EXPLORATORY, post hoc, existing data only.** Same A/A reference and the same scored decisions as above (decisions whose reference is inconclusive are left out of every error rate). All versions use the main run. 'Naive' = point gate at +/-0.05, forced to say harmful, neutral or beneficial. Groups of trials are disjoint and pooled (all records of the trials in the group, equal weight): 3 trials = trials 0-2, 3-5, 6-8 (trial 9 unused; 3 calls per decision); 5 trials = 0-4 and 5-9 (2 calls); 10 trials = all (1 call). '3 trials + inconclusive' applies the study's four-class verdict (95% CI gate for harmful/beneficial, 90% equivalence test for neutral, otherwise inconclusive; task-level bootstrap, B = 10,000, seed 1234) to each group of 3 trials. Shares are over calls (decisions x calls per decision); serious = harmful and beneficial swapped, mild = neutral against harmful or beneficial.

### D: all 30 decisions

| Version | Trials per call | Calls | Wrong | Serious | Mild | Inconclusive | Wrong among its definite calls |
|---|---|---|---|---|---|---|---|
| 1 trial, naive (previous section) | 1 | 180 (18 decisions) | **18.3%** (33) | 2.2% (4) | 16.1% (29) | not allowed | 18.3% of 180 |
| 3 trials pooled, naive | 3 | 54 (18 decisions) | **14.8%** (8) | 1.9% (1) | 13.0% (7) | not allowed | 14.8% of 54 |
| 5 trials pooled, naive | 5 | 36 (18 decisions) | **13.9%** (5) | 0.0% (0) | 13.9% (5) | not allowed | 13.9% of 36 |
| 10 trials pooled, naive (point gate on all trials) | 10 | 18 (18 decisions) | **11.1%** (2) | 0.0% (0) | 11.1% (2) | not allowed | 11.1% of 18 |
| 3 trials + CI gate + 'inconclusive' allowed | 3 | 54 (18 decisions) | **5.6%** (3) | 1.9% (1) | 3.7% (2) | 13.0% (7) | 6.4% of 47 |
| 10 trials + CI gate + 'inconclusive' allowed (the calibrated method) | 10 | 18 (18 decisions) | **0.0%** (0) | 0.0% (0) | 0.0% (0) | 11.1% (2) | 0.0% of 16 |

### D: without qwen25->qwen3

| Version | Trials per call | Calls | Wrong | Serious | Mild | Inconclusive | Wrong among its definite calls |
|---|---|---|---|---|---|---|---|
| 1 trial, naive (previous section) | 1 | 150 (15 decisions) | **21.3%** (32) | 2.7% (4) | 18.7% (28) | not allowed | 21.3% of 150 |
| 3 trials pooled, naive | 3 | 45 (15 decisions) | **17.8%** (8) | 2.2% (1) | 15.6% (7) | not allowed | 17.8% of 45 |
| 5 trials pooled, naive | 5 | 30 (15 decisions) | **16.7%** (5) | 0.0% (0) | 16.7% (5) | not allowed | 16.7% of 30 |
| 10 trials pooled, naive (point gate on all trials) | 10 | 15 (15 decisions) | **13.3%** (2) | 0.0% (0) | 13.3% (2) | not allowed | 13.3% of 15 |
| 3 trials + CI gate + 'inconclusive' allowed | 3 | 45 (15 decisions) | **6.7%** (3) | 2.2% (1) | 4.4% (2) | 15.6% (7) | 7.9% of 38 |
| 10 trials + CI gate + 'inconclusive' allowed (the calibrated method) | 10 | 15 (15 decisions) | **0.0%** (0) | 0.0% (0) | 0.0% (0) | 13.3% (2) | 0.0% of 13 |

### R: all 30 decisions

| Version | Trials per call | Calls | Wrong | Serious | Mild | Inconclusive | Wrong among its definite calls |
|---|---|---|---|---|---|---|---|
| 1 trial, naive (previous section) | 1 | 150 (15 decisions) | **19.3%** (29) | 0.0% (0) | 19.3% (29) | not allowed | 19.3% of 150 |
| 3 trials pooled, naive | 3 | 45 (15 decisions) | **15.6%** (7) | 0.0% (0) | 15.6% (7) | not allowed | 15.6% of 45 |
| 5 trials pooled, naive | 5 | 30 (15 decisions) | **13.3%** (4) | 0.0% (0) | 13.3% (4) | not allowed | 13.3% of 30 |
| 10 trials pooled, naive (point gate on all trials) | 10 | 15 (15 decisions) | **13.3%** (2) | 0.0% (0) | 13.3% (2) | not allowed | 13.3% of 15 |
| 3 trials + CI gate + 'inconclusive' allowed | 3 | 45 (15 decisions) | **6.7%** (3) | 0.0% (0) | 6.7% (3) | 13.3% (6) | 7.7% of 39 |
| 10 trials + CI gate + 'inconclusive' allowed (the calibrated method) | 10 | 15 (15 decisions) | **6.7%** (1) | 0.0% (0) | 6.7% (1) | 6.7% (1) | 7.1% of 14 |

### R: without qwen25->qwen3

| Version | Trials per call | Calls | Wrong | Serious | Mild | Inconclusive | Wrong among its definite calls |
|---|---|---|---|---|---|---|---|
| 1 trial, naive (previous section) | 1 | 130 (13 decisions) | **13.8%** (18) | 0.0% (0) | 13.8% (18) | not allowed | 13.8% of 130 |
| 3 trials pooled, naive | 3 | 39 (13 decisions) | **7.7%** (3) | 0.0% (0) | 7.7% (3) | not allowed | 7.7% of 39 |
| 5 trials pooled, naive | 5 | 26 (13 decisions) | **7.7%** (2) | 0.0% (0) | 7.7% (2) | not allowed | 7.7% of 26 |
| 10 trials pooled, naive (point gate on all trials) | 10 | 13 (13 decisions) | **7.7%** (1) | 0.0% (0) | 7.7% (1) | not allowed | 7.7% of 13 |
| 3 trials + CI gate + 'inconclusive' allowed | 3 | 39 (13 decisions) | **7.7%** (3) | 0.0% (0) | 7.7% (3) | 5.1% (2) | 8.1% of 37 |
| 10 trials + CI gate + 'inconclusive' allowed (the calibrated method) | 10 | 13 (13 decisions) | **7.7%** (1) | 0.0% (0) | 7.7% (1) | 0.0% (0) | 7.7% of 13 |

### The dropped decisions (reference inconclusive) and what a one-trial test says about them

**D: 12 of 30 decisions have an inconclusive reference.**

| Upgrade | Suite | 10-trial calibrated verdict | One-trial calls (of 10): harmful / neutral / beneficial |
|---|---|---|---|
| mistral_v01->mistral_v02 | synthetic | neutral | 4 / 4 / 2 |
| mistral_v01->mistral_v02 | bfcl_simple | neutral | 4 / 3 / 3 |
| llama3->llama31 | bfcl_simple | inconclusive | 2 / 8 / 0 |
| llama3->llama31 | bfcl_multiple | inconclusive | 3 / 7 / 0 |
| phi3_mini->phi35_mini | bfcl_simple | inconclusive | 0 / 9 / 1 |
| phi3_mini->phi35_mini | bfcl_multiple | inconclusive | 1 / 9 / 0 |
| phi35_mini->phi4_mini | synthetic | inconclusive | 0 / 8 / 2 |
| phi35_mini->phi4_mini | bfcl_simple | inconclusive | 0 / 10 / 0 |
| granite30->granite31 | synthetic | inconclusive | 0 / 10 / 0 |
| granite30->granite31 | bfcl_simple | neutral | 0 / 9 / 1 |
| granite30->granite31 | bfcl_multiple | neutral | 1 / 9 / 0 |
| gemma2_2b->gemma3_4b | bfcl_simple | inconclusive | 0 / 9 / 1 |

Over these 12 decisions (120 one-trial calls): **20.8% of the calls said harmful or beneficial anyway** (15 harmful, 10 beneficial); 79.2% said neutral. For comparison, the 10-trial calibrated method said 'inconclusive' on 8 of the 12.

**R: 15 of 30 decisions have an inconclusive reference.**

| Upgrade | Suite | 10-trial calibrated verdict | One-trial calls (of 10): harmful / neutral / beneficial |
|---|---|---|---|
| mistral_v01->mistral_v02 | bfcl_multiple | beneficial | 0 / 6 / 4 |
| mistral_v02->mistral_v03 | synthetic | neutral | 1 / 9 / 0 |
| qwen25->qwen3 | bfcl_simple | inconclusive | 0 / 10 / 0 |
| llama3->llama31 | synthetic | inconclusive | 2 / 8 / 0 |
| llama3->llama31 | bfcl_simple | harmful | 6 / 4 / 0 |
| llama3->llama31 | bfcl_multiple | inconclusive | 4 / 6 / 0 |
| phi3_mini->phi35_mini | bfcl_simple | inconclusive | 0 / 10 / 0 |
| phi3_mini->phi35_mini | bfcl_multiple | inconclusive | 0 / 10 / 0 |
| phi35_mini->phi4_mini | synthetic | inconclusive | 1 / 9 / 0 |
| phi35_mini->phi4_mini | bfcl_simple | inconclusive | 0 / 10 / 0 |
| granite30->granite31 | synthetic | inconclusive | 0 / 10 / 0 |
| granite30->granite31 | bfcl_simple | neutral | 0 / 10 / 0 |
| granite30->granite31 | bfcl_multiple | neutral | 1 / 9 / 0 |
| gemma2_2b->gemma3_4b | bfcl_simple | inconclusive | 0 / 9 / 1 |
| gemma2_2b->gemma3_4b | bfcl_multiple | beneficial | 0 / 6 / 4 |

Over these 15 decisions (150 one-trial calls): **16.0% of the calls said harmful or beneficial anyway** (15 harmful, 9 beneficial); 84.0% said neutral. For comparison, the 10-trial calibrated method said 'inconclusive' on 9 of the 15.

### Plain-language summary: how much comes from more runs, how much from "inconclusive"

Wrong-call share over calls, scored decisions only (all 30 decisions):

| | 1 trial | 3 pooled | 5 pooled | 10 pooled | 3 trials + inconclusive | 10 trials + inconclusive |
|---|---|---|---|---|---|---|
| **D** wrong | 18.3% | 14.8% | 13.9% | 11.1% | 5.6% (13.0% inconclusive) | 0.0% (11.1% inconclusive) |
| **R** wrong | 19.3% | 15.6% | 13.3% | 13.3% | 6.7% (13.3% inconclusive) | 6.7% (6.7% inconclusive) |
| D wrong, without qwen25->qwen3 | 21.3% | 17.8% | 16.7% | 13.3% | 6.7% (15.6% inconclusive) | 0.0% (13.3% inconclusive) |
| R wrong, without qwen25->qwen3 | 13.8% | 7.7% | 7.7% | 7.7% | 7.7% (5.1% inconclusive) | 7.7% (0.0% inconclusive) |

- **More runs help, but only part of the way.** Pooling all 10 trials but still forcing a call lowers the wrong-call share from 18.3% to 11.1% (D) and from 19.3% to 13.3% (R). Serious errors (harmful against beneficial) disappear from 5 trials upward; the remaining errors are mild (a neutral called harmful or beneficial, or the reverse). About half (D) to over half (R) of that gain is already there at 3 trials.
- **Allowing "inconclusive" (with the CI gate) is the larger gain.** At 10 trials it takes the wrong share from 11.1% to 0.0% (D) and from 13.3% to 6.7% (R). Splitting the total improvement from a one-run test to the calibrated method: for D (all 30), 18.3 points in all, of which about 7 points (39%) come from more runs and about 11 points (61%) from allowing "inconclusive"; for R, 12.6 points in all, about 6 points (48%) and 6.6 points (52%). Without qwen25->qwen3, D splits 38% / 62%, and for R all of the gain (13.8% to 7.7%) is from more runs, since "inconclusive" adds nothing there.
- **The price of "inconclusive"** is the share of decisions with no call: 11% (D) and 7% (R) at 10 trials; 13% at 3 trials.
- **The cheapest version that keeps wrong calls low is 3 trials with the CI gate and "inconclusive" allowed:** about 6% wrong (D) and 7% wrong (R), with 13% of calls inconclusive. That beats a forced call on all 10 trials (11% and 13% wrong) with less than a third of the runs. Going to 10 trials with "inconclusive" adds little for R (6.7% either way, one decision) and removes the last 5.6% for D (3 wrong calls of 54, one of them serious).
- **Limits:** 15 to 18 scored decisions (13 to 15 without qwen25->qwen3), and for the 3-trial versions only 39 to 54 calls, so a "wrong" count is 3 calls in several cells and the percentages are rough. The remaining R error (6.7% at 10 trials) is one decision (mistral_v01 -> v02 on bfcl_simple). The groups of 3 trials are the fixed groups 0-2, 3-5, 6-8, not random draws.
- **Boundary rule:** a stress diff of exactly +0.05 or -0.05 counts as neutral (strict inequality); I round to 9 decimals so floating-point noise cannot decide it. Four single-trial calls in the earlier CSV (all in decisions with an inconclusive reference) had been harmful or beneficial only because of floating-point noise at an exact +/-0.05; they are neutral now and the CSV is updated. They affect only the dropped-decision table, not any scored rate.
