# Intent-match strictness: human spot-check findings, scaled up

## Human spot-check result

`analysis/audit/intent_spotcheck_filled.csv` (40 records, 20 rule_verdict=true / 20 false, spread across drift types/models/suites): **32/40 agree (80%), Cohen's kappa = 0.60** (moderate agreement). **All 8 disagreements are rule=False, human=True** -- the rule-based `args_intent_match` metric is never too lenient in this sample, only too strict. Five causes account for all 8:

1. **extra `"properties"` wrapper** -- model emits `{"properties": {...actual args...}}` instead of the arguments directly (2/8 cases).
2. **string booleans** -- `"true"`/`"false"` instead of a JSON boolean (2/8 cases).
3. **units attached to numbers** -- `"5m"` instead of `5` (2/8 cases).
4. **unit synonyms** -- `"miles"` instead of `"mi"` (1/8 cases).
5. **swapped order for symmetric args** -- e.g. `team1`/`team2` values exchanged, where the task is symmetric in those two slots (1/8 cases).

**Calibration check** (`_relaxed_intent_calibration.py`): a diagnostic `relaxed_compatible()` implementing exactly these 5 leniencies (new file, `analysis/audit/relaxed_intent.py`, calling `upgradecanary/perturbations/schema_drift.py`'s own canonicalization helpers unchanged -- nothing under `upgradecanary/` was modified) reproduces the human verdict on **39/40** rows when all 5 causes are enabled together. The one exception (`bfcl-simple_python_10`, Qwen2.5) is **not** human-judgment noise -- it is a real rule the 5-cause taxonomy does not capture. The human labeling rule for the "units attached to numbers" cause is narrower than a per-value suffix strip: **a unit-suffixed value is accepted only if the unit is applied *consistently* to every measurement in the call; mixing a unit-suffixed value with a unitless value for another measurement of the same kind -- when a separate `unit` field exists to carry that information once -- is not accepted.** Applying that rule to the two near-identical `bfcl-simple_python_10` records: Mistral v0.3 emitted `{"base": "6cm", "height": "10cm"}` -- the `cm` suffix is attached to *both* measurements consistently, so it reads as a single (if redundant) unit choice applied uniformly, and the human accepted it. Qwen2.5 emitted `{"base": "6cm", "height": 10}` -- `cm` is attached to `base` only, `height` is bare, which is an inconsistent/ambiguous use of units rather than a uniform formatting choice, so the human rejected it. `relaxed_compatible()`'s `unit_number` leniency strips a unit suffix from each value independently and has no notion of consistency across sibling measurements, so it accepts both records -- this is a genuine gap in the taxonomy, not noise in the human label.

**In-sample caveat**: `relaxed_compatible()`'s 5 causes (and their parameters, e.g. the unit-synonym map) were derived directly from this same 40-row sample, and the 39/40 calibration figure above is measured on that same sample -- it is an in-sample, optimistic number, not a held-out validation. **The reportable human-vs-official-rule agreement is 32/40, Cohen's kappa = 0.60** (first line of this section); the 39/40 figure should be read only as "the taxonomy is internally consistent with the sample it was built from, modulo the one gap just described," not as independent evidence that the taxonomy generalizes.


## Part 1: records whose intent failure is attributable to exactly one named cause

For every record with strict `args_intent_match=False`, each cause is tried independently (the other 4 off); a record is attributed to a cause if enabling *that cause alone* flips intent_match to True. A record can be attributed to more than one cause if either alone would resolve it (rare -- tracked separately below).

| suite | model | cond | intent_fail_n | properties_wrapper | string_bool | unit_number | unit_synonym | swapped_symmetric | explained_by_any | explained_by_none |
|---|---|---|---|---|---|---|---|---|---|---|
| synthetic | Mistral v0.1 | baseline | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| synthetic | Mistral v0.1 | schema_drift | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| synthetic | Mistral v0.1 | runtime_fault | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| synthetic | Mistral v0.2 | baseline | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| synthetic | Mistral v0.2 | schema_drift | 19 | 0 | 0 | 0 | 0 | 0 | 0 | 19 |
| synthetic | Mistral v0.2 | runtime_fault | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| synthetic | Mistral v0.3 | baseline | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 9 |
| synthetic | Mistral v0.3 | schema_drift | 19 | 0 | 0 | 0 | 0 | 0 | 0 | 19 |
| synthetic | Mistral v0.3 | runtime_fault | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 9 |
| synthetic | Qwen2.5 | baseline | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| synthetic | Qwen2.5 | schema_drift | 19 | 0 | 0 | 0 | 1 | 0 | 1 | 18 |
| synthetic | Qwen2.5 | runtime_fault | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| synthetic | Qwen3 | baseline | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| synthetic | Qwen3 | schema_drift | 28 | 0 | 0 | 0 | 0 | 0 | 0 | 28 |
| synthetic | Qwen3 | runtime_fault | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| BFCL | Mistral v0.1 | baseline | 33 | 0 | 6 | 0 | 0 | 0 | 6 | 27 |
| BFCL | Mistral v0.1 | schema_drift | 44 | 0 | 3 | 6 | 0 | 0 | 9 | 35 |
| BFCL | Mistral v0.1 | runtime_fault | 33 | 0 | 6 | 0 | 0 | 0 | 6 | 27 |
| BFCL | Mistral v0.2 | baseline | 55 | 32 | 3 | 0 | 0 | 0 | 35 | 20 |
| BFCL | Mistral v0.2 | schema_drift | 76 | 30 | 3 | 6 | 0 | 0 | 39 | 37 |
| BFCL | Mistral v0.2 | runtime_fault | 55 | 34 | 3 | 0 | 0 | 0 | 37 | 18 |
| BFCL | Mistral v0.3 | baseline | 17 | 0 | 9 | 0 | 0 | 0 | 9 | 8 |
| BFCL | Mistral v0.3 | schema_drift | 33 | 0 | 5 | 6 | 0 | 0 | 11 | 22 |
| BFCL | Mistral v0.3 | runtime_fault | 18 | 0 | 9 | 0 | 0 | 0 | 9 | 9 |
| BFCL | Qwen2.5 | baseline | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 15 |
| BFCL | Qwen2.5 | schema_drift | 20 | 0 | 4 | 6 | 0 | 1 | 11 | 9 |
| BFCL | Qwen2.5 | runtime_fault | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 15 |
| BFCL | Qwen3 | baseline | 45 | 0 | 0 | 0 | 0 | 0 | 0 | 45 |
| BFCL | Qwen3 | schema_drift | 92 | 0 | 0 | 4 | 0 | 0 | 4 | 88 |
| BFCL | Qwen3 | runtime_fault | 52 | 0 | 0 | 0 | 0 | 0 | 0 | 52 |

### Per-model totals (all conditions, both suites pooled)

| model | intent_fail_n | properties_wrapper | string_bool | unit_number | unit_synonym | swapped_symmetric | explained_by_any | explained_by_none |
|---|---|---|---|---|---|---|---|---|
| Mistral v0.1 | 112 | 0 | 15 | 6 | 0 | 0 | 21 | 91 |
| Mistral v0.2 | 207 | 96 | 9 | 6 | 0 | 0 | 111 | 96 |
| Mistral v0.3 | 105 | 0 | 23 | 6 | 0 | 0 | 29 | 76 |
| Qwen2.5 | 69 | 0 | 4 | 6 | 1 | 1 | 12 | 57 |
| Qwen3 | 220 | 0 | 0 | 4 | 0 | 0 | 4 | 216 |

## Part 2: relaxed-intent (all 5 causes) score recompute -- upgrade decision flips

Full score recomputed with `args_intent_match` relaxed for all 5 causes at once (all other components -- parse_ok, tool_name_ok, args_valid_under_drift, executor_ok -- exactly as already scored). Gate threshold 0.05, same convention as `docs/protocol.md` and every other table in this audit.

| suite | decision | strict stress diff | relaxed-intent stress diff | strict label | relaxed label | flip? |
|---|---|---|---|---|---|---|
| synthetic | Mistral v0.1->Mistral v0.2 | -0.168 | -0.168 | harmful | harmful | no change |
| synthetic | Mistral v0.2->Mistral v0.3 | +0.123 | +0.123 | beneficial | beneficial | no change |
| synthetic | Mistral v0.1->Mistral v0.3 | -0.045 | -0.045 | neutral | neutral | no change |
| synthetic | Qwen2.5->Qwen3 | -0.042 | -0.042 | neutral | neutral | no change |
| BFCL | Mistral v0.1->Mistral v0.2 | -0.115 | -0.110 | harmful | harmful | no change |
| BFCL | Mistral v0.2->Mistral v0.3 | +0.187 | +0.180 | beneficial | beneficial | no change |
| BFCL | Mistral v0.1->Mistral v0.3 | +0.072 | +0.070 | beneficial | beneficial | no change |
| BFCL | Qwen2.5->Qwen3 | -0.230 | -0.235 | harmful | harmful | no change |

**0 decision(s) flip under relaxed intent.**
