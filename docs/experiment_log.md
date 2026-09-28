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
