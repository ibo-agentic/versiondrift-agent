# Decisions recomputed with the corrected Qwen3 runs

Every table below is recomputed directly from existing result logs (no new runs), reusing the exact bootstrap/selection/calibration conventions already used throughout this audit. **nothink is the primary corrected Qwen3 config, think_long is secondary, the original run is labeled "pre-fix" throughout.** Mistral decisions are unchanged from `docs/results_summary.md` and are recomputed here only for internal consistency (same 10 final runs as always).


## 1. Upgrade decision table, both suites, all three Qwen variants

| suite | decision | d_baseline | d_drift | d_fault | **d_stress** | label | neg/pos flips | 95% CI |
|---|---|---|---|---|---|---|---|---|
| synthetic | Mistral v0.1->Mistral v0.2 | +0.000 | -0.093 | -0.243 | **-0.168** | harmful | 102/1 | [-0.218, -0.122] |
| synthetic | Mistral v0.2->Mistral v0.3 | -0.030 | +0.033 | +0.213 | **+0.123** | beneficial | 19/93 | [+0.062, +0.180] |
| synthetic | Mistral v0.1->Mistral v0.3 | -0.030 | -0.060 | -0.030 | **-0.045** | neutral | 28/1 | [-0.083, -0.013] |
| synthetic | Qwen2.5->Qwen3 [pre-fix] | -0.003 | -0.030 | -0.053 | **-0.042** | neutral | 44/19 | [-0.078, -0.007] |
| synthetic | Mistral v0.1->Mistral v0.2 | +0.000 | -0.093 | -0.243 | **-0.168** | harmful | 102/1 | [-0.218, -0.122] |
| synthetic | Mistral v0.2->Mistral v0.3 | -0.030 | +0.033 | +0.213 | **+0.123** | beneficial | 19/93 | [+0.062, +0.180] |
| synthetic | Mistral v0.1->Mistral v0.3 | -0.030 | -0.060 | -0.030 | **-0.045** | neutral | 28/1 | [-0.083, -0.013] |
| synthetic | Qwen2.5->Qwen3-nothink [primary (nothink)] | +0.000 | +0.063 | +0.000 | **+0.032** | neutral | 0/19 | [+0.013, +0.053] |
| synthetic | Mistral v0.1->Mistral v0.2 | +0.000 | -0.093 | -0.243 | **-0.168** | harmful | 102/1 | [-0.218, -0.122] |
| synthetic | Mistral v0.2->Mistral v0.3 | -0.030 | +0.033 | +0.213 | **+0.123** | beneficial | 19/93 | [+0.062, +0.180] |
| synthetic | Mistral v0.1->Mistral v0.3 | -0.030 | -0.060 | -0.030 | **-0.045** | neutral | 28/1 | [-0.083, -0.013] |
| synthetic | Qwen2.5->Qwen3-think_long [secondary (think_long)] | +0.000 | +0.063 | +0.000 | **+0.032** | neutral | 0/19 | [+0.013, +0.053] |
| BFCL | Mistral v0.1->Mistral v0.2 | -0.083 | -0.067 | -0.163 | **-0.115** | harmful | 114/45 | [-0.182, -0.050] |
| BFCL | Mistral v0.2->Mistral v0.3 | +0.137 | +0.153 | +0.220 | **+0.187** | beneficial | 13/125 | [+0.133, +0.243] |
| BFCL | Mistral v0.1->Mistral v0.3 | +0.053 | +0.087 | +0.057 | **+0.072** | beneficial | 16/59 | [+0.035, +0.110] |
| BFCL | Qwen2.5->Qwen3 [pre-fix] | -0.100 | -0.230 | -0.230 | **-0.230** | harmful | 152/14 | [-0.282, -0.180] |
| BFCL | Mistral v0.1->Mistral v0.2 | -0.083 | -0.067 | -0.163 | **-0.115** | harmful | 114/45 | [-0.182, -0.050] |
| BFCL | Mistral v0.2->Mistral v0.3 | +0.137 | +0.153 | +0.220 | **+0.187** | beneficial | 13/125 | [+0.133, +0.243] |
| BFCL | Mistral v0.1->Mistral v0.3 | +0.053 | +0.087 | +0.057 | **+0.072** | beneficial | 16/59 | [+0.035, +0.110] |
| BFCL | Qwen2.5->Qwen3-nothink [primary (nothink)] | +0.017 | +0.013 | +0.017 | **+0.015** | neutral | 12/21 | [-0.020, +0.050] |
| BFCL | Mistral v0.1->Mistral v0.2 | -0.083 | -0.067 | -0.163 | **-0.115** | harmful | 114/45 | [-0.182, -0.050] |
| BFCL | Mistral v0.2->Mistral v0.3 | +0.137 | +0.153 | +0.220 | **+0.187** | beneficial | 13/125 | [+0.133, +0.243] |
| BFCL | Mistral v0.1->Mistral v0.3 | +0.053 | +0.087 | +0.057 | **+0.072** | beneficial | 16/59 | [+0.035, +0.110] |
| BFCL | Qwen2.5->Qwen3-think_long [secondary (think_long)] | +0.013 | -0.003 | +0.000 | **-0.002** | neutral | 21/20 | [-0.038, +0.032] |

