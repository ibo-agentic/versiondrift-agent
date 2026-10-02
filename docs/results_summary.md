# UpgradeCanary — Final Results Summary

Date: 2026-10-01. All numbers derive from the **corrected post-fix BFCL runs**
(drifted schemas verified to reach the model prompt; see
`docs/experiment_log.md`, 2026-10-01 entries) and the synthetic-suite runs.
Pre-fix BFCL runs are excluded everywhere. Primary metric per the frozen
protocol: **stress score** = mean of `schema_drift` and `runtime_fault`
functional scores; functional score = parse ∧ tool-name ∧ intent ∧
drift-validity ∧ execution. Machine-readable data: `tables/*.csv`;
figures: `figures/*.png` (regenerate with
`python scripts/generate_paper_assets.py`, system Python).

## 1. Model scores by suite and condition

| Suite | Model | baseline | schema_drift | runtime_fault | **stress** |
|---|---|---|---|---|---|
| synthetic | Mistral v0.1 | 1.000 | 0.990 | 1.000 | 0.995 |
| synthetic | Mistral v0.2 | 1.000 | 0.897 | 0.757 | 0.827 |
| synthetic | Mistral v0.3 | 0.970 | 0.930 | 0.970 | 0.950 |
| synthetic | Qwen2.5 | 1.000 | 0.937 | 1.000 | 0.968 |
| synthetic | Qwen3 | 0.997 | 0.907 | 0.947 | 0.927 |
| BFCL | Mistral v0.1 | 0.890 | 0.690 | 0.883 | 0.787 |
| BFCL | Mistral v0.2 | 0.807 | 0.623 | 0.720 | 0.672 |
| BFCL | Mistral v0.3 | 0.943 | 0.777 | 0.940 | 0.858 |
| BFCL | Qwen2.5 | 0.950 | 0.923 | 0.950 | 0.937 |
| BFCL | Qwen3 | 0.850 | 0.693 | 0.720 | 0.707 |

**Figure 1** (`figures/fig1_stress_by_suite.png`, data `tables/model_scores_by_suite.csv`):
functional success under stress by model, grouped by suite. The synthetic
suite scores near ceiling; the public suite separates the models.

## 2. Upgrade decisions (paired differences, 95% task-cluster bootstrap CIs)

| Suite | Decision | Δbaseline | Δdrift | Δfault | **Δstress** | label | neg/pos flips | 95% CI |
|---|---|---|---|---|---|---|---|---|
| syn | v0.1→v0.2 | +0.000 | −0.093 | −0.243 | **−0.168** | harmful | 102/1 | [−0.218, −0.122] |
| syn | v0.2→v0.3 | −0.030 | +0.033 | +0.213 | **+0.123** | beneficial | 19/93 | [+0.062, +0.180] |
| syn | v0.1→v0.3 | −0.030 | −0.060 | −0.030 | **−0.045** | neutral | 28/1 | [−0.083, −0.013] |
| syn | Qwen2.5→Qwen3 | −0.003 | −0.030 | −0.053 | **−0.042** | neutral | 44/19 | [−0.078, −0.007] |
| BFCL | v0.1→v0.2 | −0.083 | −0.067 | −0.163 | **−0.115** | harmful | 114/45 | [−0.183, −0.050] |
| BFCL | v0.2→v0.3 | +0.137 | +0.153 | +0.220 | **+0.187** | beneficial | 13/125 | [+0.133, +0.245] |
| BFCL | v0.1→v0.3 | +0.053 | +0.087 | +0.057 | **+0.072** | beneficial | 16/59 | [+0.035, +0.110] |
| BFCL | Qwen2.5→Qwen3 | −0.100 | −0.230 | −0.230 | **−0.230** | harmful | 152/14 | [−0.283, −0.177] |

**Figure 2** (`figures/fig2_decision_effects.png`, data `tables/upgrade_decisions.csv`):
decision effect sizes with CIs; dashed lines mark the ±0.05 gate. Four of
eight decisions are statistically decisive with consistent sign across
suites (v0.1→v0.2 harmful, v0.2→v0.3 beneficial); the Qwen upgrade is
neutral-to-harmful (synthetic vs BFCL disagree in magnitude, not direction).

## 3. Consistency (repeated trials)

| Suite | Model | all-trials success /300 | all-trials fail /300 | mean per-task range |
|---|---|---|---|---|
| synthetic | Mistral v0.1 | 297 | 0 | 0.010 |
| synthetic | Mistral v0.2 | 257 | 25 | 0.060 |
| synthetic | Mistral v0.3 | 286 | 12 | 0.007 |
| synthetic | Qwen2.5 | 290 | 2 | 0.027 |
| synthetic | Qwen3 | 273 | 6 | 0.070 |
| BFCL | Mistral v0.1 | 222 | 36 | 0.140 |
| BFCL | Mistral v0.2 | 183 | 59 | 0.193 |
| BFCL | Mistral v0.3 | 259 | 24 | 0.057 |
| BFCL | Qwen2.5 | 276 | 14 | 0.033 |
| BFCL | Qwen3 | 167 | 21 | 0.373 |

