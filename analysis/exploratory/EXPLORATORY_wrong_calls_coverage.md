**EXPLORATORY, post hoc. Not pre-registered. Existing data only, no reruns; descriptive; feeds no gate, verdict or hypothesis.** Analysis state: tag pre-analysis-v2.3 (commit 73a9017). A check of `EXPLORATORY_wrong_calls.md`. Script: `scripts/exploratory/wrong_calls_coverage.py`.

# Wrong calls vs coverage: a check of the wrong-call analysis

## 1. How the reference verdicts are built, and what they share with the scored calls

- **Reference** for a decision (pair x suite) under protocol P = the study's four-class verdict (S3) of the **A/A arm** P_AA2 (D_AA2 or R_AA2): both models of the pair, all 10 trials of the A/A arm, stress conditions, CI gate (95%) for harmful/beneficial, neutral if the 90% interval lies inside +/-0.05, otherwise inconclusive (task-level bootstrap, B = 10,000, seed 1234). Read from `analysis_out_v3/addendum/s3_classes.csv`; recomputed here for a check (matches: D: reference recomputed = saved S3 class 30/30; R: reference recomputed = saved S3 class 30/30). Decisions whose reference is inconclusive are left out of every rate.
- **Scored calls** come from the **main arm** P (trials 0-9: Phase 1 trials 0-2 + Phase 2 trials 3-9 on the laptop).
- **What the A/A arm shares with the main arm:** the same models, the same 100 tasks per suite and the same prompts (run seed 1234), and the same temperatures. Only the trial seeds differ (main 1234-1243, A/A 5678-5687). **Trial 0 is greedy (temperature 0) in both arms**, and greedy decoding does not depend on the trial seed, so trial 0 of the A/A arm repeats trial 0 of the main arm. Record by record (stress conditions, both models of every pair, score equal in the two arms):

| Protocol | Trial | Records compared | Same score in main and A/A arm |
|---|---|---|---|
| D | greedy (trial 0) | 9600 | 9600 (100.0%) |
| D | sampled (trials 1-9) | 86400 | 77391 (89.6%) |
| R | greedy (trial 0) | 9600 | 9600 (100.0%) |
| R | sampled (trials 1-9) | 86400 | 78679 (91.1%) |

- **So the overlap is:** every scored call that includes trial 0 (the 1-trial call for trial 0, the 3-trial group 0-2, the 5-trial group 0-4, and every 10-trial call) shares that trial's outputs with the reference; the sampled trials are different draws. The task sample and the prompts are shared by everything, so task-sampling error is common to the scored calls and the reference: the reference measures agreement with another run on the same tasks, not with the models' quality on new tasks.

- **Sensitivity (reference without the shared greedy trial):** the reference recomputed from A/A trials 1-9 only changes the reference class of D 0 of 30; R 1 of 30 decisions. Wrong calls against it (all 30 decisions):

| Protocol | Version | Reference decisions | Calls | Wrong | Wrong share of calls | Same, with the 10-trial reference |
|---|---|---|---|---|---|---|
| D | 1 trial, forced | 18 | 180 | 33 | 18.3% | 18.3% (33 of 180) |
| D | 3 trials, inconclusive allowed | 18 | 54 | 3 | 5.6% | 5.6% (3 of 54) |
| D | 10 trials, forced | 18 | 18 | 2 | 11.1% | 11.1% (2 of 18) |
| D | 10 trials, inconclusive allowed | 18 | 18 | 0 | 0.0% | 0.0% (0 of 18) |
| R | 1 trial, forced | 16 | 160 | 33 | 20.6% | 19.3% (29 of 150) |
| R | 3 trials, inconclusive allowed | 16 | 48 | 3 | 6.2% | 6.7% (3 of 45) |
| R | 10 trials, forced | 16 | 16 | 2 | 12.5% | 13.3% (2 of 15) |
| R | 10 trials, inconclusive allowed | 16 | 16 | 1 | 6.2% | 6.7% (1 of 15) |

