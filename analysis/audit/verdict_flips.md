# Verdict flips found across this audit

One row per (harness choice x upgrade pair x suite). "before"/"after" are the gate label (harmful/neutral/beneficial, threshold 0.05) under the unfixed vs fixed harness choice. **APPLIED** rows reflect changes already baked into the project's official numbers (BFCL drift-prompt fix, historical) or into new runs produced this session (Qwen3 thinking-mode fix). **CANDIDATE** rows are diagnostics only (escape-repair, fault-rescore) -- strict, mixed-attempt scoring remains the project's official metric for every published number; these rows show what *would* change if either candidate fix were adopted.

| # | harness choice | pair | suite | verdict before | verdict after | flip? | stress diff before -> after |
|---|---|---|---|---|---|---|---|
| 1 | BFCL drift-prompt-transmission fix (applied, historical) | Mistral v0.1->Mistral v0.2 | BFCL | harmful | harmful | no change | -0.097 -> -0.115 |
| 2 | BFCL drift-prompt-transmission fix (applied, historical) | Mistral v0.2->Mistral v0.3 | BFCL | beneficial | beneficial | no change | +0.133 -> +0.187 |
| 3 | BFCL drift-prompt-transmission fix (applied, historical) | Mistral v0.1->Mistral v0.3 | BFCL | neutral | beneficial | **FLIP** | +0.037 -> +0.072 |
| 4 | BFCL drift-prompt-transmission fix (applied, historical) | Qwen2.5->Qwen3 | BFCL | harmful | harmful | no change | -0.125 -> -0.230 |
| 5 | Qwen3 thinking-mode fix: nothink (primary) (applied, this session) | Qwen2.5->Qwen3 | synthetic | neutral | neutral | no change | -0.042 -> +0.032 |
| 6 | Qwen3 thinking-mode fix: think_long (secondary) (applied, this session) | Qwen2.5->Qwen3 | synthetic | neutral | neutral | no change | -0.042 -> +0.032 |
| 7 | Qwen3 thinking-mode fix: nothink (primary) (applied, this session) | Qwen2.5->Qwen3 | BFCL | harmful | neutral | **FLIP** | -0.230 -> +0.015 |
| 8 | Qwen3 thinking-mode fix: think_long (secondary) (applied, this session) | Qwen2.5->Qwen3 | BFCL | harmful | neutral | **FLIP** | -0.230 -> -0.002 |
| 9 | Escape-repair (lenient) parsing fix -- CANDIDATE, not applied | Mistral v0.1->Mistral v0.2 | synthetic | harmful | neutral | **FLIP** | -0.168 -> -0.050 |
| 10 | Escape-repair (lenient) parsing fix -- CANDIDATE, not applied | Mistral v0.2->Mistral v0.3 | synthetic | beneficial | neutral | **FLIP** | +0.123 -> +0.005 |
| 11 | Escape-repair (lenient) parsing fix -- CANDIDATE, not applied | Mistral v0.1->Mistral v0.3 | synthetic | neutral | neutral | no change | -0.045 -> -0.045 |
| 12 | Escape-repair (lenient) parsing fix -- CANDIDATE, not applied | Qwen2.5->Qwen3 | synthetic | neutral | neutral | no change | -0.042 -> -0.042 |
| 13 | Escape-repair (lenient) parsing fix -- CANDIDATE, not applied | Mistral v0.1->Mistral v0.2 | BFCL | harmful | harmful | no change | -0.115 -> -0.080 |
| 14 | Escape-repair (lenient) parsing fix -- CANDIDATE, not applied | Mistral v0.2->Mistral v0.3 | BFCL | beneficial | beneficial | no change | +0.187 -> +0.145 |
| 15 | Escape-repair (lenient) parsing fix -- CANDIDATE, not applied | Mistral v0.1->Mistral v0.3 | BFCL | beneficial | beneficial | no change | +0.072 -> +0.065 |
| 16 | Escape-repair (lenient) parsing fix -- CANDIDATE, not applied | Qwen2.5->Qwen3 | BFCL | harmful | harmful | no change | -0.230 -> -0.230 |
| 17 | Fault rescore (final-attempt-consistent) fix -- CANDIDATE, not applied | Mistral v0.1->Mistral v0.2 | synthetic | harmful | harmful | no change | -0.168 -> -0.173 |
| 18 | Fault rescore (final-attempt-consistent) fix -- CANDIDATE, not applied | Mistral v0.2->Mistral v0.3 | synthetic | beneficial | beneficial | no change | +0.123 -> +0.148 |
| 19 | Fault rescore (final-attempt-consistent) fix -- CANDIDATE, not applied | Mistral v0.1->Mistral v0.3 | synthetic | neutral | neutral | no change | -0.045 -> -0.025 |
| 20 | Fault rescore (final-attempt-consistent) fix -- CANDIDATE, not applied | Qwen2.5->Qwen3 | synthetic | neutral | neutral | no change | -0.042 -> -0.040 |
| 21 | Fault rescore (final-attempt-consistent) fix -- CANDIDATE, not applied | Mistral v0.1->Mistral v0.2 | BFCL | harmful | harmful | no change | -0.115 -> -0.103 |
| 22 | Fault rescore (final-attempt-consistent) fix -- CANDIDATE, not applied | Mistral v0.2->Mistral v0.3 | BFCL | beneficial | beneficial | no change | +0.187 -> +0.157 |
| 23 | Fault rescore (final-attempt-consistent) fix -- CANDIDATE, not applied | Mistral v0.1->Mistral v0.3 | BFCL | beneficial | beneficial | no change | +0.072 -> +0.053 |
| 24 | Fault rescore (final-attempt-consistent) fix -- CANDIDATE, not applied | Qwen2.5->Qwen3 | BFCL | harmful | harmful | no change | -0.230 -> -0.205 |

