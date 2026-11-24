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
