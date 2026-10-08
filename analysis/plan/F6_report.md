# F6 (sampling preset) run report (2026-10-07)

All 16 models x 3 suites, 100 tasks each, baseline/schema_drift/fault_reporting, 1 greedy + 2 sampled trials. Each model's sampled trials use its own recommended top_p/top_k/min_p/repeat_penalty (see DEVIATIONS.md for the table and source); the greedy trial always uses D's own sampling defaults, unchanged. No verdicts, no comparison to D here -- record-keeping only, per instruction.

**Runs completed: 48/48**
**Total elapsed time: 11.4 hours**
**Errors: 0**

| Model | Suite | Records | Parse rate | Truncation rate | Greedy baseline acc | Seconds |
|---|---|---|---|---|---|---|
| gemma2_2b | synthetic | 900 | 1.000 | 0.000 | 0.940 | 233 |
| gemma2_2b | bfcl_simple | 900 | 0.980 | 0.001 | 0.820 | 363 |
| gemma2_2b | bfcl_multiple | 900 | 0.978 | 0.000 | 0.850 | 395 |
| gemma3_4b | synthetic | 900 | 1.000 | 0.000 | 0.940 | 413 |
| gemma3_4b | bfcl_simple | 900 | 1.000 | 0.006 | 0.910 | 537 |
| gemma3_4b | bfcl_multiple | 900 | 0.997 | 0.001 | 0.960 | 573 |
| phi3_mini | synthetic | 900 | 1.000 | 0.007 | 0.960 | 345 |
| phi3_mini | bfcl_simple | 900 | 1.000 | 0.000 | 0.930 | 431 |
| phi3_mini | bfcl_multiple | 900 | 0.995 | 0.000 | 0.920 | 525 |
| qwen2 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 487 |
| qwen2 | bfcl_simple | 900 | 1.000 | 0.000 | 0.930 | 644 |
| qwen2 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.980 | 646 |
| llama31 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 488 |
| llama31 | bfcl_simple | 900 | 1.000 | 0.000 | 0.940 | 623 |
| llama31 | bfcl_multiple | 900 | 1.000 | 0.001 | 0.940 | 651 |
| mistral_v01 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 550 |
| mistral_v01 | bfcl_simple | 900 | 0.970 | 0.003 | 0.900 | 722 |
| mistral_v01 | bfcl_multiple | 900 | 0.985 | 0.000 | 0.900 | 781 |
| qwen25 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 465 |
| qwen25 | bfcl_simple | 900 | 1.000 | 0.001 | 0.960 | 605 |
| qwen25 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 625 |
| mistral_v03 | synthetic | 900 | 1.000 | 0.003 | 0.970 | 520 |
| mistral_v03 | bfcl_simple | 900 | 1.000 | 0.004 | 0.920 | 711 |
| mistral_v03 | bfcl_multiple | 900 | 0.997 | 0.001 | 0.950 | 713 |
| llama3 | synthetic | 900 | 0.967 | 0.000 | 1.000 | 548 |
| llama3 | bfcl_simple | 900 | 0.988 | 0.003 | 0.890 | 671 |
| llama3 | bfcl_multiple | 900 | 0.972 | 0.000 | 0.940 | 674 |
| granite32 | synthetic | 900 | 1.000 | 0.004 | 0.980 | 596 |
| granite32 | bfcl_simple | 900 | 1.000 | 0.002 | 0.970 | 811 |
| granite32 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.990 | 822 |
| granite31 | synthetic | 900 | 1.000 | 0.002 | 0.980 | 598 |
| granite31 | bfcl_simple | 900 | 1.000 | 0.002 | 0.960 | 833 |
| granite31 | bfcl_multiple | 900 | 1.000 | 0.001 | 0.990 | 850 |
| granite30 | synthetic | 900 | 1.000 | 0.001 | 1.000 | 605 |
| granite30 | bfcl_simple | 900 | 1.000 | 0.004 | 0.940 | 811 |
| granite30 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.920 | 887 |
| phi4_mini | synthetic | 900 | 1.000 | 0.000 | 1.000 | 343 |
| phi4_mini | bfcl_simple | 900 | 1.000 | 0.001 | 0.910 | 465 |
| phi4_mini | bfcl_multiple | 900 | 1.000 | 0.003 | 0.930 | 493 |
| mistral_v02 | synthetic | 900 | 0.973 | 0.000 | 0.960 | 624 |
| mistral_v02 | bfcl_simple | 900 | 0.947 | 0.006 | 0.740 | 781 |
| mistral_v02 | bfcl_multiple | 900 | 0.905 | 0.001 | 0.780 | 820 |
| phi35_mini | synthetic | 900 | 1.000 | 0.024 | 1.000 | 461 |
| phi35_mini | bfcl_simple | 900 | 1.000 | 0.056 | 0.960 | 736 |
| phi35_mini | bfcl_multiple | 900 | 1.000 | 0.062 | 0.960 | 878 |
| qwen3 | synthetic | 900 | 0.943 | 0.124 | 0.990 | 3858 |
| qwen3 | bfcl_simple | 900 | 0.688 | 0.389 | 0.770 | 4823 |
| qwen3 | bfcl_multiple | 900 | 0.413 | 0.550 | 0.500 | 5064 |

