# F11 / R_F6 / R_F3 run report (2026-10-12)

Three factors, each sharing a base protocol's config with one change (see DEVIATIONS.md for full definitions): F11 (D's config + this project's own legacy hand-typed chat wrapper, 6 models), R_F6 (R's config + F6's recommended sampling, 3 held-out models whose sampling actually changes), R_F3 (R's config + native tool template for the prompt, output still grammar-constrained, 5 held-out models with a real native template). 100 tasks each, baseline/schema_drift/fault_reporting, 1 greedy + 2 sampled trials. No verdicts, no comparison to D/R here -- record-keeping only, per instruction.

**Runs completed: 42/42**
**Total elapsed time: 13.9 hours**
**Errors: 0**

| Protocol | Model | Suite | Records | Parse rate | Truncation rate | Greedy baseline acc | Seconds |
|---|---|---|---|---|---|---|---|
| F11 | mistral_v01 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 544 |
| F11 | mistral_v01 | bfcl_simple | 900 | 0.982 | 0.003 | 0.900 | 717 |
| F11 | mistral_v01 | bfcl_multiple | 900 | 0.980 | 0.003 | 0.910 | 837 |
| F11 | mistral_v02 | synthetic | 900 | 1.000 | 0.002 | 1.000 | 659 |
| F11 | mistral_v02 | bfcl_simple | 900 | 0.982 | 0.006 | 0.810 | 833 |
| F11 | mistral_v02 | bfcl_multiple | 900 | 0.958 | 0.001 | 0.840 | 854 |
| F11 | mistral_v03 | synthetic | 900 | 1.000 | 0.000 | 0.970 | 544 |
| F11 | mistral_v03 | bfcl_simple | 900 | 1.000 | 0.003 | 0.930 | 752 |
| F11 | mistral_v03 | bfcl_multiple | 900 | 0.995 | 0.002 | 0.950 | 730 |
| F11 | qwen2 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 505 |
| F11 | qwen2 | bfcl_simple | 900 | 0.998 | 0.001 | 0.930 | 835 |
| F11 | qwen2 | bfcl_multiple | 900 | 0.992 | 0.000 | 0.990 | 667 |
| F11 | qwen25 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 457 |
| F11 | qwen25 | bfcl_simple | 900 | 1.000 | 0.000 | 0.950 | 589 |
| F11 | qwen25 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.950 | 620 |
| F11 | qwen3 | synthetic | 900 | 0.952 | 0.087 | 1.000 | 2860 |
| F11 | qwen3 | bfcl_simple | 900 | 0.815 | 0.239 | 0.890 | 3220 |
| F11 | qwen3 | bfcl_multiple | 900 | 0.623 | 0.364 | 0.690 | 3549 |
| R_F6 | llama3 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 850 |
| R_F6 | llama3 | bfcl_simple | 900 | 1.000 | 0.002 | 0.890 | 1134 |
| R_F6 | llama3 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 1150 |
| R_F6 | llama31 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 848 |
| R_F6 | llama31 | bfcl_simple | 900 | 1.000 | 0.000 | 0.940 | 1112 |
| R_F6 | llama31 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 1177 |
| R_F6 | gemma3_4b | synthetic | 900 | 1.000 | 0.000 | 0.940 | 1205 |
| R_F6 | gemma3_4b | bfcl_simple | 900 | 1.000 | 0.000 | 0.910 | 3133 |
| R_F6 | gemma3_4b | bfcl_multiple | 900 | 1.000 | 0.000 | 0.960 | 4132 |
| R_F3 | llama31 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 849 |
| R_F3 | llama31 | bfcl_simple | 900 | 1.000 | 0.000 | 0.760 | 1160 |
| R_F3 | llama31 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.650 | 1203 |
| R_F3 | phi4_mini | synthetic | 900 | 1.000 | 0.000 | 1.000 | 901 |
| R_F3 | phi4_mini | bfcl_simple | 900 | 1.000 | 0.001 | 0.760 | 1197 |
| R_F3 | phi4_mini | bfcl_multiple | 900 | 1.000 | 0.003 | 0.740 | 1291 |
| R_F3 | granite30 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 813 |
| R_F3 | granite30 | bfcl_simple | 900 | 1.000 | 0.003 | 0.810 | 1145 |
| R_F3 | granite30 | bfcl_multiple | 900 | 1.000 | 0.001 | 0.730 | 1097 |
| R_F3 | granite31 | synthetic | 900 | 1.000 | 0.000 | 0.950 | 828 |
| R_F3 | granite31 | bfcl_simple | 900 | 1.000 | 0.000 | 0.780 | 1102 |
| R_F3 | granite31 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.710 | 1132 |
| R_F3 | granite32 | synthetic | 900 | 1.000 | 0.000 | 0.950 | 820 |
| R_F3 | granite32 | bfcl_simple | 900 | 1.000 | 0.000 | 0.800 | 1090 |
| R_F3 | granite32 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.720 | 1073 |

## R_F6 greedy check vs. R

Compared every trial-0 (greedy) record against R's matching record
(by task_id + condition) for all 3 R_F6 models x 3 suites (2700
records total). **0 mismatches** -- confirms the sampling override
correctly pins the greedy trial to R's own values, same mechanism as
F6 itself.

## run_manifest.json diffs

`R_F6` vs `R` and `R_F3` vs `R` each differ in exactly one
`run_factors` field, as required:

```
R_F6 vs R:  run_factors.F6_sampling_preset   'shared' -> 'recommended'
R_F3 vs R:  run_factors.F3_prompt_format     'shared' -> 'native'
```

**`F11` vs `D` differs in 7 fields, not 1** -- but all 7 are direct,
mechanical consequences of the one `model.chat_wrapping` config change
(`native` -> `legacy`), not independent changes. Switching to
`legacy` skips the native-formatter introspection entirely, so every
field that only has meaning under native wrapping goes empty/default:

```
model_backend.chat_wrapping:                 'native' -> 'legacy'
run_factors.F11_chat_wrapping:               'native' -> 'legacy'
model_backend.native_chat_template_found:    true -> false
model_backend.native_bos_token:              '<s>' -> ''
model_backend.native_eot_token:              '' -> ''
model_backend.native_stop_tokens:            ['</s>'] -> []
model_backend.native_model_wants_bos:        true -> true (unchanged, shown for completeness)
```

No other field differs for any run, any model, any protocol.