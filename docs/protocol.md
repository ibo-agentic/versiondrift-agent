# UpgradeCanary — Frozen Experiment Protocol (main track)

**Status: FROZEN** — frozen before the UpgradeCanary-BFCL-100 confirmatory
phase. Any later change to this protocol must be logged as a deviation in
`docs/experiment_log.md` with date and rationale. Analyses not listed here,
or marked Exploratory below, are not confirmatory.

- Protocol date: 2026-09-30
- Study title: **UpgradeCanary: Detecting Robustness Regressions Across
  Open-Weight Agent Model Upgrades**

## Main claim

Model upgrades for small open-weight tool agents can produce non-monotonic,
failure-mode-specific robustness changes that are invisible to clean-task
accuracy. A compact stress-test canary with calibrated decision rules can
detect these changes.

## Existing completed components

All components below are complete and logged in `docs/experiment_log.md`:

1. **Matched Mistral v0.1/v0.2/v0.3 study** (itlwas Q4_K_M set, 100 tasks ×
   3 conditions × 3 trials, n_ctx=2048 for all): baseline 1.00/1.00/0.97;
   schema_drift 0.99/0.90/0.93; runtime_fault 1.00/0.76/0.97. v0.1→v0.2
   significantly regressed (fault −0.243, drift −0.093, task-cluster CIs
   excluding zero); v0.2→v0.3 recovered fault performance (+0.213) without a
   significant drift change.
2. **Qwen2.5→Qwen3 second-family study**: baseline 1.00/1.00; drift 0.94→0.91
   (n.s.); fault 1.00→0.95 (significant); pooled stress −0.042 → gate-neutral
   with a category swap underneath (field_drop 0.40→1.00; unexpected_field
   1.00→0.13).
3. **Repeated trials** (1 greedy + 2 sampled at temperature 0.7, distinct
   seeds) on every task-condition.
4. **Paired negative-flip / positive-flip analysis** matched on task,
   condition, drift type, fault type, trial index.
5. **Task-level cluster bootstrap** 95% confidence intervals (resample tasks,
   keeping all conditions/trials together).
6. **Leave-one-upgrade-out gate validation** (canary selected on one upgrade
   pair classifies the held-out pair; zero errors at k≥10 within-family).
7. **Cross-family gate transfer tests** (Mistral-selected → Qwen; Qwen-selected
   → Mistral): sign transfer holds both ways; small-k canaries overflag
   borderline-neutral upgrades (see Exploratory).
8. **Threshold sensitivity analysis** (t = 0.01…0.10 × k = 10…50): stable raw
   region t ∈ [0.01, 0.03] (all k), widening to 0.04 at k ≥ 20; sign accuracy
   1.00 everywhere.
9. **Canary calibration analysis** (full ≈ α·canary, α ≈ 0.35–0.51): LOUO
   magnitude MAE 0.007–0.046 vs raw 0.085–0.139; calibrated decisions repair
   the ±0.05 threshold band; family transfer reliable Mistral→Qwen only.

## Hypotheses

### H1 — Model-upgrade robustness is non-monotonic
Upgrading to a newer checkpoint does not guarantee better (or worse)
robustness; robustness can regress and later recover across versions.
- **Supports:** paired diffs with task-cluster CIs excluding zero in opposite
  directions across consecutive upgrade pairs on the same family (observed:
  v0.1→v0.2 negative, v0.2→v0.3 positive on runtime_fault).
- **Weakens:** consecutive upgrades consistently showing the same signed
  difference with overlapping CIs, on both families.

### H2 — Aggregate-neutral upgrades can hide failure-mode swaps
A pooled stress difference near zero can coexist with large opposite-signed
category effects.
- **Supports:** gate-neutral upgrades (M v0.1→v0.3; Qwen2.5→Qwen3) whose
  per-category breakdowns show |effect| ≥ 0.3 in both directions
  (observed: Qwen3 field_drop +0.60 vs unexpected_field −0.87).
- **Weakens:** neutral pooled verdicts accompanied by uniformly small
  (|effect| < 0.1) category breakdowns.

### H3 — A selected compact canary transfers across model families
Task sets selected by cross-pair informativeness from one family carry
decision-relevant signal for another family's upgrade.
- **Supports:** held-out-pair classification correct in both transfer
  directions at the protocol's k (Qwen-selected → Mistral correct at all
  k ≥ 10; Mistral-selected → Qwen sign-correct at all k).
- **Weakens:** transfer accuracy at or below the random-subset baseline in
  either direction.

