# NOTE: floating-point boundary check of the gate comparisons

**Post hoc check, existing data only, no reruns. Written 2026-11-24 for the exploratory material; it changes no pre-registered result.**

## Why

A gate says "harmful if the stress diff is below -0.05, beneficial if above +0.05, else neutral". A diff is computed as an average of
divisions, so a value that is exactly 0.05 in exact arithmetic can come out as 0.05000000000000001 as a float and be called
beneficial. Exploratory trial-level calculations hit this at three decisions (the "wrong_calls" analysis), so the main pipeline was
checked for the same problem.

## What was checked

- **4,450 distinct comparisons** (Phase 1: 1,770; Phase 2: 2,680), each recomputed with exact fractions: every decision row, all
  protocols (D, R, F1-F11, A/A and positive controls, rescored F7/F8/F10, Kaggle baselines), the descriptive controls, the greedy
  and sampled views, and the Phase 1 studies tables. All of them go through `vdanalysis.stats.compare()`, which was wrapped to record
  its inputs.
- The float label (`point_gate`, `ci_gate`) was compared with the label from the exact diff at the pre-registered gate **+/-0.05** and
  at the sensitivity values **+/-0.03** and **+/-0.07**. Comparisons within 1e-6 of a boundary were re-run with the CI gate.
- The addendum computes diffs differently (`TaskArrays`, matrix sums), so its **703 array-based diffs** were checked the same way.

## Result

| Gate | Comparisons exactly on the boundary | Float label differs from exact label |
|---|---|---|
| +/-0.05 (pre-registered) | 58 | **0** |
| +/-0.07 | 52 | **0** |
| +/-0.03 | 76 | **5** |

- **Pre-registered verdicts unchanged.** At +/-0.05 every one of the 58 boundary cases is correctly neutral: the float value happens to be the
  same double as 0.05. No point-gate or CI-gate label (D, R, any other protocol; Phase 1 or Phase 2) differs, and no S1-S9 verdict at 0.05 is affected.
- **No change at +/-0.07.**
- **Five float artifacts at +/-0.03** (diff 0.030000000000000002 or -0.030000000000000002, exactly 3/100 in exact arithmetic):
  Phase 1 F5 (phi3_mini -> phi35_mini, bfcl_simple), Phase 1 R_F5 (llama3 -> llama31, synthetic), Phase 2 F4_json (granite31 -> granite32,
  bfcl_multiple; the CI-gate label too), Phase 2 F5 (granite30 -> granite31, bfcl_multiple) and Phase 2 R_F5 (llama3 -> llama31, synthetic).
  The addendum's array-based diffs show the same three Phase 2 cases and no others.
- **Corrected:** two of these (the F4 and F5 cells) entered the exploratory threshold-sensitivity table at +/-0.03, which counted two factor flips
  that are not real. With the rounding-safe comparison the +/-0.03 column reads **19** decisions with a factor flip (was 20) and **33** factor flips in
  total (was 35); nothing else in that table changes. The other three artifacts are in comparisons that no table uses at +/-0.03.

## What the exploratory scripts do now

`scripts/exploratory/_common.py` rounds every diff to 9 decimals before comparing it with a gate (`rd`, `point_label`, `point_code`, `ci_gate`,
`classify`), so an exact +/-delta counts as neutral (strict inequality) and float noise cannot decide a label. All analyses in `scripts/exploratory/`
use it; `run_all.py` regenerates every exploratory table into a temp folder and compares it with the files here.

## Not changed

The pre-registered pipeline (`upgradecanary/gates.py`, `vdanalysis/stats.py`, the addendum) is untouched: the check found no case where it
mislabels a decision at +/-0.05. If the gate threshold or the scoring were ever changed to a value where this can happen (as at 0.03), the same
rounding would be needed there.

## Reproduce

    python -m scripts.exploratory.boundary_check --out <scratch folder>      # writes boundary_check.json
    python -m scripts.exploratory.run_all                                      # regenerates and compares all exploratory files
