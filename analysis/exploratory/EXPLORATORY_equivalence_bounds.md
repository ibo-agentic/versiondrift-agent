**EXPLORATORY, post hoc. Not pre-registered. Existing data only (analysis at tag pre-analysis-v2.2, commit 8e68388); descriptive; feeds no gate, verdict or hypothesis.**

# Equivalence bounds: upper bound on the excess flip rate per generation factor

Excess e_F = factor flip rate f_F minus the rerun flip rate (D vs D_AA2) on the same decisions, as in S1. Hierarchical bootstrap (pairs, then tasks within each pair-suite; f_F and the rerun rate recomputed in every replicate), B = 10,000, seed 1234. "Upper bound" = the one-sided 95% bound (95th percentile of the replicates of e_F). Percentage points.

## All pairs

| Factor | Decisions | Factor flips | Rerun flips | Excess (pts) | 95% interval (pts) | **95% upper bound: excess <= (pts)** |
|---|---|---|---|---|---|---|
| F1 | 30 | 3 | 2 | +3.3 | -26.7 to +23.3 | +16.7 |
| F2 | 3 | 3 | 0 | +100.0 | +100.0 to +100.0 | +100.0 |
| F3 | 9 | 3 | 0 | +33.3 | +0.0 to +66.7 | +50.0 |
| F4 | 27 | 3 | 2 | +3.7 | -23.3 to +12.5 | +10.0 |
| F5 | 30 | 5 | 2 | +10.0 | -10.0 to +20.0 | +16.7 |
| F6 | 12 | 0 | 0 | +0.0 | -20.0 to +11.1 | +6.7 |
| F11 | 12 | 3 | 2 | +8.3 | -33.3 to +50.0 | +41.7 |

## Excluding qwen25->qwen3

| Factor | Decisions | Factor flips | Rerun flips | Excess (pts) | 95% interval (pts) | **95% upper bound: excess <= (pts)** |
|---|---|---|---|---|---|---|
| F1 | 27 | 0 | 2 | -7.4 | -33.3 to -3.7 | -3.7 |
| F2 | 0 | 0 | 0 | n/a | n/a | n/a (no decisions) |
| F3 | 6 | 3 | 0 | +50.0 | +0.0 to +66.7 | +66.7 |
| F4 | 27 | 3 | 2 | +3.7 | -22.2 to +11.1 | +11.1 |
| F5 | 27 | 5 | 2 | +11.1 | -11.1 to +18.5 | +18.5 |
| F6 | 9 | 0 | 0 | +0.0 | -33.3 to +13.3 | +11.1 |
| F11 | 9 | 2 | 2 | +0.0 | -44.4 to +55.6 | +44.4 |

**Caveat:** with 3 to 30 decisions per factor the bounds are wide, so no factor gets a tight upper bound (the only bound below zero is F1 once qwen25->qwen3 is excluded: 0 factor flips against 2 rerun flips); F2 exists only for qwen25->qwen3 (n/a after excluding it). The excluded-pair point estimates are recomputed on the remaining pairs (the addendum's own excluding-pair table reports the full-data point estimate next to the reduced-data interval).
