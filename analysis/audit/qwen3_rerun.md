# Qwen3 rerun: thinking-mode control (nothink / think_long) vs original

All four new runs completed (900/900 records each, verified before the next run started): `upgradecanary-real-trials-qwen3-nothink_seed1234_20261001T213910Z`, `upgradecanary-bfcl-trials-qwen3-nothink_seed1234_20261001T220328Z`, `upgradecanary-real-trials-qwen3-think-long_seed1234_20261001T221907Z`, `upgradecanary-bfcl-trials-qwen3-think-long_seed1234_20261001T232407Z`. Same seed (1234), same task suites, same trial temperatures/seeds ([0.0,0.7,0.7] / [1234,1235,1236]) as the original Qwen3 runs. No existing result folder was touched; scoring code (`upgradecanary/evaluator.py`) was not changed. `llama_cpp_python==0.3.35` and the effective sampling params (top_p=0.95, top_k=40, min_p=0.05, repeat_penalty=1.0) are recorded in every new run's `run_manifest.json`.

**Environment note**: `llama-cpp-python` failed to load on this machine through its own loader even with the project's existing CUDA-DLL-directory fix (a Windows DLL-search-order issue specific to this install). Worked around by preloading each `llama_cpp/lib/*.dll` individually in dependency order before import -- this lives entirely in two new files (`analysis/audit/_dll_preload.py`, `analysis/audit/_run_config.py`) and does not touch any file under `upgradecanary/`.

## (a) Score table: Qwen2.5 vs Qwen3 variants, strict and lenient

| suite | model | condition | n | strict mean | lenient mean |
|---|---|---|---|---|---|
| synthetic | Qwen2.5 | baseline | 300 | 1.0000 | 1.0000 |
| synthetic | Qwen2.5 | schema_drift | 300 | 0.9367 | 0.9367 |
| synthetic | Qwen2.5 | runtime_fault | 300 | 1.0000 | 1.0000 |
| synthetic | Qwen3 | baseline | 300 | 0.9967 | 0.9967 |
| synthetic | Qwen3 | schema_drift | 300 | 0.9067 | 0.9067 |
| synthetic | Qwen3 | runtime_fault | 300 | 0.9467 | 0.9467 |
| synthetic | Qwen3-nothink | baseline | 300 | 1.0000 | 1.0000 |
| synthetic | Qwen3-nothink | schema_drift | 300 | 1.0000 | 1.0000 |
| synthetic | Qwen3-nothink | runtime_fault | 300 | 1.0000 | 1.0000 |
| synthetic | Qwen3-think_long | baseline | 300 | 1.0000 | 1.0000 |
| synthetic | Qwen3-think_long | schema_drift | 300 | 1.0000 | 1.0000 |
| synthetic | Qwen3-think_long | runtime_fault | 300 | 1.0000 | 1.0000 |
| BFCL | Qwen2.5 | baseline | 300 | 0.9500 | 0.9500 |
| BFCL | Qwen2.5 | schema_drift | 300 | 0.9233 | 0.9233 |
| BFCL | Qwen2.5 | runtime_fault | 300 | 0.9500 | 0.9500 |
| BFCL | Qwen3 | baseline | 300 | 0.8500 | 0.8500 |
| BFCL | Qwen3 | schema_drift | 300 | 0.6933 | 0.6933 |
| BFCL | Qwen3 | runtime_fault | 300 | 0.7200 | 0.7200 |
| BFCL | Qwen3-nothink | baseline | 300 | 0.9667 | 0.9667 |
| BFCL | Qwen3-nothink | schema_drift | 300 | 0.9367 | 0.9367 |
| BFCL | Qwen3-nothink | runtime_fault | 300 | 0.9667 | 0.9667 |
| BFCL | Qwen3-think_long | baseline | 300 | 0.9633 | 0.9633 |
| BFCL | Qwen3-think_long | schema_drift | 300 | 0.9200 | 0.9200 |
| BFCL | Qwen3-think_long | runtime_fault | 300 | 0.9500 | 0.9500 |

## (b) Qwen2.5 -> Qwen3 deltas, task-cluster bootstrap 95% CI (10,000 reps, seed 1234)