### H4 — Selected mixed canary beats baselines
An informativeness-selected canary spanning both stress conditions outperforms
random subsets and single-condition canaries (clean-only, drift-only,
fault-only) of the same size.
- **Supports:** higher decision accuracy than random-subset baselines
  (observed in all validation cells) **and** than drift-only/fault-only
  ablations in the BFCL-100 phase; clean-only expected to miss stress
  regressions by construction (baseline condition is the secondary metric).
- **Weakens:** parity with random subsets, or any single-condition baseline
  matching the mixed canary's decision accuracy.

### H5 — Calibrated canary differences improve estimation and decisions
Shrinking canary differences by a historically estimated α improves magnitude
estimation and thresholded decision quality versus raw canary differences.
- **Supports:** LOUO-calibrated magnitude MAE well below raw (observed 3–10×)
  and higher decision accuracy at t = 0.05 (observed 0.50→0.75–1.00 at k ≥ 20).
- **Weakens:** calibrated MAE ≥ raw MAE, or calibrated decision accuracy ≤
  raw across the threshold sweep.

## Primary metric

**Functional score under stress** = average of the schema_drift and
runtime_fault functional scores, where each record's functional score is:

```
parse_ok ∧ tool_name_ok ∧ args_intent_match ∧ args_valid_under_drift ∧ executor_ok
```

(all already-implemented metrics; no changes). Computed per record, averaged
per condition and pooled across the two stress conditions for the gate.

Baseline (clean-condition) performance is a **secondary** metric; an upgrade
that preserves baseline but moves stress scores is the primary concern of
this study.

## Secondary metrics

- baseline functional score (clean condition)
- paired score differences (per condition, per category, pooled stress)
- negative flips and positive flips (paired per record)
- task-level cluster bootstrap 95% confidence intervals
- repeated-trial consistency: all-trial success count per task × condition,
  all-trial failure count, per-task score range across trials
- failure-category breakdowns (per drift type, per fault type)

## Release-gate protocol (current recommendation)

- **Canary**: 30 tasks selected by cross-pair informativeness
  (mean |task stress diff| over historical decisions, leave-one-out for the
  decision at hand) with category-coverage pass; mixed stress conditions.
- **Trials**: 3 per task-condition where feasible — one greedy
  (temperature 0.0) plus two sampled (temperature 0.7, distinct fixed seeds).
- **Thresholds**: raw canary decisions use t ∈ [0.01, 0.03] (stable region);
  calibrated decisions use ±0.05.
- **Calibration**: α estimated by least squares through the origin from at
  least 3 historical full-suite decisions (α ≈ 0.4 in current data);
  calibrated estimate = α × canary difference.
- **Neutral decisions must include** the per-category breakdown
  (drift types × fault types) in any report — neutral verdicts are
  inspect verdicts by default.
- **Effect sizes** are estimated from the full suite only. Canary decisions
  are for **accept / reject / inspect**; canary differences are not final
  effect-size estimates (selected canaries amplify differences by ~1/α).

## Public-suite phase (next)

**UpgradeCanary-BFCL-100**: a 100-task public-suite confirmatory phase.

- Tasks derived from the public BFCL benchmark (Berkeley Function Calling
  Leaderboard) task pool.
- **Deterministic task-selection rules only**, using task metadata and fixed
  rules (e.g., stratification by function/category annotations, difficulty
  tags, argument-type coverage). **No model-outcome-based selection**: no
  task may be included or excluded based on any model's performance,
  including models in this study.
- Selection rule frozen and recorded before any BFCL-100 run; the rule and
  its inputs are part of the artifacts.
- Same conditions (baseline / schema_drift / runtime_fault), same
  perturbation engine, same evaluator, same repeated-trial setup, and the
  same paired analysis pipeline as this protocol.
- Confirmatory hypotheses: H1, H2, H4, H5 (H3 remains supported/exploratory
  until a third family exists).

## Statistical analysis plan

- **Paired matching** on (task_id, condition, drift type, fault type,
  trial_index); only perfectly matched records enter paired analyses.
- **Confidence intervals**: task-level cluster bootstrap (resample task IDs
  with replacement, keep all conditions/trials of a task together; 10,000
  replicates; fixed seed 1234); percentile 95% intervals.
- **Multiple-comparison correction**: across the two primary conditions
  (schema_drift, runtime_fault) and the pooled stress score, apply
  Holm-Bonferroni within each upgrade decision; corrected α = 0.05.
  Secondary metrics and category breakdowns are descriptive unless stated.
- **Exploratory analyses are labeled separately** (below) and are not part of
  confirmatory claims.