## 2. Wrong calls by trials per call, forced vs inconclusive allowed

Calls per decision: 10 (1 trial: each trial alone), 3 (3 trials: groups 0-2, 3-5, 6-8), 2 (5 trials: 0-4, 5-9), 1 (10 trials). *Forced* = point gate +/-0.05 on the pooled trials. *Inconclusive allowed* = the S3 four-class rule on the pooled trials (task bootstrap, B = 10,000, seed 1234). Coverage = definite calls / calls. Wrong = a definite call that differs from the reference; serious = harmful vs beneficial. Brackets: 95% percentile interval from a bootstrap over upgrade pairs (whole pairs resampled with all their suites and calls, B = 10,000, seed 1234). Check: the 10-trial inconclusive-allowed call reproduces the saved S3 class of the main run in D 30/30; R 30/30 decisions.

### D, all 30 decisions

| Version | Reference decisions | Calls | Definite calls | Coverage | Wrong | Wrong / all calls | Wrong / definite calls | Serious |
|---|---|---|---|---|---|---|---|---|
| 1 trial, forced | 18 | 180 | 180 | 100.0% [100.0, 100.0] | 33 | **18.3%** [7.9, 32.5] | 18.3% [7.9, 32.5] | 4 |
| 1 trial, inconclusive allowed | 18 | 180 | 130 | 72.2% [56.7, 86.7] | 7 | **3.9%** [0.7, 9.3] | 5.4% [0.9, 15.6] | 2 |
| 3 trials, forced | 18 | 54 | 54 | 100.0% [100.0, 100.0] | 8 | **14.8%** [3.5, 29.6] | 14.8% [3.5, 29.6] | 1 |
| 3 trials, inconclusive allowed | 18 | 54 | 47 | 87.0% [77.1, 95.2] | 3 | **5.6%** [0.0, 13.3] | 6.4% [0.0, 16.2] | 1 |
| 5 trials, forced | 18 | 36 | 36 | 100.0% [100.0, 100.0] | 5 | **13.9%** [0.0, 31.2] | 13.9% [0.0, 31.2] | 0 |
| 5 trials, inconclusive allowed | 18 | 36 | 33 | 91.7% [81.8, 100.0] | 2 | **5.6%** [0.0, 14.3] | 6.1% [0.0, 16.7] | 0 |
| 10 trials, forced | 18 | 18 | 18 | 100.0% [100.0, 100.0] | 2 | **11.1%** [0.0, 28.6] | 11.1% [0.0, 28.6] | 0 |
| 10 trials, inconclusive allowed | 18 | 18 | 16 | 88.9% [71.4, 100.0] | 0 | **0.0%** [0.0, 0.0] | 0.0% [0.0, 0.0] | 0 |

### D, without qwen25->qwen3

| Version | Reference decisions | Calls | Definite calls | Coverage | Wrong | Wrong / all calls | Wrong / definite calls | Serious |
|---|---|---|---|---|---|---|---|---|
| 1 trial, forced | 15 | 150 | 150 | 100.0% [100.0, 100.0] | 32 | **21.3%** [9.0, 37.5] | 21.3% [9.0, 37.5] | 4 |
| 1 trial, inconclusive allowed | 15 | 150 | 101 | 67.3% [53.3, 83.1] | 7 | **4.7%** [1.0, 11.7] | 6.9% [1.2, 20.8] | 2 |
| 3 trials, forced | 15 | 45 | 45 | 100.0% [100.0, 100.0] | 8 | **17.8%** [4.8, 33.3] | 17.8% [4.8, 33.3] | 1 |
| 3 trials, inconclusive allowed | 15 | 45 | 38 | 84.4% [74.4, 93.8] | 3 | **6.7%** [0.0, 15.4] | 7.9% [0.0, 20.0] | 1 |
| 5 trials, forced | 15 | 30 | 30 | 100.0% [100.0, 100.0] | 5 | **16.7%** [0.0, 36.4] | 16.7% [0.0, 36.4] | 0 |
| 5 trials, inconclusive allowed | 15 | 30 | 27 | 90.0% [79.2, 100.0] | 2 | **6.7%** [0.0, 16.7] | 7.4% [0.0, 20.8] | 0 |
| 10 trials, forced | 15 | 15 | 15 | 100.0% [100.0, 100.0] | 2 | **13.3%** [0.0, 33.3] | 13.3% [0.0, 33.3] | 0 |
| 10 trials, inconclusive allowed | 15 | 15 | 13 | 86.7% [66.7, 100.0] | 0 | **0.0%** [0.0, 0.0] | 0.0% [0.0, 0.0] | 0 |

