**EXPLORATORY, post hoc. Not pre-registered. Existing data only (analysis at tag pre-analysis-v2.3, commit 73a9017); descriptive; feeds no gate, verdict or hypothesis.**

# Pseudo A/A: a pooled noise floor for the rerun flip rate

**Method.** For each model and suite, the 20 trials of the main arm (10) and the A/A arm (10, same prompts) are pooled. Each of B = 2,000 random splits puts 10 trials in each of two arms; each arm keeps exactly one greedy trial (the two greedy trials are assigned to the arms at random) and gets 9 of the 18 sampled trials. Splits are independent for every model and suite and shared by the pairs that use the model. In each arm the stress diff (new minus old, equal weight over the two stress conditions, all tasks) gets the point-gate label (+/-0.05); the per-decision rerun flip probability is the share of splits whose two arms differ. Seed 1234.

**Assumptions.** Trial 0 of every arm is the greedy trial (checked from the stored temperatures: exactly one greedy trial in each arm for all 96 model-suite runs); splitting treats the 20 trials as exchangeable apart from the greedy rule, i.e. it assumes the main and the A/A arm have the same sampling process (true by design: same run seed, same temperatures, other trial seeds). Tasks are not resampled here, so this noise is trial noise only, not task-sampling noise.

## Rerun flip rate

| Protocol | Observed rerun flips (main vs A/A arm) | Pseudo A/A mean flip rate | 95% CI over pairs | S1.4 expected share (task bootstrap) |
|---|---|---|---|---|
| D | 2/30 (6.7%) | 11.1% | 4.0% to 18.4% | 15.1% |
| R | 5/30 (16.7%) | 14.0% | 3.9% to 25.4% | n/a here |

(The S1.4 expected share for R, 11.8%, is in EXPLORATORY_r_vs_d_noise.md.) CI = bootstrap over the 10 upgrade pairs (whole pairs resampled, 10,000 replicates, seed 1234).

## Excess over the pseudo A/A noise floor: All pairs

| Factor | Decisions | Factor flips | Pseudo-A/A noise (expected flips per decision) | Excess (pts) | 95% CI (pts) | 95% upper bound (pts) | P(excess <= 0) |
|---|---|---|---|---|---|---|---|
| F1 | 30 | 3 | 11.1% | -1.1 | -17.8 to +24.2 | +20.2 | 0.588 |
| F2 | 3 | 3 | 0.0% | +100.0 | +100.0 to +100.0 | +100.0 | 0.000 |
| F3 | 9 | 3 | 4.3% | +29.1 | +0.0 to +87.2 | +87.2 | 0.328 |
| F4 | 27 | 3 | 12.3% | -1.2 | -12.7 to +11.3 | +9.1 | 0.598 |
| F5 | 30 | 5 | 11.1% | +5.6 | -5.4 to +17.3 | +15.4 | 0.173 |
| F6 | 12 | 0 | 11.2% | -11.2 | -22.9 to +0.0 | +0.0 | 1.000 |
| F11 | 12 | 3 | 13.4% | +11.6 | -26.8 to +58.3 | +50.0 | 0.295 |

## Excess over the pseudo A/A noise floor: Excluding qwen25->qwen3

| Factor | Decisions | Factor flips | Pseudo-A/A noise (expected flips per decision) | Excess (pts) | 95% CI (pts) | 95% upper bound (pts) | P(excess <= 0) |
|---|---|---|---|---|---|---|---|
| F1 | 27 | 0 | 12.3% | -12.3 | -19.8 to -5.0 | -5.8 | 1.000 |
| F2 | 0 | | | n/a | n/a | n/a | n/a |
| F3 | 6 | 3 | 6.4% | +43.6 | +0.0 to +87.2 | +87.2 | 0.272 |
| F4 | 27 | 3 | 12.3% | -1.2 | -12.4 to +11.1 | +8.9 | 0.588 |
| F5 | 27 | 5 | 12.3% | +6.2 | -5.8 to +19.0 | +16.9 | 0.170 |
| F6 | 9 | 0 | 14.9% | -14.9 | -23.5 to +0.0 | +0.0 | 1.000 |
| F11 | 9 | 2 | 17.8% | +4.4 | -26.8 to +66.7 | +66.7 | 0.463 |

The factor flip rate f_F is the observed share of decisions where the factor changes the point-gate label (same cells as S1); the noise column is the mean pseudo-A/A flip probability (D protocol) over the same decisions, so excess = f_F minus that. The interval resamples pairs and holds each decision's noise probability fixed.

**Caveat:** pseudo A/A uses all 20 trials, so each arm's decision is made from the same trial pool and the two arms are not independent draws; it is a lower-variance estimate of the noise than one real rerun, but it also ignores task-sampling noise and is based on 30 decisions per protocol.
