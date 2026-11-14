**EXPLORATORY, post hoc. Not pre-registered. Existing data only (analysis at tag pre-analysis-v2.2, commit 8e68388); descriptive; feeds no gate, verdict or hypothesis.**

# Headline excess with a bootstrap over upgrade PAIRS

Headline = share of decisions with >= 1 generation-factor flip (F1-F6, F11, main variants) minus the mean expected share with >= 1 noise flip (`s1_per_decision.csv`). The earlier exploratory note resampled decisions; here whole pairs (all of a pair's suites) are resampled with replacement, B = 10,000, seed 1234, so the 3 suites of a pair stay together.

| | Pairs | Decisions | Observed share | Expected noise share | Difference (pts) | 95% CI (pts) | P(diff <= 0) |
|---|---|---|---|---|---|---|---|
| All pairs | 10 | 30 | 50.0% | 32.2% | +17.8 | -1.0 to +41.6 | 0.034 |
| Excluding qwen25->qwen3 | 9 | 27 | 44.4% | 35.5% | +8.9 | -4.1 to +25.3 | 0.116 |

**Caveat:** only 10 pairs (9 after the exclusion) are resampled, so the interval is coarse; the expected noise share per decision is held fixed (task-level uncertainty in it is ignored), and pairs sharing a model are treated as independent.
