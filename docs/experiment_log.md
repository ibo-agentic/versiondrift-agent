# Experiment Log

Dated notes on runs, findings, and harness changes. Comparisons listed here
are exploratory until the noted harness fixes land.

## 2026-09-28 — Real pilot comparison: Mistral v0.2 vs v0.3 (exploratory)

- Runs: `upgradecanary-real-pilot-v0.2_seed1234_20260928T115309Z` and
  `upgradecanary-real-pilot-v0.3_seed1234_20260928T184507Z`.
  300/300 perfectly paired records (same seed → same perturbation assignment).
- Paired success (v0.2 → v0.3), n=100 per condition:
  baseline 100 → 88; schema_drift 66 → 55; runtime_fault 78 → 100.
- Bootstrap 95% CI of paired mean difference (B=10000, seed 1234):
  baseline −0.120 [−0.190, −0.060]; schema_drift −0.110 [−0.190, −0.030];
  runtime_fault +0.220 [+0.140, +0.300]. All exclude zero.
- Finding 1 (metric fairness): v0.3 strips whitespace in calculator
  expressions (`"7*3+11"` vs expected `"7 * 3 + 11"`). Mathematically equal,
  but `args_intent_match` compared strings literally and marked it a mismatch
  (concentrated in calculator tasks 056–070: baseline −12, field_rename −15).
  Fix: AST-based arithmetic equivalence inside intent matching;
  `args_exact` stays strict.
- Finding 2 (harness shim): on `type_mutation` and `unexpected_field`, v0.3
  adapted correctly at protocol level (`args_valid_under_drift` = 1.0) yet
  scored 0, because canonical execution did not coerce drifted string values
  back to canonical numeric types and passed drift-only fields to mock
  handlers that reject them. v0.2 failed earlier (validation) for the same 0.
  Fix: canonicalize types ("3" → 3) and drop drift-only fields before
  execution; `args_valid_under_drift` stays strict against the drifted schema.
- Conclusion: the v0.2 vs v0.3 comparison above is exploratory. Both models
  must be rerun after these fixes for a fair comparison.

## 2026-09-28 — Fairness fixes applied; score redefined to functional success

- Fairness fixes applied (semantic expression matching; canonical type
  coercion and drift-only field dropping before execution) and both models
  rerun: v0.2 `..._20260928T191059Z`, v0.3 `..._20260928T191615Z`.
- New issue found: the score formula still gated baseline on `args_exact`, so
  v0.3 baseline scored 0.88 with every functional metric at 1.0 (calculator
  whitespace only). Redefined: `score` = `parse_ok ∧ tool_name_ok ∧
  args_intent_match ∧ args_valid_under_drift ∧ executor_ok`, identical for all
  conditions. `args_exact` and `recovered_after_fault` are diagnostic only.
  Parser, drifted-schema validity, and executor validation unchanged.
- Recomputed offline from the fair-rerun folders (no model reruns).
  Old formula (stored summary.json): baseline 1.00/0.88, schema_drift
  0.84/0.82, runtime_fault 0.78/1.00 (v0.2/v0.3).
  New functional score: baseline 1.00/1.00 (diff 0.00); schema_drift 0.84/0.82
  (15 neg / 13 pos flips, diff −0.020, 95% CI [−0.120, +0.080] — no
  significant difference); runtime_fault 0.78/1.00 (diff +0.220, CI
  [+0.140, +0.300] — significant v0.3 improvement).
- Interpretation under the repaired harness: v0.3 matches v0.2 on baseline and
  schema drift (its protocol-validity advantage is real: valid 0.91→1.00,
  executor_ok 0.91→1.00, but intent is a wash: 0.92 vs 0.82 in opposite
  directions per task) and is strictly better at fault recovery.

## 2026-09-28 — Fix: renamed-expression intent artifact (prior schema_drift conclusions invalid)

- Artifact: the arithmetic-equivalence check in intent matching keyed on the
  literal argument name "expression". Under the `expression`→`expr` rename,
  the comparison saw key "expr", missed the special case, and fell back to
  string equality — marking v0.3's correctly adapted `{"expr": "7*3+11"}`
  calls as intent failures (44/45 calculator rename records in the
  repeated-trial runs; concentrated in tasks 056–070).
- Why it skewed v0.3: v0.3 both adapts the rename and strips whitespace, and
  only that combination hit the missed key; v0.2 kept original spacing and
  never triggered it. The repeated-trial schema_drift result (pooled
  0.86/0.82, diff −0.047, CI [−0.137, +0.043]) was artifact-inflated against
  v0.3, and every earlier schema_drift conclusion involving calculator
  field_rename is invalid.
- Fix: `compatible()` now maps drifted keys back to canonical names
  (`_canonical_key`) before per-argument semantic comparison.
  `args_exact`, `args_valid_under_drift`, executor validation, and the
  functional score formula are unchanged.
- Corrected metrics were recomputed offline from the saved parsed_results of
  the repeated-trial runs (no model reruns) and written beside the originals
  as `parsed_results_corrected.jsonl` / `summary_corrected.json`. The
  corrected paired analysis is the authoritative schema_drift comparison.

## 2026-09-29 — Matched itlwas three-version phase begins

- The earlier v0.2 vs v0.3 comparison used whatever quantizer each release
  shipped with (mixed quantizers), so it is preliminary: part of any
  difference could be quantization, not the model generation.
- The matched phase uses the itlwas Q4_K_M set (v0.1/v0.2/v0.3, same
  quantizer, ~4.07 GiB each under `models/itlwas/`) with configs
  `configs/real_trials_itlwas_v0.{1,2,3}.yaml` — identical settings to the
  trials configs otherwise. This enables clean across-version comparisons:
  v0.1→v0.2 (tool/function-calling training introduced) and v0.2→v0.3
  (tokenizer v3 + training refresh).