### R, all 30 decisions

| Version | Reference decisions | Calls | Definite calls | Coverage | Wrong | Wrong / all calls | Wrong / definite calls | Serious |
|---|---|---|---|---|---|---|---|---|
| 1 trial, forced | 15 | 150 | 150 | 100.0% [100.0, 100.0] | 29 | **19.3%** [7.4, 35.3] | 19.3% [7.4, 35.3] | 0 |
| 1 trial, inconclusive allowed | 15 | 150 | 103 | 68.7% [51.4, 87.3] | 9 | **6.0%** [0.0, 14.3] | 8.7% [0.0, 25.8] | 0 |
| 3 trials, forced | 15 | 45 | 45 | 100.0% [100.0, 100.0] | 7 | **15.6%** [0.0, 37.5] | 15.6% [0.0, 37.5] | 0 |
| 3 trials, inconclusive allowed | 15 | 45 | 39 | 86.7% [68.4, 100.0] | 3 | **6.7%** [0.0, 21.4] | 7.7% [0.0, 25.5] | 0 |
| 5 trials, forced | 15 | 30 | 30 | 100.0% [100.0, 100.0] | 4 | **13.3%** [0.0, 31.2] | 13.3% [0.0, 31.2] | 0 |
| 5 trials, inconclusive allowed | 15 | 30 | 26 | 86.7% [73.1, 100.0] | 2 | **6.7%** [0.0, 21.4] | 7.7% [0.0, 26.1] | 0 |
| 10 trials, forced | 15 | 15 | 15 | 100.0% [100.0, 100.0] | 2 | **13.3%** [0.0, 31.2] | 13.3% [0.0, 31.2] | 0 |
| 10 trials, inconclusive allowed | 15 | 15 | 14 | 93.3% [78.6, 100.0] | 1 | **6.7%** [0.0, 21.4] | 7.1% [0.0, 22.2] | 0 |

### R, without qwen25->qwen3

| Version | Reference decisions | Calls | Definite calls | Coverage | Wrong | Wrong / all calls | Wrong / definite calls | Serious |
|---|---|---|---|---|---|---|---|---|
| 1 trial, forced | 13 | 130 | 130 | 100.0% [100.0, 100.0] | 18 | **13.8%** [5.0, 26.9] | 13.8% [5.0, 26.9] | 0 |
| 1 trial, inconclusive allowed | 13 | 130 | 94 | 72.3% [53.0, 91.7] | 9 | **6.9%** [0.0, 16.7] | 9.6% [0.0, 30.6] | 0 |
| 3 trials, forced | 13 | 39 | 39 | 100.0% [100.0, 100.0] | 3 | **7.7%** [0.0, 25.0] | 7.7% [0.0, 25.0] | 0 |
| 3 trials, inconclusive allowed | 13 | 39 | 37 | 94.9% [88.9, 100.0] | 3 | **7.7%** [0.0, 25.0] | 8.1% [0.0, 27.9] | 0 |
| 5 trials, forced | 13 | 26 | 26 | 100.0% [100.0, 100.0] | 2 | **7.7%** [0.0, 25.0] | 7.7% [0.0, 25.0] | 0 |
| 5 trials, inconclusive allowed | 13 | 26 | 24 | 92.3% [83.3, 100.0] | 2 | **7.7%** [0.0, 25.0] | 8.3% [0.0, 29.6] | 0 |
| 10 trials, forced | 13 | 13 | 13 | 100.0% [100.0, 100.0] | 1 | **7.7%** [0.0, 25.0] | 7.7% [0.0, 25.0] | 0 |
| 10 trials, inconclusive allowed | 13 | 13 | 13 | 100.0% [100.0, 100.0] | 1 | **7.7%** [0.0, 25.0] | 7.7% [0.0, 25.0] | 0 |

