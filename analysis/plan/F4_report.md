# F4 (generic-JSON constrained decoding) run report (2026-10-08)

All 16 models x 3 suites, 100 tasks each, baseline/schema_drift/fault_reporting, 1 greedy + 2 sampled trials. constrained_decoding: generic_json for every model; everything else unchanged from D. Only PLAN.md's generic_json level is run -- full_schema is cut (see DEVIATIONS.md). fault_reporting is NOT grammar-constrained under this protocol (its envelope shape differs from the generic_json schema), so its numbers reflect the same unconstrained behavior as D. Qwen3's grammar also structurally blocks its <think> block -- its results carry a separate label below. No verdicts, no comparison to D here -- record-keeping only, per instruction.

**Runs completed: 48/48**
**Total elapsed time: 20.2 hours**
**Errors: 0**

| Model | Suite | Records | Parse rate | Truncation rate | Greedy baseline acc | Seconds |
|---|---|---|---|---|---|---|
| gemma2_2b | synthetic | 900 | 1.000 | 0.000 | 0.940 | 3092 |
| gemma2_2b | bfcl_simple | 900 | 1.000 | 0.001 | 0.830 | 3657 |
| gemma2_2b | bfcl_multiple | 900 | 1.000 | 0.000 | 0.850 | 3527 |
| gemma3_4b | synthetic | 900 | 1.000 | 0.000 | 0.940 | 2115 |
| gemma3_4b | bfcl_simple | 900 | 1.000 | 0.004 | 0.910 | 1635 |
| gemma3_4b | bfcl_multiple | 900 | 1.000 | 0.001 | 0.960 | 1726 |
| phi3_mini | synthetic | 900 | 1.000 | 0.007 | 0.960 | 381 |
| phi3_mini | bfcl_simple | 900 | 1.000 | 0.000 | 0.930 | 516 |
| phi3_mini | bfcl_multiple | 900 | 1.000 | 0.000 | 0.920 | 606 |
| qwen2 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 1798 |
| qwen2 | bfcl_simple | 900 | 1.000 | 0.000 | 0.930 | 3576 |
| qwen2 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.980 | 3518 |
| llama31 | synthetic | 900 | 1.000 | 0.001 | 1.000 | 2225 |
| llama31 | bfcl_simple | 900 | 1.000 | 0.002 | 0.940 | 1989 |
| llama31 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 2925 |
| mistral_v01 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 572 |
| mistral_v01 | bfcl_simple | 900 | 1.000 | 0.003 | 0.880 | 751 |
| mistral_v01 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.910 | 967 |
| qwen25 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 908 |
| qwen25 | bfcl_simple | 900 | 1.000 | 0.000 | 0.960 | 1115 |
| qwen25 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 1189 |
| mistral_v03 | synthetic | 900 | 1.000 | 0.003 | 0.960 | 594 |
| mistral_v03 | bfcl_simple | 900 | 1.000 | 0.004 | 0.920 | 825 |
| mistral_v03 | bfcl_multiple | 900 | 1.000 | 0.001 | 0.960 | 824 |
| llama3 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 826 |
| llama3 | bfcl_simple | 900 | 1.000 | 0.001 | 0.890 | 1357 |
| llama3 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 1126 |
| granite32 | synthetic | 900 | 1.000 | 0.004 | 0.980 | 736 |
| granite32 | bfcl_simple | 900 | 1.000 | 0.002 | 0.970 | 1012 |
| granite32 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.990 | 1375 |
| granite31 | synthetic | 900 | 1.000 | 0.002 | 0.980 | 786 |
| granite31 | bfcl_simple | 900 | 1.000 | 0.002 | 0.960 | 1019 |
| granite31 | bfcl_multiple | 900 | 1.000 | 0.001 | 0.990 | 1045 |
| granite30 | synthetic | 900 | 1.000 | 0.001 | 1.000 | 917 |
| granite30 | bfcl_simple | 900 | 1.000 | 0.004 | 0.940 | 1662 |
| granite30 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 1777 |
| phi4_mini | synthetic | 900 | 1.000 | 0.000 | 1.000 | 1996 |
| phi4_mini | bfcl_simple | 900 | 1.000 | 0.001 | 0.940 | 1172 |
| phi4_mini | bfcl_multiple | 900 | 1.000 | 0.003 | 0.950 | 1200 |
| mistral_v02 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 713 |
| mistral_v02 | bfcl_simple | 900 | 1.000 | 0.006 | 0.790 | 1147 |
| mistral_v02 | bfcl_multiple | 900 | 1.000 | 0.001 | 0.800 | 1271 |
| phi35_mini | synthetic | 900 | 1.000 | 0.024 | 1.000 | 781 |
| phi35_mini | bfcl_simple | 900 | 1.000 | 0.054 | 0.960 | 784 |
| phi35_mini | bfcl_multiple | 900 | 1.000 | 0.053 | 0.950 | 902 |
| qwen3 [grammar + thinking blocked] | synthetic | 900 | 0.848 | 0.094 | 0.930 | 2154 |
| qwen3 [grammar + thinking blocked] | bfcl_simple | 900 | 0.972 | 0.183 | 0.940 | 2852 |
| qwen3 [grammar + thinking blocked] | bfcl_multiple | 900 | 0.957 | 0.173 | 0.900 | 3051 |

