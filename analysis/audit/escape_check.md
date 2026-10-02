# Escape-check: strict vs lenient (invalid-escape-repaired) scoring

Read-only diagnostic. `lenient` retries JSON extraction after repairing invalid backslash-escapes (e.g. `\_` -> `_`) via the new `extract_tool_call(..., lenient=True)` mode in `upgradecanary/parsing.py` (default `lenient=False` everywhere in production; this file never changes an existing score). The repair can only make an unparseable string parseable, never the reverse, so every strict->lenient score flip (always 0->1) is caused *solely* by an invalid-escape fix.

## Headline number (Q1)

Of the **71** `executor_failure`-bucket records in Mistral v0.2 synthetic `runtime_fault` (first attempt intent-matched and schema-valid, but final `executor_ok=False`), **71** flip to a passing score under lenient (escape-repaired) retry parsing -- i.e. **71/71** fail *only* because of an invalid JSON escape in the retry output (100.0%).

## Strict vs lenient score, every model x suite x condition

| suite | model | condition | n | strict mean | lenient mean | records flipped 0->1 |
|---|---|---|---|---|---|---|
| synthetic | Mistral v0.1 | baseline | 300 | 1.000 | 1.000 | 0 |
| synthetic | Mistral v0.1 | schema_drift | 300 | 0.990 | 0.990 | 0 |
| synthetic | Mistral v0.1 | runtime_fault | 300 | 1.000 | 1.000 | 0 |
| synthetic | Mistral v0.2 | baseline | 300 | 1.000 | 1.000 | 0 |
| synthetic | Mistral v0.2 | schema_drift | 300 | 0.897 | 0.897 | 0 |
| synthetic | Mistral v0.2 | runtime_fault | 300 | 0.757 | 0.993 | 71 |
| synthetic | Mistral v0.3 | baseline | 300 | 0.970 | 0.970 | 0 |
| synthetic | Mistral v0.3 | schema_drift | 300 | 0.930 | 0.930 | 0 |
| synthetic | Mistral v0.3 | runtime_fault | 300 | 0.970 | 0.970 | 0 |
| synthetic | Qwen2.5 | baseline | 300 | 1.000 | 1.000 | 0 |
| synthetic | Qwen2.5 | schema_drift | 300 | 0.937 | 0.937 | 0 |
| synthetic | Qwen2.5 | runtime_fault | 300 | 1.000 | 1.000 | 0 |
| synthetic | Qwen3 | baseline | 300 | 0.997 | 0.997 | 0 |
| synthetic | Qwen3 | schema_drift | 300 | 0.907 | 0.907 | 0 |
| synthetic | Qwen3 | runtime_fault | 300 | 0.947 | 0.947 | 0 |
| BFCL | Mistral v0.1 | baseline | 300 | 0.890 | 0.900 | 3 |
| BFCL | Mistral v0.1 | schema_drift | 300 | 0.690 | 0.697 | 2 |
| BFCL | Mistral v0.1 | runtime_fault | 300 | 0.883 | 0.890 | 2 |
| BFCL | Mistral v0.2 | baseline | 300 | 0.807 | 0.827 | 6 |
| BFCL | Mistral v0.2 | schema_drift | 300 | 0.623 | 0.643 | 6 |
| BFCL | Mistral v0.2 | runtime_fault | 300 | 0.720 | 0.783 | 19 |
| BFCL | Mistral v0.3 | baseline | 300 | 0.943 | 0.943 | 0 |
| BFCL | Mistral v0.3 | schema_drift | 300 | 0.777 | 0.777 | 0 |
| BFCL | Mistral v0.3 | runtime_fault | 300 | 0.940 | 0.940 | 0 |
| BFCL | Qwen2.5 | baseline | 300 | 0.950 | 0.950 | 0 |
| BFCL | Qwen2.5 | schema_drift | 300 | 0.923 | 0.923 | 0 |
| BFCL | Qwen2.5 | runtime_fault | 300 | 0.950 | 0.950 | 0 |
| BFCL | Qwen3 | baseline | 300 | 0.850 | 0.850 | 0 |
| BFCL | Qwen3 | schema_drift | 300 | 0.693 | 0.693 | 0 |
| BFCL | Qwen3 | runtime_fault | 300 | 0.720 | 0.720 | 0 |

## Total escape-only flips per model (all conditions pooled)

| suite | model | total records flipped 0->1 by escape repair |
|---|---|---|
| synthetic | Mistral v0.1 | 0 |
| synthetic | Mistral v0.2 | 71 |
| synthetic | Mistral v0.3 | 0 |
| synthetic | Qwen2.5 | 0 |
| synthetic | Qwen3 | 0 |
| BFCL | Mistral v0.1 | 7 |
| BFCL | Mistral v0.2 | 31 |
| BFCL | Mistral v0.3 | 0 |
| BFCL | Qwen2.5 | 0 |
| BFCL | Qwen3 | 0 |

## Interpretation

Strict scoring remains the project's official metric; nothing above changes any published number. This table exists to size the 'spurious backslash escape' failure mode identified in `AUDIT.md` section E13 (Mistral v0.2 retry outputs like `get\_weather`). Where the flip count for a model/condition is non-trivial, it suggests a fraction of that model's measured 'failures' are a retry-prompt-induced formatting quirk rather than a semantic or robustness failure -- the same caution AUDIT.md already raises for Qwen3's thinking-mode truncation, but via a different mechanism.
