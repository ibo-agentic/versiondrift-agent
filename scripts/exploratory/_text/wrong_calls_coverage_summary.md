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