## 2. Gate accuracy: LOUO-selected canary (k=30), random canary (1000x, k=30), baseline-only gate

LOUO selection: for each decision, informativeness = mean |per-task stress diff| over the OTHER 3 decisions IN THE SAME QWEN-VARIANT SET (so a Mistral pair's canary is now selected partly using the corrected, much-smaller Qwen signal -- this is exactly the mechanism that can make Mistral canaries change too, see note below the table).

| suite | qwen variant | decision | truth | selected@k=30 | correct? | random match rate | baseline-only | agrees? |
|---|---|---|---|---|---|---|---|---|
| synthetic | - | Mistral v0.1->Mistral v0.2 | harmful | harmful (-0.450) | YES | 0.999 | neutral (+0.000) | no |
| synthetic | - | Mistral v0.2->Mistral v0.3 | beneficial | beneficial (+0.306) | YES | 0.938 | neutral (-0.030) | no |
| synthetic | - | Mistral v0.1->Mistral v0.3 | neutral | harmful (-0.111) | no | 0.648 | neutral (-0.030) | YES |
| synthetic | pre-fix | Qwen2.5->Qwen3 [pre-fix] | neutral | harmful (-0.067) | no | 0.680 | neutral (-0.003) | YES |
| synthetic | - | Mistral v0.1->Mistral v0.2 | harmful | harmful (-0.467) | YES | 0.999 | neutral (+0.000) | no |
| synthetic | - | Mistral v0.2->Mistral v0.3 | beneficial | beneficial (+0.328) | YES | 0.926 | neutral (-0.030) | no |
| synthetic | - | Mistral v0.1->Mistral v0.3 | neutral | harmful (-0.128) | no | 0.666 | neutral (-0.030) | YES |
| synthetic | primary (nothink) | Qwen2.5->Qwen3-nothink [primary (nothink)] | neutral | beneficial (+0.056) | no | 0.912 | neutral (+0.000) | YES |
| synthetic | - | Mistral v0.1->Mistral v0.2 | harmful | harmful (-0.467) | YES | 1.000 | neutral (+0.000) | no |
| synthetic | - | Mistral v0.2->Mistral v0.3 | beneficial | beneficial (+0.328) | YES | 0.933 | neutral (-0.030) | no |
| synthetic | - | Mistral v0.1->Mistral v0.3 | neutral | harmful (-0.128) | no | 0.621 | neutral (-0.030) | YES |
| synthetic | secondary (think_long) | Qwen2.5->Qwen3-think_long [secondary (think_long)] | neutral | beneficial (+0.056) | no | 0.899 | neutral (+0.000) | YES |
| BFCL | - | Mistral v0.1->Mistral v0.2 | harmful | harmful (-0.300) | YES | 0.881 | harmful (-0.083) | YES |
| BFCL | - | Mistral v0.2->Mistral v0.3 | beneficial | beneficial (+0.344) | YES | 0.999 | beneficial (+0.137) | YES |
| BFCL | - | Mistral v0.1->Mistral v0.3 | beneficial | beneficial (+0.072) | YES | 0.720 | beneficial (+0.053) | YES |
| BFCL | pre-fix | Qwen2.5->Qwen3 [pre-fix] | harmful | harmful (-0.222) | YES | 1.000 | harmful (-0.100) | YES |
| BFCL | - | Mistral v0.1->Mistral v0.2 | harmful | harmful (-0.306) | YES | 0.901 | harmful (-0.083) | YES |
| BFCL | - | Mistral v0.2->Mistral v0.3 | beneficial | beneficial (+0.328) | YES | 1.000 | beneficial (+0.137) | YES |
| BFCL | - | Mistral v0.1->Mistral v0.3 | beneficial | beneficial (+0.078) | YES | 0.749 | beneficial (+0.053) | YES |
| BFCL | primary (nothink) | Qwen2.5->Qwen3-nothink [primary (nothink)] | neutral | neutral (+0.028) | YES | 0.882 | neutral (+0.017) | YES |
| BFCL | - | Mistral v0.1->Mistral v0.2 | harmful | harmful (-0.317) | YES | 0.867 | harmful (-0.083) | YES |
| BFCL | - | Mistral v0.2->Mistral v0.3 | beneficial | beneficial (+0.350) | YES | 1.000 | beneficial (+0.137) | YES |
| BFCL | - | Mistral v0.1->Mistral v0.3 | beneficial | beneficial (+0.078) | YES | 0.730 | beneficial (+0.053) | YES |
| BFCL | secondary (think_long) | Qwen2.5->Qwen3-think_long [secondary (think_long)] | neutral | neutral (+0.028) | YES | 0.948 | neutral (+0.013) | YES |

**Note on Mistral canary changes:** because Mistral canary selection partly depends on the Qwen decision's per-task diffs (cross-pair informativeness), the Mistral rows' `selected@k=30` values can differ across the three Qwen-variant blocks above even though the Mistral runs themselves are identical in all three -- any such difference is coming entirely from which tasks get selected, not from any change in Mistral's own scores.


## 3. Calibration fits (alpha, least squares through origin, k=30)

alpha = sum(full_i * canary_i) / sum(canary_i^2) (same as `scripts/analyze_gate_threshold_sensitivity.py:fit_alpha`). LOUO: alpha fit on the other 3 decisions, applied to the held-out one. Family transfer: alpha(Mistral->Qwen) fit on the 3 Mistral decisions (n=3); alpha(Qwen->Mistral) fit on the single Qwen decision (n=1, always unstable -- see AUDIT.md J22).

| suite | qwen variant | LOUO alpha (M12, M23, M13, Qwen) | alpha(Mistral->Qwen) | alpha(Qwen->Mistral) | magnitude MAE: raw / LOUO-cal |
|---|---|---|---|---|---|
| synthetic | pre-fix | 0.41, 0.38, 0.39, 0.38 | 0.38 | 0.62 | 0.139 / 0.011 |
| synthetic | primary (nothink) | 0.38, 0.36, 0.37, 0.37 | 0.37 | 0.57 | 0.152 / 0.006 |
| synthetic | secondary (think_long) | 0.38, 0.36, 0.37, 0.37 | 0.37 | 0.57 | 0.152 / 0.006 |
| BFCL | pre-fix | 0.70, 0.63, 0.58, 0.49 | 0.49 | 1.03 | 0.088 / 0.069 |
| BFCL | primary (nothink) | 0.59, 0.41, 0.48, 0.49 | 0.49 | 0.54 | 0.088 / 0.038 |
| BFCL | secondary (think_long) | 0.55, 0.39, 0.45, 0.47 | 0.47 | -0.06 | 0.100 / 0.040 |

**What changes because the Qwen pair is now neutral (not harmful/decisive):**
- `alpha(Qwen->Mistral)` (the single-point fit) is now fit on a near-zero full diff with a correspondingly different canary diff -- this was already flagged as statistically meaningless with n=1 (AUDIT.md J22), and a near-zero full value makes the ratio even more sensitive to canary-selection noise than before (a small canary-diff denominator change can swing alpha sharply). Treat every `alpha(Qwen->Mistral)` value in this table as illustrative, never as a calibration to rely on.
- The Qwen decision's own LOUO alpha and predicted magnitude move accordingly, but since the decision is neutral either way (pre-fix on BFCL was the one exception -- harmful -- and that's precisely the row that changes), the *decision accuracy* impact is really about whether the corrected BFCL Qwen row still gates to the same label under calibration, which table 1 above already answers directly (gate label), not something calibration adds information to here.


