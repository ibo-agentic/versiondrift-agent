# R (robust protocol) run report (2026-10-09)

All 16 models x 3 suites, 100 tasks each, baseline/schema_drift/fault_reporting, 1 greedy + 2 sampled trials. R = D + max_tokens=1024 + constrained_decoding: generic_json (PLAN.md section 7 items 1-2); everything else unchanged from D. fault_reporting is NOT grammar-constrained (its envelope shape differs from the generic_json schema). Qwen3's grammar also structurally blocks its <think> block -- its results carry a separate label below. No verdicts, no comparison to D here -- record-keeping only, per instruction.

**Runs completed: 48/48**
**Total elapsed time: 21.1 hours**
**Errors: 0**

| Model | Suite | Records | Parse rate | Truncation rate | Greedy baseline acc | Seconds |
|---|---|---|---|---|---|---|
| gemma2_2b | synthetic | 900 | 1.000 | 0.000 | 0.940 | 1171 |
| gemma2_2b | bfcl_simple | 900 | 1.000 | 0.000 | 0.830 | 1653 |
| gemma2_2b | bfcl_multiple | 900 | 1.000 | 0.000 | 0.850 | 1727 |
| gemma3_4b | synthetic | 900 | 1.000 | 0.000 | 0.940 | 1298 |
| gemma3_4b | bfcl_simple | 900 | 1.000 | 0.000 | 0.910 | 1820 |
| gemma3_4b | bfcl_multiple | 900 | 1.000 | 0.000 | 0.960 | 1941 |
| phi3_mini | synthetic | 900 | 1.000 | 0.000 | 0.960 | 398 |
| phi3_mini | bfcl_simple | 900 | 1.000 | 0.000 | 0.930 | 529 |
| phi3_mini | bfcl_multiple | 900 | 1.000 | 0.000 | 0.920 | 633 |
| qwen2 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 951 |
| qwen2 | bfcl_simple | 900 | 1.000 | 0.000 | 0.930 | 1259 |
| qwen2 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.980 | 1250 |
| llama31 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 895 |
| llama31 | bfcl_simple | 900 | 1.000 | 0.000 | 0.940 | 1194 |
| llama31 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 2882 |
| mistral_v01 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 814 |
| mistral_v01 | bfcl_simple | 900 | 1.000 | 0.001 | 0.880 | 1081 |
| mistral_v01 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.910 | 1116 |
| qwen25 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 13828 |
| qwen25 | bfcl_simple | 900 | 1.000 | 0.000 | 0.960 | 1174 |
| qwen25 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 1269 |
| mistral_v03 | synthetic | 900 | 1.000 | 0.000 | 0.960 | 621 |
| mistral_v03 | bfcl_simple | 900 | 1.000 | 0.000 | 0.920 | 855 |
| mistral_v03 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.960 | 857 |
| llama3 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 884 |
| llama3 | bfcl_simple | 900 | 1.000 | 0.001 | 0.890 | 1206 |
| llama3 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 1232 |
| granite32 | synthetic | 900 | 1.000 | 0.000 | 0.980 | 797 |
| granite32 | bfcl_simple | 900 | 1.000 | 0.000 | 0.970 | 1048 |
| granite32 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.990 | 1059 |
| granite31 | synthetic | 900 | 1.000 | 0.000 | 0.980 | 745 |
| granite31 | bfcl_simple | 900 | 1.000 | 0.000 | 0.960 | 1038 |
| granite31 | bfcl_multiple | 900 | 1.000 | 0.001 | 0.990 | 1071 |
| granite30 | synthetic | 900 | 1.000 | 0.001 | 1.000 | 790 |
| granite30 | bfcl_simple | 900 | 1.000 | 0.003 | 0.940 | 1105 |
| granite30 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 1079 |
| phi4_mini | synthetic | 900 | 1.000 | 0.000 | 1.000 | 898 |
| phi4_mini | bfcl_simple | 900 | 1.000 | 0.001 | 0.940 | 1228 |
| phi4_mini | bfcl_multiple | 900 | 1.000 | 0.003 | 0.950 | 1313 |
| mistral_v02 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 663 |
| mistral_v02 | bfcl_simple | 900 | 1.000 | 0.000 | 0.790 | 869 |
| mistral_v02 | bfcl_multiple | 900 | 1.000 | 0.001 | 0.800 | 962 |
| phi35_mini | synthetic | 900 | 1.000 | 0.021 | 1.000 | 786 |
| phi35_mini | bfcl_simple | 900 | 1.000 | 0.042 | 0.960 | 1347 |
| phi35_mini | bfcl_multiple | 900 | 1.000 | 0.032 | 0.950 | 1391 |
| qwen3 [grammar + thinking blocked] | synthetic | 900 | 0.848 | 0.030 | 0.930 | 3127 |
| qwen3 [grammar + thinking blocked] | bfcl_simple | 900 | 0.972 | 0.056 | 0.940 | 4870 |
| qwen3 [grammar + thinking blocked] | bfcl_multiple | 900 | 0.958 | 0.048 | 0.900 | 5076 |

## Timing anomaly: qwen25/synthetic (isolated, not a protocol issue)

`qwen25/synthetic` took 13,828s vs F1's 461s for the identical config
(~30x) while every surrounding run stayed in the normal ~2.5x-vs-F1
range. Checked directly: 0% truncation, normal record lengths (74-105
chars for tool calls), no repetition loop -- not a generation-content
issue. Treated as an isolated external/environmental slowdown (not the
grammar, not the protocol), logged in DEVIATIONS.md.

## Qwen3-only repetition loop recurs (lower rate than F4)

The same pattern found in F4 (2026-10-09) recurs under R: **26/1800
(1.44%) of Qwen3's baseline/schema_drift records** (0/600 synthetic,
10/600 bfcl_simple, 16/600 bfcl_multiple) get stuck repeating a
key-value pair in the open-ended `"arguments"` object until
`max_tokens` -- all 26 still truncated, all 26 still fail to parse.
Lower than F4's 2.6% despite R's 4x larger budget (plausible: a model
that's going to loop either escapes early or doesn't; a bigger budget
mostly means more repeated garbage before the same outcome, not a
higher chance of looping). Scanned all 15 other models again: zero
occurrences. Not fixed, same reasoning as F4.

## Qwen3: grammar also blocks thinking (same label as F4)

Same mechanism and decision as F4 (2026-10-08): the `generic_json`
grammar forces the first emitted token to be `{`, so Qwen3's `<think>`
block is never emitted. **For every other model, R changes exactly two
things from D** (max_tokens, constrained decoding). **For Qwen3, R
changes three**: those two, plus (as a structural side effect)
thinking gets blocked -- labeled `[grammar + thinking blocked]` above.

## Qwen3: all 3 suites pre-split ahead of time

Per DEVIATIONS.md, 2026-10-09: all 3 suites ran via
`scripts/split_run.py` (50-task halves, merged).

## run_manifest.json diff vs. D (all 48 runs)

Compared every field under `run_factors` and `model_backend` for all 48
model/suite pairs directly. **Exactly two differences, identical
across every single run:**

```
run_factors.F1_max_tokens:            D = 256     R = 1024
run_factors.F4_constrained_decoding:  D = 'off'   R = 'generic_json'
```

No other field differs on any of the 48 runs.