## 3. Paired difference: 3 trials + inconclusive minus 10 trials forced

Same bootstrap replicates (pairs resampled once, both methods scored on the same resample). Negative = 3 trials + inconclusive makes fewer wrong calls. P(diff >= 0) = share of replicates in which the 3-trial method is not better.

| Protocol | Decisions | Rate | Difference (pts) | 95% CI (pts) | P(diff >= 0) |
|---|---|---|---|---|---|
| D | all 30 decisions | wrong over all calls | -5.6 | -17.6 to +4.2 | 0.196 |
| D | all 30 decisions | wrong over definite calls | -4.7 | -15.3 to +5.3 | 0.206 |
| D | without qwen25->qwen3 | wrong over all calls | -6.7 | -20.5 to +5.1 | 0.186 |
| D | without qwen25->qwen3 | wrong over definite calls | -5.4 | -17.8 to +6.7 | 0.200 |
| R | all 30 decisions | wrong over all calls | -6.7 | -21.4 to +0.0 | 0.348 |
| R | all 30 decisions | wrong over definite calls | -5.6 | -20.0 to +1.5 | 0.349 |
| R | without qwen25->qwen3 | wrong over all calls | +0.0 | +0.0 to +0.0 | 1.000 |
| R | without qwen25->qwen3 | wrong over definite calls | +0.4 | +0.0 to +2.7 | 1.000 |

## 4. Matched-coverage baseline

The 10-trial forced verdict is made to abstain on the same share of decisions as the method it is compared with, choosing the decisions whose 10-trial stress diff lies closest to the +/-0.05 gate (smallest ||diff| - 0.05|). Then its wrong rate among the calls it still makes is compared with the method's wrong rate among its definite calls.

| Protocol | Decisions | Matched to | Abstains on | 10-trial forced, matched: wrong / definite | Method: wrong / definite |
|---|---|---|---|---|---|
| D | all 30 decisions | 3 trials, inconclusive allowed (13.0% inconclusive) | 2 of 18 | 2 / 16 = **12.5%** [0.0, 33.3] | **6.4%** |
| D | all 30 decisions | 10 trials, inconclusive allowed (11.1% inconclusive) | 2 of 18 | 2 / 16 = **12.5%** [0.0, 33.3] | **0.0%** |
| D | without qwen25->qwen3 | 3 trials, inconclusive allowed (15.6% inconclusive) | 2 of 15 | 2 / 13 = **15.4%** [0.0, 40.0] | **7.9%** |
| D | without qwen25->qwen3 | 10 trials, inconclusive allowed (13.3% inconclusive) | 2 of 15 | 2 / 13 = **15.4%** [0.0, 40.0] | **0.0%** |
| R | all 30 decisions | 3 trials, inconclusive allowed (13.3% inconclusive) | 2 of 15 | 1 / 13 = **7.7%** [0.0, 25.0] | **7.7%** |
| R | all 30 decisions | 10 trials, inconclusive allowed (6.7% inconclusive) | 1 of 15 | 2 / 14 = **14.3%** [0.0, 38.5] | **7.1%** |
| R | without qwen25->qwen3 | 3 trials, inconclusive allowed (5.1% inconclusive) | 1 of 13 | 0 / 12 = **0.0%** [0.0, 0.0] | **8.1%** |
| R | without qwen25->qwen3 | 10 trials, inconclusive allowed (0.0% inconclusive) | 0 of 13 | 1 / 13 = **7.7%** [0.0, 25.0] | **7.7%** |

## Plain-language summary