## 4. K24-style ranking/gap table: per-condition gaps + bootstrap CI, Qwen2.5 vs each Qwen3 variant

(Mistral rows are unchanged from AUDIT.md K24 and are not repeated here; only the Qwen2.5->Qwen3 row changes.)

| suite | qwen variant | condition | diff | 95% CI | significant? |
|---|---|---|---|---|---|
| synthetic | pre-fix | baseline | -0.0033 | [-0.0100, +0.0000] | n.s. |
| synthetic | pre-fix | schema_drift | -0.0300 | [-0.0967, +0.0367] | n.s. |
| synthetic | pre-fix | runtime_fault | -0.0533 | [-0.0800, -0.0267] | significant |
| synthetic | pre-fix | **sign agreement** | ALL SAME SIGN | | |
| synthetic | primary (nothink) | baseline | +0.0000 | [+0.0000, +0.0000] | n.s. |
| synthetic | primary (nothink) | schema_drift | +0.0633 | [+0.0267, +0.1067] | significant |
| synthetic | primary (nothink) | runtime_fault | +0.0000 | [+0.0000, +0.0000] | n.s. |
| synthetic | primary (nothink) | **sign agreement** | SIGNS DISAGREE | | |
| synthetic | secondary (think_long) | baseline | +0.0000 | [+0.0000, +0.0000] | n.s. |
| synthetic | secondary (think_long) | schema_drift | +0.0633 | [+0.0267, +0.1067] | significant |
| synthetic | secondary (think_long) | runtime_fault | +0.0000 | [+0.0000, +0.0000] | n.s. |
| synthetic | secondary (think_long) | **sign agreement** | SIGNS DISAGREE | | |
| BFCL | pre-fix | baseline | -0.1000 | [-0.1567, -0.0467] | significant |
| BFCL | pre-fix | schema_drift | -0.2300 | [-0.3033, -0.1600] | significant |
| BFCL | pre-fix | runtime_fault | -0.2300 | [-0.2933, -0.1667] | significant |
| BFCL | pre-fix | **sign agreement** | ALL SAME SIGN | | |
| BFCL | primary (nothink) | baseline | +0.0167 | [-0.0167, +0.0533] | n.s. |
| BFCL | primary (nothink) | schema_drift | +0.0133 | [-0.0300, +0.0600] | n.s. |
| BFCL | primary (nothink) | runtime_fault | +0.0167 | [-0.0200, +0.0533] | n.s. |
| BFCL | primary (nothink) | **sign agreement** | ALL SAME SIGN | | |
| BFCL | secondary (think_long) | baseline | +0.0133 | [-0.0233, +0.0500] | n.s. |
| BFCL | secondary (think_long) | schema_drift | -0.0033 | [-0.0500, +0.0433] | n.s. |
| BFCL | secondary (think_long) | runtime_fault | +0.0000 | [-0.0367, +0.0367] | n.s. |
| BFCL | secondary (think_long) | **sign agreement** | SIGNS DISAGREE | | |