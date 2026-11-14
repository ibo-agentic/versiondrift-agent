**EXPLORATORY, post hoc. Not pre-registered. Existing data only (analysis at tag pre-analysis-v2.2, commit 8e68388); descriptive; feeds no gate, verdict or hypothesis.**

# qwen25->qwen3: dose of thinking budget

Protocols: D (thinking on, 256 tokens), F1 (thinking on, 1024 tokens), F2 (thinking off). Stress diff = qwen3 minus qwen25 under the same protocol for the pair as the analysis builds it. Unparsed = share of stress-condition records for qwen3 where nothing parseable came out (failure bucket 'format'); truncated = share of all raw outputs of the qwen3 run flagged truncated.

| Suite | Protocol | Stress diff | 95% CI | Point label | CI label | qwen3 unparsed | qwen3 truncated |
|---|---|---|---|---|---|---|---|
| synthetic | D (think, 256) | -0.112 | [-0.165, -0.060] | harmful | harmful | 18.2% | 13.5% |
| synthetic | F1 (think, 1024) | +0.039 | [+0.007, +0.072] | neutral | neutral | 2.8% | 3.1% |
| synthetic | F2 (no think) | +0.084 | [+0.053, +0.117] | beneficial | beneficial | 0.0% | 0.0% |
| bfcl_simple | D (think, 256) | -0.354 | [-0.417, -0.288] | harmful | harmful | 44.4% | 39.0% |
| bfcl_simple | F1 (think, 1024) | +0.013 | [-0.026, +0.054] | neutral | neutral | 4.8% | 5.0% |
| bfcl_simple | F2 (no think) | +0.071 | [+0.030, +0.114] | beneficial | beneficial | 0.0% | 0.0% |
| bfcl_multiple | D (think, 256) | -0.480 | [-0.540, -0.417] | harmful | harmful | 54.9% | 55.1% |
| bfcl_multiple | F1 (think, 1024) | -0.019 | [-0.058, +0.020] | neutral | neutral | 5.5% | 5.7% |
| bfcl_multiple | F2 (no think) | +0.054 | [+0.015, +0.094] | beneficial | beneficial | 0.0% | 0.0% |

## Greedy-only A/A

Trial 0 only (temperature 0). Label changes between the main arm and its rerun arm, point gate:

- D vs D_AA2 over the 30 decisions: **0 flip(s)**
- R vs R_AA2 over the 30 decisions: 0 flip(s)
- D vs D_AA2 over the 48 A/A control decisions (16 models x 3 suites, model vs itself): **0 non-neutral label(s)** of 48

**Caveat:** three decisions (one pair, three suites) and one model's thinking budget; this shows how the qwen3 result moves with the budget, not why. Truncation is computed over all conditions of the run, unparsed over stress conditions only.
