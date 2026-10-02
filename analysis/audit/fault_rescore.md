# Fault rescore: first-try vs final-attempt-consistent scoring

Read-only, recomputed from existing logs (no reruns). See `upgradecanary/parsing.py`/`analysis/audit/common.py` (`recompute_record`, parity-checked against stored scores in `_parity_check.py`: 0 mismatches across all 9,000 records x 10 runs).

**Terminology note (per AUDIT.md E11):** this file reports the `timeout`/`tool_exception`/`empty_result`/`partial_result` fault types under the label **retry_after_tool_failure**, since what is actually measured is "does a second generation, prompted with the first failure's error message, produce a correct call" -- not fault *detection* or *handling* in any deeper sense. `stale_result` is reported separately: `apply_fault` always returns `ok: True` for it, so it cannot fail by construction and is excluded from the main aggregate below.

## Per model x suite: first-try vs final-attempt score, recovered / broken_by_retry

| suite | model | n (excl. stale) | first_try mean | final mean (fixed, consistent) | final mean (original/mixed) | recovered | broken_by_retry |
|---|---|---|---|---|---|---|---|
| synthetic | Mistral v0.1 | 225 | 0.000 | 0.987 | 1.000 | 222 | 0 |
| synthetic | Mistral v0.2 | 225 | 0.000 | 0.658 | 0.684 | 148 | 0 |
| synthetic | Mistral v0.3 | 225 | 0.000 | 1.000 | 0.960 | 225 | 0 |
| synthetic | Qwen2.5 | 225 | 0.000 | 1.000 | 1.000 | 225 | 0 |
| synthetic | Qwen3 | 225 | 0.000 | 0.938 | 0.933 | 211 | 0 |
| BFCL | Mistral v0.1 | 231 | 0.000 | 0.905 | 0.879 | 209 | 0 |
| BFCL | Mistral v0.2 | 231 | 0.000 | 0.758 | 0.701 | 175 | 0 |
| BFCL | Mistral v0.3 | 231 | 0.000 | 0.926 | 0.948 | 214 | 0 |
| BFCL | Qwen2.5 | 231 | 0.000 | 0.957 | 0.952 | 221 | 0 |
| BFCL | Qwen3 | 231 | 0.000 | 0.788 | 0.719 | 182 | 0 |

## stale_result, reported separately (cannot fail by construction)

| suite | model | n | first_try mean | final mean | recovered | broken_by_retry |
|---|---|---|---|---|---|---|
| synthetic | Mistral v0.1 | 75 | 1.000 | 1.000 | 0 | 0 |
| synthetic | Mistral v0.2 | 75 | 0.973 | 0.973 | 0 | 0 |
| synthetic | Mistral v0.3 | 75 | 1.000 | 1.000 | 0 | 0 |
| synthetic | Qwen2.5 | 75 | 1.000 | 1.000 | 0 | 0 |
| synthetic | Qwen3 | 75 | 0.987 | 0.987 | 0 | 0 |
| BFCL | Mistral v0.1 | 69 | 0.899 | 0.899 | 0 | 0 |
| BFCL | Mistral v0.2 | 69 | 0.783 | 0.783 | 0 | 0 |
| BFCL | Mistral v0.3 | 69 | 0.913 | 0.913 | 0 | 0 |
| BFCL | Qwen2.5 | 69 | 0.942 | 0.942 | 0 | 0 |
| BFCL | Qwen3 | 69 | 0.725 | 0.725 | 0 | 0 |

## Reading this table

- **first_try mean**: score if the retry never happened (fault-forced first-attempt failure counts as a real failure). This is the closest thing to "did the model's own call survive contact with the fault" for the four retryable types, and it is near-zero for all of them by construction (apply_fault always fails the first attempt when the original call was otherwise correct).
- **final mean (fixed, consistent)**: all five components recomputed on the actual final attempt (the retry's own parsed call + exec, when a retry happened) -- the corrected scoring this follow-up asked for.
- **final mean (original/mixed)**: the number currently published (docs/results_summary.md), included for comparison -- computed with four of five metrics taken from the first attempt and only `executor_ok` from the retry (see AUDIT.md E10).
- A difference between the 'fixed' and 'mixed' columns means the retry's OWN parsed call differs from the first attempt's in a way that matters for `tool_name_ok`/`args_intent_match`/`args_valid_under_drift` (not just `executor_ok`) -- e.g. a retry that changes its mind about an argument, or one broken by an escape artifact (see escape_check.md), which the mixed scoring would not have caught since it only looks at the retry's final `ok` flag, not its restated arguments.
- **stale_result** mean scores track each model's own baseline-level correctness almost exactly, confirming it carries no fault-specific signal (AUDIT.md E11) and should not be pooled into a 'robustness under faults' claim.