## Exploratory analyses (labeled, non-confirmatory)

- Qwen→Mistral calibration transfer (single training decision; unstable α).
- Category-specific mechanism claims (e.g. "v0.2 regressed via tool_exception
  retries") — hypothesis-generating.
- Any optional third-family results collected before protocol amendment.

## Reproducibility requirements

Required artifacts for any reported result:

- task files (`data/*.jsonl`) and the generator script
- provenance notes (`docs/experiment_log.md` entries, deviations)
- configs (`configs/*.yaml`) exactly as run
- evaluator and perturbation engine (`upgradecanary/`)
- analysis scripts (`scripts/analyze_version_trials.py`,
  `scripts/analyze_release_gate.py`,
  `scripts/validate_release_gate_splits.py`,
  `scripts/validate_cross_family_gate.py`,
  `scripts/analyze_gate_threshold_sensitivity.py`)
- experiment log (`docs/experiment_log.md`)
- **model manifest**: model name, source, quantizer, file path, SHA-256,
  context/trial settings (extend `models/` listing with hashes before
  BFCL-100)
- reproduction commands:
  `python -m upgradecanary.runner --config <config>` per run, then the
  analysis scripts above on the resulting run folders.

## Frozen-statement

This protocol is frozen as of 2026-09-30, before the BFCL-100 confirmatory
phase. Later changes to metrics, thresholds, selection rules, hypotheses, or
analysis plans must be recorded in `docs/experiment_log.md` as dated
deviations with rationale; results produced under a prior protocol must be
re-tagged with the protocol version they followed.

## UpgradeCanary-BFCL-100 selection protocol (amendment)

This section is a dated amendment to the frozen protocol above and a
documented deviation from the original fully-synthetic suite.

### Source
- data source: `external/gorilla/berkeley-function-call-leaderboard/bfcl_eval/data/BFCL_v4_simple_python.json`
- answer source: `external/gorilla/berkeley-function-call-leaderboard/bfcl_eval/data/possible_answer/BFCL_v4_simple_python.json`

### Eligibility rules
A task is eligible only if:
1. it comes from `BFCL_v4_simple_python.json`
2. the `possible_answer` record exists for the same id
3. it has exactly one function
4. it has exactly one expected call
5. the question is printable ASCII
6. the question length is between 20 and 400 characters
7. the question contains no URL or `http` substring
8. every required argument is either grounded in the question text, or has an explicit default
9. all expected argument values are scalar: string, number, or boolean
10. the rendered prompt is under 1200 characters
11. duplicate function names are removed by keeping the first eligible occurrence

### Sampling rule
- select exactly 100 eligible tasks
- seeded stratified sample; strata = parameter-type signature
- fixed seed: **20260930**
- selection depends only on task metadata and never on model outputs

### Drift restriction (deviation from the synthetic suite)
For the BFCL-derived phase, use only: `field_rename`, `field_drop`,
`type_mutation`, `unexpected_field`. `enum_drift` is excluded because BFCL
`simple_python` provides no enum schemas. This is a logged deviation from
the original suite, which includes enum drift.

### Scoring and execution model
- This is a BFCL-derived **schema-match** suite; execution uses a generic
  simulated deterministic executor. No claim of full executable BFCL coverage
  is made.
- The functional score is unchanged; `args_exact` remains diagnostic only.
- Strict JSON parsing, `args_valid_under_drift`, and executor validation are
  unchanged (not weakened).
- Canonical expected call = first non-empty acceptable value per argument
  (deterministic tie-break); the full acceptable-values map is stored per
  task and used by `args_intent_match` as described in the amendment below.

## BFCL acceptable-values intent amendment (dated 2026-09-30)

- BFCL ground truth allows multiple acceptable values per parameter, and uses
  `""` to mean that omitting the parameter is acceptable.
- `args_intent_match` must respect these semantics for BFCL-derived tasks:
  an expected parameter passes if it is present with any value from its
  acceptable set, or omitted when the set contains `""`. Extra arguments are
  tolerated for intent only when they are declared in the active schema or
  part of the task's acceptable map (this covers `field_drop` remnants and
  `unexpected_field` adaptation, which strict validity/execution already
  gate). Required arguments with no `""` entry must still be present.
- When no acceptable map is provided (synthetic suite), intent comparison is
  exactly the pre-amendment behavior.
- `args_valid_under_drift` and executor validation remain strict; strict JSON
  parsing is unchanged; the functional score formula is unchanged. This
  amendment changes intent semantics for BFCL tasks only.