## Per-model recommended sampling values

qwen2, qwen25, llama3, llama31, gemma3_4b, and qwen3 (thinking-on values,
since thinking stays on under F6) have an official recommendation and use
it for the 2 sampled trials. The other 10 models (gemma2_2b, phi3_mini,
mistral_v01/v02/v03, granite30/31/32, phi4_mini, phi35_mini) have no
official recommendation and keep D's own sampling values unchanged, per
instruction. Full table with sources and the greedy-isolation mechanism:
`DEVIATIONS.md`, 2026-10-07.

## Qwen3: all 3 suites pre-split ahead of time

Per explicit instruction (not a reactive risk decision this time): all 3
Qwen3 suites ran via `scripts/split_run.py` (50-task halves, merged).
D's own unsplit Qwen3 timings (synthetic 3845s, bfcl_simple 4865s,
bfcl_multiple 5058s, all comfortably under the 2-hour ceiling) gave no
reason to expect F6 to need splitting -- F6 changes neither max_tokens
nor prompt_format, the two factors that drove F1/F3's Qwen3 slowdowns.
Logged in `DEVIATIONS.md`.

## Greedy-record check vs. D

Compared every trial-0 (`temperature=0.0`) `raw_output` against D's
matching record (by task_id + condition) for all 48 model/suite pairs
(14,400 greedy records total). **1/14,400 mismatches**
(`qwen3/bfcl_simple`, task `bfcl-simple_python_279`, `schema_drift`
condition): both D's and F6's completions are byte-identical for the
first ~85% of the (truncated) `<think>` block, then diverge into two
different continuations, both still truncated at the same 256-token
budget. Same prompt (identical `prompt_sha256`), same temperature
(0.0) and seed (1234) in both. This is consistent with this project's
own documented caveat (`README.md`: "llama.cpp seeding is best-effort
on GPU, so ... may not be perfectly reproducible") -- a token-level
near-tie in the logits can flip under GPU floating-point
non-associativity even at temperature 0, and the divergence then
cascades through the rest of the generation. Not caused by F6's
per-trial sampling mechanism (the greedy trial's `top_p`/`top_k`/
`min_p`/`repeat_penalty` are explicitly pinned to D's own values here,
confirmed via the config and via 0 mismatches on the other 14,399
records) and not a parser or harness issue -- a pre-existing,
documented GPU-determinism limitation, observed here for the first
time simply because this is the largest side-by-side greedy comparison
run in this project to date.

## run_manifest.json diff vs. D (all 48 runs)

Compared every field under `run_factors` and `model_backend` for all 48
model/suite pairs directly (including `gemma2_2b`, a no-recommendation
model, as a negative control). **Exactly one difference, identical
across every single run:**

```
run_factors.F6_sampling_preset:  D = 'shared'   F6 = 'recommended'
```

No other field differs on any of the 48 runs -- including for the 10
models with no official recommendation, where `run_factors.
F6_sampling_preset` still reads `'recommended'` (the protocol's own
declared intent) even though every actual sampling value is identical
to D's.