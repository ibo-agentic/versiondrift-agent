# Controls run report (PLAN.md section 6, 2026-10-11)

Three controls, each R's exact config with one change (see DEVIATIONS.md for the full definitions): R_AA (seed 5678 instead of 1234, 6 models), R_PC_NODESC (tool descriptions stripped, 4 models), R_PC_Q2K (Q2_K quant instead of Q4_K_M, 4 models). 100 tasks each, baseline/schema_drift/fault_reporting, 1 greedy + 2 sampled trials. No verdicts, no comparison to R here -- record-keeping only, per instruction.

**Runs completed: 42/42**
**Total elapsed time: 12.8 hours**
**Errors: 0**

| Protocol | Model | Suite | Records | Parse rate | Truncation rate | Greedy baseline acc | Seconds |
|---|---|---|---|---|---|---|---|
| R_AA | mistral_v02 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 668 |
| R_AA | mistral_v02 | bfcl_simple | 900 | 1.000 | 0.000 | 0.790 | 817 |
| R_AA | mistral_v02 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.800 | 841 |
| R_AA | qwen2 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 895 |
| R_AA | qwen2 | bfcl_simple | 900 | 1.000 | 0.000 | 0.930 | 1167 |
| R_AA | qwen2 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.980 | 1186 |
| R_AA | qwen25 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 860 |
| R_AA | qwen25 | bfcl_simple | 900 | 1.000 | 0.000 | 0.960 | 1169 |
| R_AA | qwen25 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 1178 |
| R_AA | llama31 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 885 |
| R_AA | llama31 | bfcl_simple | 900 | 1.000 | 0.000 | 0.940 | 1127 |
| R_AA | llama31 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 1165 |
| R_AA | phi35_mini | synthetic | 900 | 1.000 | 0.018 | 1.000 | 756 |
| R_AA | phi35_mini | bfcl_simple | 900 | 1.000 | 0.044 | 0.960 | 1340 |
| R_AA | phi35_mini | bfcl_multiple | 900 | 1.000 | 0.032 | 0.950 | 1262 |
| R_AA | granite31 | synthetic | 900 | 1.000 | 0.000 | 0.980 | 786 |
| R_AA | granite31 | bfcl_simple | 900 | 1.000 | 0.000 | 0.960 | 992 |
| R_AA | granite31 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.990 | 1009 |
| R_PC_NODESC | mistral_v03 | synthetic | 900 | 1.000 | 0.000 | 0.990 | 586 |
| R_PC_NODESC | mistral_v03 | bfcl_simple | 900 | 1.000 | 0.000 | 0.840 | 807 |
| R_PC_NODESC | mistral_v03 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.810 | 807 |
| R_PC_NODESC | qwen25 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 884 |
| R_PC_NODESC | qwen25 | bfcl_simple | 900 | 1.000 | 0.000 | 0.870 | 1145 |
| R_PC_NODESC | qwen25 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.820 | 1204 |
| R_PC_NODESC | llama31 | synthetic | 900 | 1.000 | 0.000 | 0.970 | 1917 |
| R_PC_NODESC | llama31 | bfcl_simple | 900 | 1.000 | 0.000 | 0.860 | 2224 |
| R_PC_NODESC | llama31 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.770 | 2744 |
| R_PC_NODESC | granite32 | synthetic | 900 | 1.000 | 0.000 | 0.950 | 1138 |
| R_PC_NODESC | granite32 | bfcl_simple | 900 | 1.000 | 0.000 | 0.930 | 1566 |
| R_PC_NODESC | granite32 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.880 | 1671 |
| R_PC_Q2K | mistral_v03 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 571 |
| R_PC_Q2K | mistral_v03 | bfcl_simple | 900 | 1.000 | 0.001 | 0.960 | 830 |
| R_PC_Q2K | mistral_v03 | bfcl_multiple | 900 | 1.000 | 0.000 | 0.960 | 796 |
| R_PC_Q2K | qwen25 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 814 |
| R_PC_Q2K | qwen25 | bfcl_simple | 900 | 1.000 | 0.000 | 0.940 | 1067 |
| R_PC_Q2K | qwen25 | bfcl_multiple | 900 | 1.000 | 0.002 | 0.950 | 1183 |
| R_PC_Q2K | llama31 | synthetic | 900 | 1.000 | 0.000 | 0.940 | 793 |
| R_PC_Q2K | llama31 | bfcl_simple | 900 | 1.000 | 0.002 | 0.850 | 1127 |
| R_PC_Q2K | llama31 | bfcl_multiple | 900 | 1.000 | 0.001 | 0.900 | 1199 |
| R_PC_Q2K | granite32 | synthetic | 900 | 1.000 | 0.000 | 1.000 | 752 |
| R_PC_Q2K | granite32 | bfcl_simple | 900 | 1.000 | 0.001 | 0.970 | 1095 |
| R_PC_Q2K | granite32 | bfcl_multiple | 900 | 1.000 | 0.002 | 0.980 | 1093 |

## run_manifest.json diff vs. R (every model, every control)

Compared every field under `run_factors` and `model_backend`, plus the
top-level `seed`, for every (control, model, suite) triple against R's
matching run. **Each control differs from R in exactly the one field
it's supposed to:**

```
R_AA vs R:          seed                                   1234 -> 5678
R_PC_NODESC vs R:    run_factors.F3_prompt_format           'shared' -> 'no_description'
R_PC_Q2K vs R:       run_factors.F5_quant_level             unset -> 'Q2_K'
                     model_backend.model_path               Q4_K_M file -> Q2_K file
```

(R_PC_Q2K's two differing fields both label the same single change --
swapping the quant file necessarily changes its path too.) No other
field differs for any control, any model, any suite.

## Timing note

One run's elapsed time looked anomalous while live-reading the
orchestrator's log (`R_PC_NODESC/granite32/bfcl_multiple`), but that
was the orchestrator's own external wrapper timer, not this run's
real work -- the table above already uses the correct internal timing
(`_status.json`'s own `elapsed_seconds`, 1670.9s, normal). See
DEVIATIONS.md, 2026-10-12, for the full explanation. A separate,
genuine internal slowdown (`qwen25/synthetic` under R, 2026-10-11,
13,828s vs F1's 461s) remains unexplained but is not part of this
report (R itself, not the controls).