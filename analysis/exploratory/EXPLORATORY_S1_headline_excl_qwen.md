# EXPLORATORY: S1 headline excluding the qwen25->qwen3 pair

**Exploratory. Not pre-registered. Descriptive only; it feeds no gate, verdict or hypothesis.**
Asked for 2026-11-14, after the first Phase 2 analysis (tag pre-analysis-v2.1, commit 9654dbd) had been seen.

## What was computed

For each decision (pair x suite) that has a rerun arm: the observed flag "flips under at least one generation factor"
(F1, F2, F3, F4, F5, F6, F11, main variants, as in S1) and the expected probability of at least one noise flip
(`p_at_least_one_noise_flip` from `analysis_out_v3/addendum/s1_per_decision.csv`). The headline is the observed share
minus the mean expected share. The 95% interval is a percentile bootstrap over decisions: resample the decisions with
replacement, B = 10,000, seed 1234.

## Result

| | Decisions | Observed share with >=1 generation flip | Expected noise share | Difference | 95% CI | P(diff <= 0) |
|---|---|---|---|---|---|---|
| All decisions | 30 | 50.0% (15/30) | 32.2% | +17.9 pts | +2.0 to +34.4 | 0.013 |
| Excluding qwen25->qwen3 | 27 | 44.4% (12/27) | 35.5% | +8.9 pts | -5.1 to +24.2 | 0.11 |

The "All decisions" row reproduces the saved S1 headline (observed 0.5, expected 0.3215).

## Caveat

The interval resamples decisions only. It ignores the task-level sampling uncertainty in each decision's noise
probability (which the S1 hierarchical bootstrap includes), and it treats decisions as independent although several
share models. It is therefore narrower than a full hierarchical interval would be. Read it as a rough guide.

With the three qwen25->qwen3 decisions dropped, the gap above noise is smaller and its interval includes zero. This is
in line with the factor-level S1 result, where only F2 (qwen3 thinking off, which exists only for that pair) stood out
after Holm adjustment.