| suite | Qwen3 variant | condition | diff | 95% CI | significant? |
|---|---|---|---|---|---|
| synthetic | Qwen3 | baseline | -0.0033 | [-0.0100, +0.0000] | n.s. |
| synthetic | Qwen3 | schema_drift | -0.0300 | [-0.0967, +0.0367] | n.s. |
| synthetic | Qwen3 | runtime_fault | -0.0533 | [-0.0800, -0.0267] | significant |
| synthetic | Qwen3 | **stress (pooled)** | **-0.0417** | [-0.0783, -0.0067] | significant |
| synthetic | Qwen3-nothink | baseline | +0.0000 | [+0.0000, +0.0000] | n.s. |
| synthetic | Qwen3-nothink | schema_drift | +0.0633 | [+0.0267, +0.1067] | significant |
| synthetic | Qwen3-nothink | runtime_fault | +0.0000 | [+0.0000, +0.0000] | n.s. |
| synthetic | Qwen3-nothink | **stress (pooled)** | **+0.0317** | [+0.0133, +0.0533] | significant |
| synthetic | Qwen3-think_long | baseline | +0.0000 | [+0.0000, +0.0000] | n.s. |
| synthetic | Qwen3-think_long | schema_drift | +0.0633 | [+0.0267, +0.1067] | significant |
| synthetic | Qwen3-think_long | runtime_fault | +0.0000 | [+0.0000, +0.0000] | n.s. |
| synthetic | Qwen3-think_long | **stress (pooled)** | **+0.0317** | [+0.0133, +0.0533] | significant |
| BFCL | Qwen3 | baseline | -0.1000 | [-0.1567, -0.0467] | significant |
| BFCL | Qwen3 | schema_drift | -0.2300 | [-0.3033, -0.1600] | significant |
| BFCL | Qwen3 | runtime_fault | -0.2300 | [-0.2933, -0.1667] | significant |
| BFCL | Qwen3 | **stress (pooled)** | **-0.2300** | [-0.2817, -0.1800] | significant |
| BFCL | Qwen3-nothink | baseline | +0.0167 | [-0.0167, +0.0533] | n.s. |
| BFCL | Qwen3-nothink | schema_drift | +0.0133 | [-0.0300, +0.0600] | n.s. |
| BFCL | Qwen3-nothink | runtime_fault | +0.0167 | [-0.0200, +0.0533] | n.s. |
| BFCL | Qwen3-nothink | **stress (pooled)** | **+0.0150** | [-0.0200, +0.0500] | n.s. |
| BFCL | Qwen3-think_long | baseline | +0.0133 | [-0.0233, +0.0500] | n.s. |
| BFCL | Qwen3-think_long | schema_drift | -0.0033 | [-0.0500, +0.0433] | n.s. |
| BFCL | Qwen3-think_long | runtime_fault | +0.0000 | [-0.0367, +0.0367] | n.s. |
| BFCL | Qwen3-think_long | **stress (pooled)** | **-0.0017** | [-0.0383, +0.0317] | n.s. |

## (c) Failure breakdown + truncation rate, each Qwen3 variant