## Qwen3-only repetition loop, found at full scale

The quick test (5 tasks/suite) found 0/270 truncated `baseline`/
`schema_drift` records and concluded the grammar does not cause
endless whitespace or looping -- true at that sample size, but
incomplete. At full scale, **Qwen3 shows a real repetition loop in
47/1800 (2.6%) of its `baseline`/`schema_drift` records** (6/600
synthetic, 16/600 bfcl_simple, 25/600 bfcl_multiple): it gets stuck
repeating the same key-value pair inside the open-ended `"arguments"`
object until `max_tokens` cuts it off, e.g. `..."crime_type_v2": "theft
crimes", "crime_type_v2": "theft crimes", ...`. This explains why
Qwen3's parse rate (0.848-0.972) and truncation rate (0.094-0.183) in
the table above are not near-1.000/near-0.000 like every other model's.
Scanned all 15 other models' baseline/schema_drift records (27,000
total) for the same pattern: **zero occurrences** -- this is a
Qwen3-only effect, tied to the same `<think>`-block suppression logged
separately below, not a general risk of the `generic_json` grammar.
Not fixed (see DEVIATIONS.md, 2026-10-09).

## Qwen3: grammar also blocks thinking (separate label)

Confirmed directly before running: the `generic_json` grammar forces
the first emitted token to be `{`, so Qwen3's `<think>` block is never
emitted at all (not truncated/malformed -- absent). Decided to run
Qwen3 under the same plain grammar as every other model rather than
build a custom think-aware grammar for just one model (see
DEVIATIONS.md, 2026-10-08, for the full decision). **For every other
model, F4 changes exactly one thing from D** (constrained decoding).
**For Qwen3, F4 changes two things**: the grammar itself, and (as a
structural side effect) thinking gets blocked -- labeled `[grammar +
thinking blocked]` in the table above, reported separately from the
other 15 models, and intended to be compared against F2 (thinking off
only) to help separate the two effects. Protocol R will have the same
Qwen3 effect for the same reason (also generic-JSON), logged in
advance.

## Qwen3: all 3 suites pre-split ahead of time

Per the same convention as F6 (not a reactive risk decision): all 3
Qwen3 suites ran via `scripts/split_run.py` (50-task halves, merged).

## run_manifest.json diff vs. D (all 48 runs)

Compared every field under `run_factors` and `model_backend` for all 48
model/suite pairs directly. **Exactly one difference, identical across
every single run:**

```
run_factors.F4_constrained_decoding:  D = 'off'   F4 = 'generic_json'
```

No other field differs on any of the 48 runs.