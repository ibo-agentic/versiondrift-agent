# EXPLORATORY: S3 four-class verdict on the original 100 tasks vs the full W3 task set

**Exploratory. Not pre-registered. Descriptive only; it feeds no gate, verdict or hypothesis.**
Made 2026-11-14 from existing data only (no new runs), after the Phase 2 analysis had been seen.
Code state: tag pre-analysis-v2.2, commit 8e68388. Script: not committed (run from the scratchpad).

## What was computed

For bfcl_simple and bfcl_multiple (synthetic is not extended in W3), protocols D and R, all 10 adjacent pairs
(20 decisions per protocol, 40 in total), the S3 class under two task sets:

- (a) the original 100 tasks (the W3 records restricted to the original task ids);
- (b) the full W3 task set: 191 tasks for bfcl_simple, 109 tasks for bfcl_multiple.

Classes are the S3 rules (delta = 0.05): harmful / beneficial = the pre-registered CI-gate label (`label_ci`);
neutral = the 90% interval entirely inside [-0.05, +0.05]; inconclusive = everything else. Intervals come from the
task-level bootstrap (B = 10,000, seed 1234). Both protocols use the CI-based classes, as in S3. As a check, the
(a) classes reproduce the saved S3 classes of the main analysis for all 40 decisions (0 mismatches).

## Class shares, side by side (counts of decisions)

| Protocol | Suite | Task set | Harmful | Neutral | Beneficial | Inconclusive |
|---|---|---|---|---|---|---|
| D | bfcl_simple | original (100) | 1 | 3 | 2 | 4 |
| D | bfcl_simple | full (191) | 1 | 4 | 2 | 3 |
| D | bfcl_multiple | original (100) | 1 | 2 | 4 | 3 |
| D | bfcl_multiple | full (109) | 1 | 3 | 4 | 2 |
| D | both suites (20) | original | 2 (10%) | 5 (25%) | 6 (30%) | 7 (35%) |
| D | both suites (20) | full | 2 (10%) | 7 (35%) | 6 (30%) | 5 (25%) |
| R | bfcl_simple | original (100) | 1 | 2 | 3 | 4 |
| R | bfcl_simple | full (191) | 1 | 3 | 4 | 2 |
| R | bfcl_multiple | original (100) | 0 | 2 | 5 | 3 |
| R | bfcl_multiple | full (109) | 0 | 2 | 5 | 3 |
| R | both suites (20) | original | 1 (5%) | 4 (20%) | 8 (40%) | 7 (35%) |
| R | both suites (20) | full | 1 (5%) | 5 (25%) | 9 (45%) | 5 (25%) |
| D and R | both suites (40) | original | 3 (7.5%) | 9 (22.5%) | 14 (35%) | 14 (35%) |
| D and R | both suites (40) | full | 3 (7.5%) | 12 (30%) | 15 (37.5%) | 10 (25%) |

## Decisions that move out of "inconclusive"

4 of the 14 inconclusive decisions (29%) get a definite class on the full task set: D 2 of 7, R 2 of 7. No decision moves
into "inconclusive", and no harmful, neutral or beneficial decision changes class.

| Protocol | Suite | Pair | Original -> full | Stress diff, original -> full |
|---|---|---|---|---|
| D | bfcl_simple | phi3_mini -> phi35_mini | inconclusive -> neutral | +0.015 -> -0.011 |
| D | bfcl_multiple | llama3 -> llama31 | inconclusive -> neutral | -0.018 -> -0.014 |
| R | bfcl_simple | phi3_mini -> phi35_mini | inconclusive -> neutral | +0.016 -> -0.012 |
| R | bfcl_simple | phi35_mini -> phi4_mini | inconclusive -> beneficial | +0.032 -> +0.054 |

The three "neutral" moves are decisions whose point estimate stays within +/-0.02 and whose 90% interval narrows
inside +/-0.05 with more tasks. The one "beneficial" move is a point estimate that grows from +0.032 to +0.054 and
crosses the CI gate. It is the same decision that P7 flags for R on bfcl_simple.

## Caveats

- 40 decisions, and decisions are not independent (pairs share models, and D and R use the same tasks). The shares
  carry no confidence interval and should not be read as precise rates.
- The full-set classes describe these particular W3 tasks, not tasks in general.
- bfcl_multiple adds only 9 tasks (100 -> 109), so almost nothing changes there; the gain comes from bfcl_simple
  (100 -> 191).
- The class rules (delta, 90% TOST, the CI gate) are unchanged; nothing here alters any pre-registered result.
