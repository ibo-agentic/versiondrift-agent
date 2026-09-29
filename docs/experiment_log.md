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

## 2026-09-29 — Matched itlwas three-version results (analysis: scripts/analyze_version_trials.py)

- Runs: `..._v0.1_...T120210Z`, `..._v0.2_...T121701Z`, `..._v0.3_...T132749Z`;
  900/900 records matched across all three (task, condition, drift, fault,
  trial).
- Context caveat: v0.3 ran with n_ctx=1024 (v0.1/v0.2: 2048). Assessment: the
  125 unique prompts are byte-identical across versions, 510–857 chars
  (~150–250 tokens at conservative estimates) against a 768-token prompt
  budget; v0.3 shows zero truncation signals (0 unclosed outputs, 0 parse
  failures, max output 105 chars); its 9 baseline failures are deterministic
  query-paraphrase behavior on tasks 023/029/035, identical across all
  trials. Comparison valid; a 2048 rerun of v0.3 is still desirable for
  exactness.
- Pooled functional scores (v0.1 / v0.2 / v0.3): baseline 1.00 / 1.00 / 0.97;
  schema_drift 0.99 / 0.90 / 0.93; runtime_fault 1.00 / 0.76 / 0.97.
- Pairwise (task-level cluster bootstrap 95% CI): v0.1→v0.2: drift −0.093
  [−0.143, −0.047], fault −0.243 [−0.323, −0.167] — significant regressions
  (field_drop 0.93→0.43, unexpected_field 0.97→0.60, fault recovery collapse
  on tool_exception 1.00→0.49). v0.2→v0.3: fault +0.213 [+0.123, +0.307]
  significant (recovery back to ~1.00); drift +0.033 [−0.023, +0.090] not
  significant. v0.1→v0.3: drift −0.060 [−0.107, −0.020] significant; fault
  −0.030 [−0.070, 0.000] marginal.
- Consistency (mean per task×condition score range over trials): v0.3 0.007 <
  v0.1 0.010 << v0.2 0.060. All-trials-succeed: 297/300 (v0.1), 257/300
  (v0.2), 286/300 (v0.3).
- Main findings: (1) v0.1 is the strongest on this harness — the v0.2
  function-calling training coincided with a large robustness regression,
  especially retry-after-fault behavior; (2) v0.3 recovers most of it and is
  the most consistent of the three, but does not fully reach v0.1 on fault
  recovery or baseline query fidelity; (3) the earlier mixed-quantizer
  v0.2→v0.3 direction (large fault-recovery gain) replicates under matched
  quantizers (+0.21), so that preliminary conclusion stands.

## 2026-09-29 — Release-gate simulation: canary subsets predict upgrade outcomes

- Design: paired matching as before (task, condition, drift, fault, trial);
  ground truth = full-suite stress difference (schema_drift + runtime_fault
  pooled, 600 records); harmful < −0.05, beneficial > +0.05, else neutral.
  200 deterministic subsets per size (10/20/30/40/50 tasks; sampling seed
  20240929). Script: `scripts/analyze_release_gate.py`.
- Full-suite truth: v0.1→v0.2 = −0.168 (harmful); v0.2→v0.3 = +0.123
  (beneficial).
- Results: v0.1→v0.2 is easy to flag — 93.5% accuracy at 10 tasks, 100% from
  30; false-accept 6.5% at size 10, 0% from 30. v0.2→v0.3 is harder
  (beneficial signal driven by fault recovery; drift alone is neutral):
  false-reject 24% at 10 tasks, 9% at 30, 4% at 40, 1% at 50.
- Best tradeoff: 40 tasks — minimum size reaching ≥0.95 accuracy on every
  pair (0.96 / 1.00). At 40 tasks the canary runs ~3x fewer records than the
  full suite with near-certain gating.
- Informativeness: runtime_fault categories dominate both upgrades
  (tool_exception ±0.51, partial_result ±0.30; a fault-only canary gates both
  pairs correctly); schema_drift field_drop (−0.50) and unexpected_field
  (−0.37/+0.33) carry the v0.1→v0.2 harm and part of the v0.2→v0.3 recovery.
  Top single tasks: 015/017 (±0.83), 011/019/020 (±0.67).
- Limitations: only two upgrade pairs (one harmful, one beneficial) from a
  single model family; thresholds (±0.05, 0.95 accuracy) chosen post hoc;
  subsets sampled from the same 100 tasks that define the ground truth
  (in-distribution); AUROC undefined with two pairs. See docs/paper_story.md.

## 2026-09-29 — v0.3 matched-context rerun: caveat closed, Mistral phase complete

- Rerun: `upgradecanary-real-trials-itlwas-v0.3_seed1234_20260929T192811Z`
  with n_ctx=2048 (matching v0.1/v0.2). Verified: its summary is identical
  to the earlier n_ctx=1024 run (`..._20260929T132749Z`) apart from run_id —
  baseline 0.97, schema_drift 0.93, runtime_fault 0.97, n=300 per condition.
  The low-context assessment is confirmed; no truncation or prompt-fit
  effects existed at 1024 either.
- The v0.3 context caveat is now closed. No open methodological caveats
  remain for the matched Mistral phase: same Q4_K_M quantizer (itlwas set),
  same context length, same seeds/trials across v0.1/v0.2/v0.3.
- Matched Mistral phase status: methodologically complete. Reference
  findings (see entries above): v0.1 strongest overall (fault recovery
  1.00, drift 0.99); v0.2 significantly regressed (fault −0.243, drift
  −0.093 vs v0.1); v0.3 recovered most of it (fault 0.97, drift 0.93) and is
  the most consistent (mean per-task range 0.007). Release-gate reference
  numbers: 40-task in-distribution canary at >= 0.95 accuracy; 10–20 task
  canaries selected on one upgrade pair classify the held-out pair with zero
  errors (leave-one-upgrade-out validation).
