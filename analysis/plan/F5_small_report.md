# F5 / R_F5 (Q8_0) run report, small models (laptop)

gemma2_2b, gemma3_4b, phi3_mini, phi35_mini, phi4_mini; 3 suites; F5 = D's config + Q8_0 file, R_F5 = R's config + Q8_0 file. Record-keeping only: no verdicts, no comparison to D/R.

**Runs completed: 30/30**
**Total elapsed time: 9.8 hours**
**Errors: 0**

| Protocol | Model | Suite | Records | Parse rate | Truncation rate | Greedy baseline acc | Seconds |
|---|---|---|---|---|---|---|---|
| F5 | gemma2_2b | synthetic | 900 | 1.000 | 0.000 | 0.970 | 305 |
| F5 | gemma2_2b | bfcl_simple | 900 | 0.997 | 0.002 | 0.830 | 487 |
| F5 | gemma2_2b | bfcl_multiple | 900 | 0.993 | 0.000 | 0.880 | 507 |
| F5 | phi3_mini | synthetic | 900 | 1.000 | 0.000 | 0.960 | 483 |
| F5 | phi3_mini | bfcl_simple | 900 | 1.000 | 0.002 | 0.930 | 635 |
| F5 | phi3_mini | bfcl_multiple | 900 | 0.993 | 0.001 | 0.960 | 712 |
| F5 | phi4_mini | synthetic | 900 | 1.000 | 0.000 | 1.000 | 569 |
| F5 | phi4_mini | bfcl_simple | 900 | 1.000 | 0.000 | 0.920 | 674 |
| F5 | phi4_mini | bfcl_multiple | 900 | 1.000 | 0.002 | 0.940 | 695 |
| F5 | gemma3_4b | synthetic | 900 | 1.000 | 0.002 | 0.900 | 497 |
| F5 | gemma3_4b | bfcl_simple | 900 | 1.000 | 0.003 | 0.940 | 651 |
| F5 | gemma3_4b | bfcl_multiple | 900 | 1.000 | 0.001 | 0.940 | 674 |
| F5 | phi35_mini | synthetic | 900 | 1.000 | 0.069 | 1.000 | 834 |
| F5 | phi35_mini | bfcl_simple | 900 | 1.000 | 0.138 | 0.930 | 1330 |
| F5 | phi35_mini | bfcl_multiple | 900 | 1.000 | 0.160 | 0.960 | 1542 |
| R_F5 | gemma2_2b | synthetic | 900 | 1.000 | 0.000 | 1.000 | 1128 |
| R_F5 | gemma2_2b | bfcl_simple | 900 | 1.000 | 0.000 | 0.850 | 1584 |
| R_F5 | gemma2_2b | bfcl_multiple | 900 | 1.000 | 0.000 | 0.870 | 1664 |
| R_F5 | phi3_mini | synthetic | 900 | 1.000 | 0.000 | 0.960 | 498 |
| R_F5 | phi3_mini | bfcl_simple | 900 | 1.000 | 0.000 | 0.940 | 709 |
| R_F5 | phi3_mini | bfcl_multiple | 900 | 1.000 | 0.001 | 0.950 | 819 |
| R_F5 | phi4_mini | synthetic | 900 | 1.000 | 0.000 | 1.000 | 1009 |
| R_F5 | phi4_mini | bfcl_simple | 900 | 1.000 | 0.000 | 0.930 | 1324 |
| R_F5 | phi4_mini | bfcl_multiple | 900 | 1.000 | 0.002 | 0.960 | 1409 |
| R_F5 | gemma3_4b | synthetic | 900 | 1.000 | 0.000 | 0.900 | 1307 |
| R_F5 | gemma3_4b | bfcl_simple | 900 | 1.000 | 0.000 | 0.950 | 1813 |
| R_F5 | gemma3_4b | bfcl_multiple | 900 | 1.000 | 0.000 | 0.940 | 1862 |
| R_F5 | phi35_mini | synthetic | 900 | 1.000 | 0.059 | 1.000 | 1912 |
| R_F5 | phi35_mini | bfcl_simple | 900 | 1.000 | 0.124 | 0.930 | 3585 |
| R_F5 | phi35_mini | bfcl_multiple | 900 | 1.000 | 0.130 | 0.960 | 3965 |

## run_manifest.json diffs

Compared every field under `run_factors` and `model_backend`, for all
5 models x 3 suites, against each protocol's base (`F5` vs `D`, `R_F5`
vs `R`). **Both differ in exactly the same two fields, nothing else:**

```
run_factors.F5_quant_level:   'unspecified' -> 'Q8_0'
model_backend.model_path:     <model>-Q4_K_M.gguf -> <model>-Q8_0.gguf
```

Both fields label the one intended change (quant level; the path
necessarily follows). Unlike F11's manifest diff, there is no second
real difference here -- swapping Q4_K_M for Q8_0 only changes which
weights file is loaded, not sampling, stop tokens, or wrapping.