**5 of 24 rows are label flips.**


## Reading this table

- Rows 1-4 (BFCL drift-prompt fix): only the Mistral v0.1->v0.3 BFCL decision flips label (neutral -> beneficial); the other three BFCL pairs keep the same label through this fix (their magnitudes still move a lot -- see AUDIT.md H17 -- just not across a gate boundary).
- Rows 5-8 (Qwen3 thinking-mode fix, nothink + think_long x 2 suites): BFCL flips from harmful to neutral under both corrected configs; synthetic stays labeled neutral both before and after, but the point estimate crosses zero (sign reversal without a label flip) -- flagged as "no change" here since the 0.05 gate itself doesn't move, but see `qwen3_rerun.md` / `decisions_corrected.md` for the magnitude story.
- Rows 9-16 (escape-repair candidate): check whether these rows flip before treating any of them as settled -- the escape bug was concentrated in Mistral v0.1/v0.2 `runtime_fault` (see `escape_check.md`), so the Mistral v0.1->v0.2 rows are where a flip is most plausible a priori.
- **Row 9 is exactly on the gate boundary, not comfortably past it**: the lenient stress diff is `-30/600 = -0.050000` to full precision -- an exact tie with the `-0.05` threshold, not a rounding artifact. The gate rule (`scripts/analyze_release_gate.py:gate_label`, `d < -GATE_THRESHOLD`) uses a strict inequality, so exactly `-0.05` is labeled "neutral" by one ULP's worth of margin. This is the headline, published H1 illustrative example ("v0.1->v0.2 significantly regressed") sitting on a coin-flip: a single additional record going either way would move it back to "harmful" or further into "neutral". Read this as "the escape bug alone is enough to erase this decision's safety margin entirely," not as "this decision is now robustly neutral."
- Rows 17-24 (fault-rescore candidate): checks whether final-attempt-consistent scoring (vs. the current mixed first-attempt-metrics/retry-exec_ok scoring, see AUDIT.md E10) moves any decision across the gate boundary on its own.