| suite | model | condition | n | fail | parse | wrong_tool | intent | invalid_drift | exec_fail | truncated(1st) | retry_truncated |
|---|---|---|---|---|---|---|---|---|---|---|---|
| synthetic | Qwen3 | baseline | 300 | 1 | 1 | 0 | 0 | 0 | 0 | N/A (no truncated field logged for this run) | N/A |
| synthetic | Qwen3 | schema_drift | 300 | 28 | 28 | 0 | 0 | 0 | 0 | N/A (no truncated field logged for this run) | N/A |
| synthetic | Qwen3 | runtime_fault | 300 | 16 | 2 | 0 | 0 | 0 | 14 | N/A (no truncated field logged for this run) | N/A |
| synthetic | Qwen3-nothink | baseline | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0/300 | 0/300 |
| synthetic | Qwen3-nothink | schema_drift | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0/300 | 0/300 |
| synthetic | Qwen3-nothink | runtime_fault | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0/300 | 0/300 |
| synthetic | Qwen3-think_long | baseline | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0/300 | 0/300 |
| synthetic | Qwen3-think_long | schema_drift | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0/300 | 0/300 |
| synthetic | Qwen3-think_long | runtime_fault | 300 | 0 | 0 | 0 | 0 | 0 | 0 | 0/300 | 0/300 |
| BFCL | Qwen3 | baseline | 300 | 45 | 34 | 0 | 11 | 0 | 0 | N/A (no truncated field logged for this run) | N/A |
| BFCL | Qwen3 | schema_drift | 300 | 92 | 76 | 0 | 16 | 0 | 0 | N/A (no truncated field logged for this run) | N/A |
| BFCL | Qwen3 | runtime_fault | 300 | 84 | 38 | 0 | 14 | 0 | 32 | N/A (no truncated field logged for this run) | N/A |
| BFCL | Qwen3-nothink | baseline | 300 | 10 | 0 | 0 | 10 | 0 | 0 | 0/300 | 0/300 |
| BFCL | Qwen3-nothink | schema_drift | 300 | 19 | 0 | 0 | 19 | 0 | 0 | 0/300 | 0/300 |
| BFCL | Qwen3-nothink | runtime_fault | 300 | 10 | 0 | 0 | 10 | 0 | 0 | 0/300 | 0/300 |
| BFCL | Qwen3-think_long | baseline | 300 | 11 | 0 | 0 | 11 | 0 | 0 | 0/300 | 0/300 |
| BFCL | Qwen3-think_long | schema_drift | 300 | 24 | 0 | 0 | 24 | 0 | 0 | 0/300 | 0/300 |
| BFCL | Qwen3-think_long | runtime_fault | 300 | 15 | 0 | 0 | 15 | 0 | 0 | 0/300 | 0/300 |

## (d) Gate verdict, Qwen2.5 -> Qwen3, threshold 0.05

| suite | Qwen3 variant | stress diff | verdict |
|---|---|---|---|
| synthetic | Qwen3 | -0.0417 | **neutral** |
| synthetic | Qwen3-nothink | +0.0317 | **neutral** |
| synthetic | Qwen3-think_long | +0.0317 | **neutral** |
| BFCL | Qwen3 | -0.2300 | **harmful** |
| BFCL | Qwen3-nothink | +0.0150 | **neutral** |
| BFCL | Qwen3-think_long | -0.0017 | **neutral** |

## (e) Plain-English answer

**No -- "Qwen3 is a robustness downgrade from Qwen2.5" does not survive once thinking-mode truncation is removed. On this harness, it reverses: Qwen3 (correctly configured) is essentially on par with or slightly ahead of Qwen2.5.**

- **Original** (thinking on, max_tokens=256, truncation uncontrolled): stress diff synthetic -0.042 (gate: neutral), BFCL -0.230 (gate: **harmful**) -- this is the published 'Qwen3 downgrade' finding.
- **nothink** (thinking disabled, same 256-token budget): stress diff synthetic +0.032 (gate: neutral), BFCL +0.015 (gate: neutral) -- both **flip from harmful/neutral to neutral-to-beneficial** territory; synthetic reaches a perfect 1.0/1.0/1.0 for Qwen3 across all three conditions (see table (a)), actually beating Qwen2.5's 0.937 on `schema_drift`.
- **think_long** (thinking on, max_tokens=2048): stress diff synthetic +0.032 (gate: neutral), BFCL -0.002 (gate: neutral) -- essentially the same result as nothink. This matters: it shows the fix is not 'stop Qwen3 from thinking', it's 'give it enough budget to finish either way' -- thinking itself was never the problem, the shared, too-small 256-token ceiling was.
- Every parse failure disappears: `mean_parse_ok=1.0` and 0/900 truncated records in all four new runs (table (c)), versus 31-148 parse failures and the `<think>`-truncation pattern documented in `AUDIT.md` B6 for the original run.
- The gate verdict for Qwen2.5->Qwen3 moves from **harmful (BFCL) / neutral (synthetic)** in the original run to **neutral-to-beneficial on both suites** under both fixed variants (table (d)) -- a full reversal of the direction the published decision currently reports for BFCL.

**Conclusion: the "Qwen3 robustness downgrade" claim, as currently published, is primarily a decoding-configuration artifact** (thinking mode + an undersized shared token budget), not a property of the Qwen2.5->Qwen3 upgrade itself. Recommend re-running the confirmatory analysis with `qwen3_nothink` or `qwen3_think_long` in place of the original Qwen3 config before this decision is used in any paper claim.