- **The earlier numbers are reproduced.** Forced calls are wrong 18.3% (1 trial), 14.8% (3), 13.9% (5) and 11.1% (10) of the time under D; 3 trials with "inconclusive" allowed are wrong 5.6% of the time, and 10 trials with "inconclusive" allowed 0.0%. Under R the same figures are 19.3%, 15.6%, 13.3%, 13.3%, 6.7% and 6.7%.
- **The intervals are wide.** The estimates rest on 18 (D) and 15 (R) scored decisions, about 9 pairs. Over upgrade pairs the 95% intervals run, for example:

  | Method (D) | Wrong share | 95% interval |
  |---|---|---|
  | 10 trials, forced | 11.1% | 0 to 28.6% |
  | 3 trials + inconclusive | 5.6% | 0 to 13.3% |
  | 1 trial, forced | 18.3% | 7.9 to 32.5% |

  Most rates differ by a few calls.
- **"3 trials + inconclusive beats 10 trials forced" is not established.**
  - The paired difference (3 trials + inconclusive minus 10 trials forced, wrong share over all calls) is -5.6 points under D (95% CI -17.6 to +4.2) and -6.7 points under R (-21.4 to 0.0). In 20% (D) and 35% (R) of the resamples the 3-trial method is not better.
  - Without qwen25->qwen3, under R the two methods make exactly the same share of wrong calls (7.7%).
  - The direction is consistent, but the data do not exclude no difference.
- **Most of the gain comes from allowing "inconclusive", not from more trials, and it already appears at 1 trial.** One trial with "inconclusive" allowed is wrong on 3.9% of calls (D) and 6.0% (R), no worse than 3 trials (5.6%, 6.7%). The cost is lower coverage: it abstains on 28% (D) and 31% (R) of calls, against 13% at 3 trials. So the earlier statement that "3 trials with the CI gate and inconclusive is the cheapest version that keeps wrong calls low" holds only if a lower coverage is not acceptable. The real trade-off is coverage, not wrong calls.
- **The matched-coverage baseline gives a mixed result.**
  - Under D: a 10-trial forced verdict that abstains on the 2 decisions closest to the gate is still wrong on 2 of 16 (12.5%), against 6.4% (3 trials + inconclusive) and 0% (10 trials + inconclusive). So under D the four-class rule removes errors that "skip the closest calls" does not.
  - Under R the matched baseline does as well or better: 7.7% vs 7.7% (all decisions) and 0% vs 8.1% (without qwen25->qwen3, 3-trial match).
  - So under R the advantage of "inconclusive" over simply abstaining near the gate is not shown.
- **The reference is not independent of the scored calls.** This is the most important caveat and it weakens all the error rates, making them optimistic.
  - The reference arm uses the same models, tasks and prompts.
  - Its greedy trial is identical to the main arm's (9,600 of 9,600 stress records).
  - Its sampled trials match the main arm's score on 89.6% (D) and 91.1% (R) of records.
- **What the shared greedy trial does and does not change.**
  - Dropping that trial from the reference changes 0 (D) and 1 (R) reference classes. The wrong shares barely move: R 1 trial forced 20.6% vs 19.3%; 10 trials + inconclusive 6.2% vs 6.7%. So the shared greedy trial is not what drives the low error rates.
  - The shared **tasks** cannot be removed with existing data. The rates measure agreement with another run on the same 100 tasks per suite, not correctness on new tasks.
- **The excluded decisions are the hard ones.**
  - Decisions with an inconclusive reference are left out: 12 of 30 (D) and 15 of 30 (R).
  - These are the decisions closest to the gate, where any method errs most often.
  - So all wrong-call rates describe the easier half to two thirds of the decisions, and they understate the error a user would meet on a random decision.
- **Serious errors** (harmful called beneficial or the reverse) appear only under D: 4 with 1 trial forced, 2 with 1 trial + inconclusive, 1 at 3 trials (forced or inconclusive allowed), and none from 5 trials on. R has none at any trial count.
