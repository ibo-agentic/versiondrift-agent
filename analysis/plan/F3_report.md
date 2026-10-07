# F3 (native tool template) run report (2026-10-06)

The 8 models with a real native tool-calling template, x 3 suites, 100 tasks each, baseline/schema_drift/fault_reporting, 1 greedy + 2 sampled trials. No verdicts, no comparison to D here -- record-keeping only, per instruction.

**Runs completed: 24/24**
**Total elapsed time: 8.0 hours**
**Errors: 0**

| Model | Suite | Records | Parse rate | Truncation rate | Greedy baseline acc | Seconds |
|---|---|---|---|---|---|---|
| llama31 | synthetic | 900 | 1.000 | 0.000 | 0.800 | 502 |
| llama31 | bfcl_simple | 900 | 0.997 | 0.001 | 0.490 | 649 |
| llama31 | bfcl_multiple | 900 | 0.992 | 0.000 | 0.420 | 671 |
| qwen25 | synthetic | 900 | 0.980 | 0.000 | 0.960 | 542 |
| qwen25 | bfcl_simple | 900 | 0.998 | 0.000 | 0.790 | 679 |
| qwen25 | bfcl_multiple | 900 | 0.983 | 0.000 | 0.720 | 707 |
| mistral_v03 | synthetic | 900 | 1.000 | 0.008 | 1.000 | 875 |
| mistral_v03 | bfcl_simple | 900 | 0.995 | 0.063 | 0.840 | 1286 |
| mistral_v03 | bfcl_multiple | 900 | 0.988 | 0.030 | 0.770 | 1227 |
| granite32 | synthetic | 900 | 1.000 | 0.002 | 0.980 | 665 |
| granite32 | bfcl_simple | 900 | 1.000 | 0.003 | 0.780 | 882 |
| granite32 | bfcl_multiple | 900 | 0.975 | 0.000 | 0.710 | 874 |
| granite31 | synthetic | 900 | 1.000 | 0.002 | 0.950 | 694 |
| granite31 | bfcl_simple | 900 | 1.000 | 0.001 | 0.830 | 945 |
| granite31 | bfcl_multiple | 900 | 0.978 | 0.000 | 0.740 | 967 |
| granite30 [^1] | synthetic | 900 | 0.890 | 0.001 | 0.900 | 855 |
| granite30 [^1] | bfcl_simple | 900 | 0.717 | 0.028 | 0.570 | 1428 |
| granite30 [^1] | bfcl_multiple | 900 | 0.695 | 0.042 | 0.420 | 1561 |
| phi4_mini [^2] | synthetic | 900 | 0.298 | 0.000 | 0.240 | 561 |
| phi4_mini [^2] | bfcl_simple | 900 | 0.212 | 0.006 | 0.100 | 748 |
| phi4_mini [^2] | bfcl_multiple | 900 | 0.162 | 0.014 | 0.060 | 795 |

[^1]: 2026-10-07 update: these rows are `results_v2/F3_rerun/granite30/`
(the official result as of 2026-10-07), not the original
`results_v2/F3/granite30/` run. A parser gap was found and fixed
(Granite-3.0's `{"type":"function","function":"<name string>",...}`
and combined `function`+`parameters` hybrid shapes); raw model output
is confirmed byte-identical between the two folders, so every number
change here is the parser fix, not a model-output difference. Seconds
column still reflects the original run's wall-clock time (the rerun
was not separately timed as an official run). Full writeup in
`DEVIATIONS.md`.

[^2]: 2026-10-07 update: rescored in place from the same raw outputs
(no rerun -- deterministic, no GPU needed) with the same parser fix.
See `DEVIATIONS.md`.
| qwen3 | synthetic | 900 | 0.962 | 0.114 | 1.000 | 3540 |
| qwen3 | bfcl_simple | 900 | 0.658 | 0.401 | 0.630 | 2323 |
| qwen3 | bfcl_multiple | 900 | 0.542 | 0.458 | 0.470 | 4692 |
## Models with a native tool template (and which don't)

8 of 16 have a real native tool-calling template (per `analysis/plan/
feasibility.md`'s verified research, reconfirmed in the smoke tests):
**Mistral v0.3, Qwen2.5, Qwen3, Llama-3.1, Phi-4-mini, Granite-3.0,
Granite-3.1, Granite-3.2.** The other 8 (Mistral v0.1/v0.2, Qwen2,
Llama-3, Phi-3-mini, Phi-3.5-mini, Gemma-2-2b, Gemma-3-4b) do not, and
were not run under F3.

## Task-instruction-text parity with D

Confirmed directly (not assumed): F3's prompt carries the exact same
`"You are an agent that answers questions by calling tools.\nQuestion:
{task.prompt}"` text as D -- only the tool-format instruction (schema
dump vs. native `tools=`) differs. Rendered the full final prompt for
one example per family (Mistral, Qwen, Llama, Phi, Granite) and
confirmed in every case: the task question is present, the tool
name(s) are present (via the existing render-check-and-fallback
mechanism for Phi-4-mini specifically), and the prompt correctly ends
on that model's own assistant-turn-opening marker.

## Quick test and investigation (5 tasks/suite: phi4_mini, qwen3, granite31)

Tool-name render check passed cleanly for all 405 records (no crashes --
every tool name reached every rendered prompt, directly or via the
fallback). Parse rates were low for two of the three models; both were
investigated to their root cause before the full run (see
`DEVIATIONS.md`, 2026-10-06, for the full writeup):

- **phi4_mini**: traced precisely to the F3/D task-text parity fix
  itself -- the added framing sentence (intentional, per explicit prior
  instruction) is what flips this model from clean JSON to prose+Python,
  confirmed by testing both prompt forms back-to-back on the identical
  model/seed/temperature. Not a harness bug; the fix was correct and
  necessary to avoid a confound between D and F3.
- **qwen3**: all 54 quick-test failures were truncation (0 format
  failures) -- confirmed via 3 inspected examples, all still mid-`<think>`
  when the 256-token cap hit. Same accepted D/F1 thinking-budget
  tradeoff, intensified by the native template's own tool rendering.
  Not a harness bug.
- **granite31**: 1/90 failures, negligible.

Per instruction, no model was excluded for a bad result -- only a
harness bug would have been grounds to fix or skip, and none was found.
All 8 native-template models were run at full scale.

## Qwen3/F3: two suites pre-split ahead of time

Given the quick test's truncation rates (40%/46% at full scale on
`bfcl_simple`/`bfcl_multiple` -- see table above), both were pre-split
into 50-task halves before running (`scripts/split_run.py`, generalized
from the F1 split mechanism) rather than risking the 2-hour
background-execution ceiling reactively. `qwen3/synthetic` ran as a
single, unsplit run (11.4% truncation, well within budget). Logged in
`DEVIATIONS.md`.

## run_manifest.json diff vs. D (all 24 runs)

Compared every field under `run_factors` and `model_backend` for all 24
model/suite pairs directly. **Exactly one difference, identical across
every single run:**

```
run_factors.F3_prompt_format:  D = 'shared'   F3 = 'native'
```

No other field differs on any of the 24 runs.
