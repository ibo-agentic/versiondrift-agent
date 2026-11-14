**EXPLORATORY, post hoc. Not pre-registered. Existing data only (analysis at tag pre-analysis-v2.2, commit 8e68388); descriptive; feeds no gate, verdict or hypothesis.**

# Why R reruns flip more than D reruns (5/30 vs 2/30)

Per decision (30 decisions, the same pairs and suites under both protocols). Distance = ||stress diff| - 0.05|, in points. CI width = the 95% task-bootstrap interval of the stress diff from the pipeline's own gate rows. Expected rerun flip probability = per-decision share of task resamples in which the main arm and its rerun arm get different point labels (S1.4 method, B = 10,000, seed 1234), averaged over the decisions.

| Quantity | D | R |
|---|---|---|
| Observed rerun flips | 2/30 | 5/30 |
| Expected rerun flip share (mean of per-decision probabilities) | 15.1% | 11.8% |
| Distance to boundary, median / IQR (pts) | 3.53 / 2.31-4.75 | 2.35 / 1.41-3.38 |
| Decisions within 1 pt(s) of a boundary | 2 | 5 |
| Decisions within 2 pt(s) of a boundary | 6 | 13 |
| Decisions within 3 pt(s) of a boundary | 13 | 18 |
| 95% CI width of the stress diff, median / IQR (pts) | 8.68 / 8.00-9.72 | 8.38 / 7.21-9.40 |

Paired Wilcoxon on the distances, D vs R: p = 0.012.

**Caveat:** 2 vs 5 flips out of 30 is a small difference (the intervals overlap widely), and the comparison explains the gap only descriptively: R decisions lying closer to a boundary or having wider intervals would raise R's rerun flip chance. In this table R decisions lie closer to a boundary (median 2.35 vs 3.53 points; paired Wilcoxon p = 0.012) while the CI widths are about the same (8.4 vs 8.7 points), so closeness to the boundary, not wider intervals, is what differs. D's observed rerun flips (2) are below its expected share (15.1%, about 4.5 flips) and R's (5) are above its expected share (11.8%, about 3.5 flips), so part of the 2 vs 5 gap is chance; the expected shares themselves differ by only 3 points.