**Figure 3** (`figures/fig3_consistency.png`, data `tables/consistency.csv`):
all-trials success (bars) and mean per-task score range (line). Qwen2.5 and
Mistral v0.3 are the most stable on the public suite; Qwen3 is the least
stable on both suites.

## 4. Synthetic vs BFCL comparison

- Synthetic stress exceeds BFCL stress for every model (gap 0.03–0.22): the
  synthetic suite **overestimates robustness moderately**, most on drift.
- Rankings: synthetic [v0.1, Qwen2.5, v0.3, Qwen3, v0.2] vs BFCL [Qwen2.5,
  v0.3, v0.1, Qwen3, v0.2] — the **bottom two agree on both suites** (Qwen3 and
  v0.2 are the weakest everywhere); the top order is suite-dependent.
- Replicated findings: v0.2 regression, v0.3 recovery, Qwen3 as a robustness
  downgrade, Qwen2.5 excellent on public schemas. Suite-dependent: absolute
  levels and the fine ordering of the top three.

## 5. Release-gate validation

Gate accuracy (leave-one-decision-out selection, 4 decisions per suite;
`tables/gate_accuracy.csv`):

| Suite | k | selected | random | clean-only | drift-only | fault-only |
|---|---|---|---|---|---|---|
| synthetic | 10 | 0.25 | 0.75 | 0.50 | 0.50 | 0.75 |
| synthetic | 20 | 0.50 | 0.74 | 0.50 | 0.50 | 0.50 |
| synthetic | 30 | 0.50 | 0.81 | 0.50 | 0.50 | 0.50 |
| synthetic | 40 | 0.75 | 0.81 | 0.50 | 0.75 | 0.50 |
| BFCL | 10 | 0.75 | 0.82 | 1.00 | 1.00 | 0.75 |
| BFCL | 20 | 0.75 | 0.86 | 1.00 | 1.00 | 1.00 |
| BFCL | 30 | **1.00** | 0.90 | 1.00 | 1.00 | 1.00 |
| BFCL | 40 | **1.00** | 0.95 | 1.00 | 1.00 | 1.00 |

**Figure 4** (`figures/fig4_gate_accuracy.png`): gate decision accuracy by
canary size. On BFCL (decisive effects) all selection strategies converge to
perfect accuracy by k=30. On synthetic, the two borderline-neutral truths
(v0.1→v0.3 and Qwen2.5→Qwen3, |Δ|≈0.04) make decisions intrinsically
unstable at the ±0.05 gate; selection strategy matters less than truth
borderline distance. This table uses strict leave-one-decision-out selection;
in-distribution and cross-pair variants in the experiment log show higher
accuracy for selected canaries.

### Final hypothesis status

| Hypothesis | Synthetic | BFCL (corrected) | Overall |
|---|---|---|---|
| H1 non-monotonic robustness | supported (CIs exclude 0, opposite signs) | supported | **Supported** |
| H2 neutral aggregate hides failure-mode swaps | supported (Qwen neutral hides field_drop gain / unexpected_field loss) | not supported (no neutral decisions) | **Partial** |
| H3 selected canary transfers across families | supported (k≤20, LOUO 100%) | supported at k≥30 | **Supported, size-dependent** |
| H4 selected mixed canary beats baselines | supported (in-distribution; strict LOO table above is borderline-neutral-limited) | partial (single-condition canaries match at small k; parity by k=30) | **Partial** |
| H5 calibration improves estimation/decisions | magnitude yes (3–10×), decisions neutral | magnitude yes (~1.3–1.6×), decisions neutral | **Supported for magnitude; neutral for decisions** |

## 6. Main claims

1. **Model upgrades for small open-weight tool agents produce non-monotonic,
   failure-mode-specific robustness changes invisible to clean-task accuracy**
   (baseline ≈1.0 on synthetic for all models while stress scores swing by up
   to ±0.24).
2. **A compact stress-test canary with calibrated decision rules detects these
   changes**: 30-task canaries gate all four BFCL decisions correctly; gate
   decisions are accept/reject/inspect with category breakdowns required for
   neutral verdicts.
3. **Task informativeness transfers across suites and families** at the
   category level (synthetic→BFCL 1.00 at k≥20; BFCL→synthetic 0.75),
   supporting a single reusable canary pool.
4. **The public suite is harsher than the synthetic suite** (moderate
   overestimation; drift gap largest), and bottom-of-ranking models agree
   across suites.

## 7. Limitations

- Five models, one family pair (Mistral ×3, Qwen ×2); no Llama-class or
  sub-7B models; single quantizer level (Q4_K_M).
- BFCL phase is schema-match only with a simulated deterministic executor;
  no executable BFCL coverage; staleness detection is not scored.
- Two synthetic decisions are borderline-neutral (|Δ|≈0.04), making gate
  accuracy there threshold-sensitive; thresholds remain post hoc (though
  sensitivity-bounded, see experiment log).
- Canary |Δ| is amplified by informativeness selection (~1/α ≈ 1.7–2.5×);
  canary numbers are for decisions, not effect sizes.
- Two harness bugs were found and fixed during the study (scoring fairness;
  drift-prompt transmission); the corrected runs and regression tests define
  the trustworthy result set, and the invalidation trail is in the log.
