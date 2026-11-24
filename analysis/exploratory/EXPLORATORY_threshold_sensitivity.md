**EXPLORATORY, post hoc. Not pre-registered. Existing data only (analysis at tag pre-analysis-v2.3, commit 73a9017); descriptive; feeds no gate, verdict or hypothesis.**

# Threshold sensitivity: gate at +/-0.03, +/-0.05, +/-0.07

The point gate's threshold is changed everywhere (labels recomputed from the stored stress diffs; the CI gate and the 4-class verdict use the same threshold, with the stored 95% intervals and a 90% task bootstrap, B = 10,000, seed 1234). No data are rerun. (a) uses the P1 definition: 30 decisions, flips under at least one of F1-F10 (main variants; F9 = CI gate). (b) point-gate label changes between the main arm and its A/A arm, over 30 decisions. (c) sign reversal = a label change between harmful and beneficial. (d) 4-class verdict of the main arm.

| Quantity | +/-0.03 | **+/-0.05 (pre-registered)** | +/-0.07 |
|---|---|---|---|
| (a) decisions with >= 1 factor flip (of 30) | 19 (63.3%) | 13 (43.3%) | 9 (30.0%) |
| (a') factor flips in total (decision x factor cells) | 33 | 21 | 13 |
| (b) rerun flips D vs D_AA2 (of 30) | 9 (30.0%) | 2 (6.7%) | 2 (6.7%) |
| (b) rerun flips R vs R_AA2 (of 30) | 9 (30.0%) | 5 (16.7%) | 0 (0.0%) |
| (c) sign reversals among factor flips | 4 | 3 | 2 |
| (c) sign reversals in reruns (D / R) | 0 / 0 | 0 / 0 | 0 / 0 |
| (d) inconclusive share, D (of 30) | 17 (56.7%) | 10 (33.3%) | 5 (16.7%) |
| (d) inconclusive share, R (of 30) | 15 (50.0%) | 10 (33.3%) | 8 (26.7%) |

Check: at +/-0.05 the recomputed values reproduce the saved ones (factor flips match; D inconclusive 10 of 30, R 10 of 30 as in S3; rerun flips 2 and 5).

**Correction (2026-11-24):** the +/-0.03 column of rows (a) and (a') was first computed with plain floating-point comparisons and counted two factor flips that are not real: F4 for granite31 -> granite32 and F5 for granite30 -> granite31, both on bfcl_multiple, where the factor's stress diff is exactly 0.03 in exact arithmetic but 0.030000000000000002 as a float. With a round-safe comparison (diffs rounded to 9 decimals; an exact +/-delta is neutral) (a) is 19, not 20, and (a') is 33, not 35. No other cell in this table changes, and the pre-registered +/-0.05 verdicts are unaffected (checked against exact fractions for all 4,450 pipeline comparisons).

**Caveat:** only the threshold changes; the per-decision noise, the task set and the factor definitions do not, and decisions near a boundary move between classes as the boundary moves, so (a), (b) and (d) are expected to fall as the threshold widens. 30 decisions, not independent.
