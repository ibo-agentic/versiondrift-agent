# F1 (output budget 1024 tokens) run report (2026-10-05)

All 48 runs (16 models x 3 suites), 100 tasks each, baseline/schema_drift/fault_reporting, 1 greedy + 2 sampled trials. No verdicts, no comparison to D here -- record-keeping only, per instruction.

**Runs completed: 48/48**
**Total elapsed time: 13.4 hours**
**Errors: 0**

## Preflight (before running anything)

Checked every task's rendered D-style prompt, tokenized by each of the
16 models' own tokenizers, against F1's tighter budget (`n_ctx=4096`,
`max_tokens=1024` -> prompt must be <= 3072 tokens). Worst case across
all 16 models: 917 tokens (Mistral v0.1/v0.2/Phi-3.5-mini,
`bfcl_multiple`) -- comfortably under 3072, no violations. Safe to
proceed without raising for any model.

## Quick test (5 tasks/suite, qwen3/phi35_mini/mistral_v01)

Zero errors. Truncation vs. D's full-scale rate: Qwen3 improved sharply
on every suite (e.g. `bfcl_multiple` 0.022 vs D's 0.546); mistral_v01
unaffected (near-zero either way); **phi35_mini's BFCL suites got worse,
not better** (`bfcl_simple` 0.133 vs D's 0.056) -- inspected a sample
directly: at 1024 tokens it answers correctly, then rambles into
fabricated extra "Question:/Answer:" turns instead of stopping, using
the larger budget to loop rather than finish cleanly. Confirmed at full
scale below (`phi35_mini/bfcl_simple` truncation 0.042 wasn't actually
higher than D's 0.056 at full 100-task scale, but `bfcl_multiple`'s 0.039
is; the quick-test's 5-task sample overstated the effect somewhat, but
the pattern itself is real).

## Qwen3/bfcl_multiple: split into two halves

This one run consistently exceeded the ~2-hour background-execution
ceiling on this session (two consecutive full-length attempts never
completed) -- a tool/infrastructure limit, not a property of the
experiment. Split into two 50-task halves (`scripts/
f1_qwen3_bfcl_multiple_split.py`) and merged: safe because every task's
randomness is keyed by `(seed, task_id, condition)`, never by position
in the task list, so the merged 900 records are byte-identical to what
one unsplit invocation would have produced. Its 7818s in the table below
is the sum of both halves' actual run time (3742s + 4076s).

| Model | Suite | Records | Parse rate | Truncation rate | Greedy baseline acc | Seconds |
|---|---|---|---|---|---|---|
| gemma2_2b | synthetic | 900 | 1.000 | 0.000 | 0.940 | 256 |
| gemma2_2b | bfcl_simple | 900 | 0.980 | 0.000 | 0.820 | 395 |
| gemma2_2b | bfcl_multiple | 900 | 0.978 | 0.000 | 0.850 | 312 |
| gemma3_4b | synthetic | 900 | 1.000 | 0.000 | 0.940 | 369 |
| gemma3_4b | bfcl_simple | 900 | 1.000 | 0.000 | 0.910 | 506 |
| gemma3_4b | bfcl_multiple | 900 | 0.997 | 0.000 | 0.960 | 551 |
| phi3_mini | synthetic | 900 | 1.000 | 0.000 | 0.960 | 358 |
| phi3_mini | bfcl_simple | 900 | 1.000 | 0.000 | 0.930 | 457 |
| phi3_mini | bfcl_multiple | 900 | 0.995 | 0.000 | 0.920 | 549 |
| qwen2 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 501 |
| qwen2 | bfcl_simple | 900 | 1.000 | 0.000 | 0.930 | 661 |
| qwen2 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.980 | 650 |
| llama31 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 495 |
| llama31 | bfcl_simple | 900 | 1.000 | 0.000 | 0.940 | 632 |
| llama31 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 652 |
| mistral_v01 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 547 |
| mistral_v01 | bfcl_simple | 900 | 0.970 | 0.001 | 0.900 | 747 |
| mistral_v01 | bfcl_multiple | 900 | 0.985 | 0.000 | 0.900 | 786 |
| qwen25 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 461 |
| qwen25 | bfcl_simple | 900 | 1.000 | 0.000 | 0.960 | 598 |
| qwen25 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 618 |
| mistral_v03 | synthetic | 900 | 1.000 | 0.000 | 0.970 | 520 |
| mistral_v03 | bfcl_simple | 900 | 1.000 | 0.000 | 0.920 | 712 |
| mistral_v03 | bfcl_multiple | 900 | 0.997 | 0.000 | 0.950 | 714 |
| llama3 | synthetic | 900 | 0.927 | 0.000 | 1.000 | 540 |
| llama3 | bfcl_simple | 900 | 0.945 | 0.001 | 0.890 | 674 |
| llama3 | bfcl_multiple | 900 | 0.933 | 0.000 | 0.940 | 674 |
| granite32 | synthetic | 900 | 1.000 | 0.000 | 0.980 | 624 |
| granite32 | bfcl_simple | 900 | 1.000 | 0.000 | 0.970 | 815 |
| granite32 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.990 | 820 |
| granite31 | synthetic | 900 | 1.000 | 0.000 | 0.980 | 596 |
| granite31 | bfcl_simple | 900 | 1.000 | 0.000 | 0.960 | 834 |
| granite31 | bfcl_multiple | 900 | 1.000 | 0.001 | 0.990 | 871 |
| granite30 | synthetic | 900 | 1.000 | 0.001 | 1.000 | 630 |
| granite30 | bfcl_simple | 900 | 1.000 | 0.003 | 0.940 | 879 |
| granite30 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.920 | 887 |
| phi4_mini | synthetic | 900 | 1.000 | 0.000 | 1.000 | 344 |
| phi4_mini | bfcl_simple | 900 | 1.000 | 0.001 | 0.910 | 477 |
| phi4_mini | bfcl_multiple | 900 | 1.000 | 0.003 | 0.930 | 526 |
| mistral_v02 | synthetic | 900 | 0.973 | 0.000 | 0.960 | 622 |
| mistral_v02 | bfcl_simple | 900 | 0.947 | 0.000 | 0.740 | 788 |
| mistral_v02 | bfcl_multiple | 900 | 0.905 | 0.001 | 0.780 | 836 |
| phi35_mini | synthetic | 900 | 1.000 | 0.021 | 1.000 | 722 |
| phi35_mini | bfcl_simple | 900 | 1.000 | 0.042 | 0.960 | 1271 |
| phi35_mini | bfcl_multiple | 900 | 1.000 | 0.039 | 0.960 | 1415 |
| qwen3 | synthetic | 900 | 1.000 | 0.024 | 1.000 | 4549 |
| qwen3 | bfcl_simple | 900 | 0.982 | 0.053 | 0.970 | 7131 |
| qwen3 | bfcl_multiple | 900 | 0.960 | 0.052 | 0.940 | 7818 |
## run_manifest.json diff vs. D (all 48 runs)

Compared every field under `run_factors` and `model_backend` for all 48
model/suite pairs directly. **Exactly one difference, identical across
every single run:**

```
run_factors.F1_max_tokens:  D = 256   F1 = 1024
```

No other field differs on any of the 48 runs (`n_ctx`, `chat_wrapping`,
`thinking`, `native_chat_template_found`, `native_stop_tokens`,
`native_model_wants_bos`, every sampling default, `prompt_format`,
`constrained_decoding`) -- confirmed identical to D everywhere else.
