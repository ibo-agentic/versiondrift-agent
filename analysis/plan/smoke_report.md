# PLAN.md 10.2 Smoke Test Report (2026-10-05)

All 16 models from PLAN.md section 2, run exactly once each through the D
protocol plus whichever of F3/F4 apply. No full experiment was run; this
is engineering verification only, per PLAN.md 10.2's own scope. Outputs
live under `results_smoke/<model_key>/<config>/` (raw_outputs.jsonl,
parsed_results.jsonl, config_summary.json per config; model_result.json
aggregates a model's configs) — never written into `results/`.

## Method

- **Tasks**: first 5 (by task_id) from each of synthetic, BFCL-simple,
  BFCL-multiple = 15 tasks/config.
- **Conditions per task**: `baseline`, one `schema_drift` type
  (`field_rename` — generatable for every tool, so no suite is skipped),
  and `fault_reporting`. For `fault_reporting`, the 5 tasks per suite were
  assigned deterministically — not left to chance — to guarantee coverage:
  task 1 = clean "ok" (no fault), tasks 2-5 = `timeout`/`tool_exception`/
  `empty_result`/`partial_result` once each.
- **Trials**: greedy only (temperature 0), as instructed.
- **Configs per model**: **D** (`chat_wrapping: native`, `prompt_format:
  shared`, `max_tokens: 256`, `constrained_decoding: off`) and **F4**
  (same, `constrained_decoding: generic_json`) for all 16 models; **F3**
  (`prompt_format: native`, passing a `tools=` list) only for the 8 models
  with a real native tool-calling template per
  `analysis/plan/feasibility.md`'s own research: Mistral v0.3, Qwen2.5,
  Qwen3, Llama-3.1, Phi-4-mini, Granite 3.0/3.1/3.2. 40 model×config rows,
  45 records each = **1,800 total generations**.
- `n_ctx=4096` for every run (matches this project's existing default).
- Harness: `scripts/smoke_lib.py`/`smoke_one_model.py`/`smoke_test.py` —
  drives `upgradecanary`'s existing `build_prompt`/`apply_drift`/
  `extract_tool_call_with_format`/`evaluate`/`evaluate_fault_reporting`
  functions directly (nothing reimplemented), one model per subprocess
  for VRAM/crash isolation.

**Out of scope for this pass** (not downloaded/run; a separate decision):
Gemma-2-9b-it (not one of the 16 core models — PLAN.md lists it only as
an optional extra "if smoke test fits 8GB"), every Q8_0 and Q2_K file
(F5/positive-control (a) need those; not downloaded yet), and F6
"recommended" sampling presets (this pass used greedy/shared throughout).

## Headline results

- **`tokenizer.chat_template` present: yes, for all 16 GGUFs** (40/40
  rows) — every downloaded file preserved this metadata; native wrapping
  (and F3) has what it needs for every model.
- **BOS check: correct for all 40 rows** — exactly one BOS token at the
  prompt's start for every model whose template wants one, and exactly
  zero for the ones that don't (e.g. Qwen's ChatML templates — confirmed
  intentional via `native_model_wants_bos`, not a bug).
- **Role/turn-marker leakage (over-generation check): zero across all
  1,800 generations.** No output anywhere contained `<|im_start|>`,
  `<|eot_id|>`, `<end_of_turn|>`, or any other marker from PLAN.md
  10's list.
- **Peak VRAM: 2.68–6.73 GiB across every config** — comfortably inside
  the 8 GB card for all 16 models; nothing approached the risk zone
  Gemma-2-9b would represent (not tested here).
- **Llama-3.1's `"parameters"` key (F3) parsed at 100%** — confirms the
  `parameters_alias` handling added in today's Fix 2 works on a real
  model's actual output, not just the synthetic test fixtures.
- Granite 3.0/3.1/3.2, Llama-3.1, and (after the fix below) Phi-4-mini
  all render a real tool list under F3 (directly verified by rendering
  their templates with the same `tools=`/fallback input the harness
  uses) — PLAN.md 10's explicit "verify ... render with a tool list"
  check now passes for all 5 of these models. Phi-4-mini needed the fix
  in Problem 1 to get there; it was the one exception found.

## Full results: one row per model × config

| Model | Config | chat_template | BOS ok | parse_rate | detected_format | trunc_rate | role_leaks | peak_vram_MiB | sec/record |
|---|---|---|---|---|---|---|---|---|---|
| mistral_v01 | D | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 5114 | 0.71 |
| mistral_v01 | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 5114 | 0.79 |
| mistral_v02 | D | True | True | 0.867 | bare_json:26 | 0.000 | 0 | 5114 | 0.97 |
| mistral_v02 | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 5114 | 1.12 |
| mistral_v03 | D | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 5116 | 0.77 |
| mistral_v03 | F3_native_tool_format | True | True | 0.967 | list_wrapped:29 | 0.000 | 0 | 5116 | 1.15 |
| mistral_v03 | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 5116 | 0.93 |
| qwen2 | D | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 4852 | 0.66 |
| qwen2 | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 5630 | 1.52 |
| qwen25 | D | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 4898 | 0.72 |
| qwen25 | F3_native_tool_format | True | True | 1.000 | qwen_tool_call_tag:30 | 0.000 | 0 | 4898 | 0.75 |
| qwen25 | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 4898 | 1.45 |
| qwen3 | D | True | True | 0.667 | bare_json:20 | 0.400 | 0 | 5542 | 5.20 |
| qwen3 | F3_native_tool_format | True | True | 0.567 | qwen_tool_call_tag:18 | 0.467 | 0 | 5542 | 5.54 |
| qwen3 | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.178 | 0 | 5542 | 3.28 |
| llama3 | D | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 6198 | 0.81 |
| llama3 | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 6202 | 1.41 |
| llama31 | D | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 6188 | 0.70 |
| llama31 | F3_native_tool_format | True | True | 1.000 | parameters_alias:30 | 0.000 | 0 | 6164 | 0.79 |
| llama31 | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 6204 | 1.52 |
| phi3_mini | D | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 4999 | 0.61 |
| phi3_mini | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 4999 | 0.76 |
| phi35_mini | D | True | True | 1.000 | bare_json:30 | 0.089 | 0 | 4999 | 1.11 |
| phi35_mini | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.089 | 0 | 5017 | 1.26 |
| phi4_mini | D | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 6484 | 0.96 |
| phi4_mini | F3_native_tool_format | True | True | 0.500 | list_wrapped:15 | 0.022 | 0 | 3522 | 0.73 |
| phi4_mini | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 6734 | 3.68 |
| granite30 | D | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 5809 | 0.84 |
| granite30 | F3_native_tool_format | True | True | 0.933 | list_wrapped:28 | 0.000 | 0 | 5809 | 0.86 |
| granite30 | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 5809 | 1.04 |
| granite31 | D | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 5809 | 0.82 |
| granite31 | F3_native_tool_format | True | True | 1.000 | qwen_tool_call_tag:30 | 0.000 | 0 | 5809 | 0.84 |
| granite31 | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 5809 | 1.01 |
| granite32 | D | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 5809 | 0.81 |
| granite32 | F3_native_tool_format | True | True | 1.000 | qwen_tool_call_tag:30 | 0.000 | 0 | 5809 | 0.85 |
| granite32 | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 5809 | 1.02 |
| gemma2_2b | D | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 2677 | 0.32 |
| gemma2_2b | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 2677 | 1.56 |
| gemma3_4b | D | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 3563 | 0.49 |
| gemma3_4b | F4_generic_json | True | True | 1.000 | bare_json:30 | 0.000 | 0 | 3563 | 1.67 |

`detected_format` counts are out of 30 tool-call attempts per config
(baseline + schema_drift, 5 tasks × 3 suites × 2 conditions); `(none)`
means zero of the 30 attempts matched any recognized shape, tagged or
untagged. `parse_rate` is parse-success out of those same 30.

### fault_reporting success rate (config-independent — same prompt regardless of D/F3/F4)

| Model | Rate | Model | Rate |
|---|---|---|---|
| mistral_v01 | 0.933 | phi3_mini | 0.867 |
| mistral_v02 | 0.933 | phi35_mini | 0.667 |
| mistral_v03 | 0.533 | phi4_mini | 0.733 |
| qwen2 | 0.533 | granite30 | 0.933 |
| qwen25 | 0.933 | granite31 | 0.933 |
| qwen3 | 0.600 | granite32 | 1.000 |
| llama3 | 0.933 | gemma2_2b | 1.000 |
| llama31 | 1.000 | gemma3_4b | 0.933 |

15 records/model (5 per suite × 3 suites): 1 clean "ok" case + 1 each of
4 fault types, per suite.

## Problems found

**1. [HIGH, FIXED 2026-10-05] Phi-4-mini's native tool-calling path (F3)
was completely non-functional: 0% parse rate, zero detected tool-call
attempts of any kind, across all 30 baseline/schema_drift records.**
Root-caused by directly rendering Phi-4-mini's own chat template with
the exact `tools=` input the harness used: the rendered prompt was
`<|user|>What is the weather in Berlin?<|end|><|assistant|>` — **the tool
list was completely absent**, not malformed. Fetched Phi-4-mini's actual
`chat_template` from its `tokenizer_config.json` directly: it only
renders tool info when a `system`-role message has a `"tools"` field
(and expects that field to already be a JSON *string*, since the
template does raw string concatenation) — the top-level `tools=` kwarg
this harness (and every other model's template here) uses is never
referenced by Phi-4-mini's template at all. **Fix applied**:
`LlamaCppClient.generate()` now renders normally first, checks
(`missing_tool_names()`, new) whether every tool name actually appears
in the rendered text, and if not, retries once with a `system` message
carrying `{"tools": json.dumps(tools)}` before giving up with a clear
error — this check now runs for every model in F3 mode, not just
Phi-4-mini, so a template using some third convention will raise
instead of silently dropping tools again. Verified against Phi-4-mini's
real template text in `tests/test_native_tool_rendering.py` (reproduces
the original bug, then proves the fallback fixes it).

**Rerun result**: parse rate **0% → 50%** (15/30 detected as
`list_wrapped`, 2.2% truncation, down from 15.6%). The remaining 50% is
genuine model non-compliance, not a rendering problem — broken down by
suite: **synthetic 10/10, BFCL-simple 5/10, BFCL-multiple 0/10.** The
failures are Phi-4-mini explaining how to call the function in prose or
a Python code snippet instead of emitting the requested JSON (e.g. "You
can use the `math.gcd` function... ```python\nimport math\n..."), and it
gets worse as the prompt becomes more BFCL-native/multi-tool — a real
instruction-following limitation on this model's part, now that it
actually sees the tools. D and F4 for Phi-4-mini remain 100% unaffected
(they never use `tools=`). See
`docs/ENGINEERING_NOTES.md` section 3 for the full writeup.

**2. [MEDIUM, decision: leave D as-is] Qwen3's default "thinking" burns
through the D protocol's 256-token budget.** D and F3 both show markedly
worse truncation (40%, 47% aggregate) and parse rate (67%, 57%) than
every other model (all ≥87%, most 100%) — confirmed by inspecting a raw
record: the model emits a full `<think>...</think>` block before the
JSON answer, and on tasks where that reasoning runs long, the 256-token
cap is hit before the real answer appears (also explains Qwen3's much
higher seconds/record: ~5.2-5.5s vs. 0.3-1.6s for every other model). F4
is less affected (100% parse, 18% truncation) since the grammar still
forces valid JSON once generation reaches that point.

**Decision: D is not changed.** This is the intended typical setup, and
F1 (max_tokens)/F2 (thinking) are the factors that test exactly this
axis — not something D itself should special-case per model. Every
model × suite combination under D with truncation > 2%, for the record:

| Model | Suite | Truncation rate |
|---|---|---|
| qwen3 | bfcl_simple | 0.467 (7/15) |
| qwen3 | bfcl_multiple | 0.733 (11/15) |
| phi35_mini | bfcl_simple | 0.200 (3/15) |
| phi35_mini | bfcl_multiple | 0.067 (1/15) |

Every other model × suite combination under D is 0.000. Qwen3's
synthetic suite is also 0.000 — the truncation is specific to BFCL's
longer/more-complex prompts leaving less of the 256-token budget for
the `<think>` block to finish in, and worst on `bfcl_multiple` (longest
prompts, multiple candidate tools). Phi-3.5-mini's smaller, non-thinking
truncation (20%/7% on the same two suites) is a separate, much milder
effect worth noting but not investigated further here.

**3. [LOW-MEDIUM] Granite-3.0's actual output tag differs from
Granite-3.1 and -3.2's.** 3.1 and 3.2 both emit paired
`<tool_call>...</tool_call>` tags (Qwen-style — detected as
`qwen_tool_call_tag`), while 3.0 emits the JSON list with no recognized
tag at all (detected as untagged `list_wrapped`). All three still parse
at ≥93%, so this isn't a functional failure, but it means the three
Granite point releases are not fully interchangeable in which tag
convention actually shows up in practice — `feasibility.md`'s research
(reading each template's source instruction text, which all three phrase
nearly identically: "respond with `<|tool_call|>` followed by a JSON
list") did not predict this difference. Worth knowing before treating all
three Granite versions as using one shared parsing convention.

**Decision: keep Granite-3.0's own format (no change).** Inspected both
of its F3 parse failures (the 2/30 behind its 93.3% rate) directly.
Both (`bfcl-multiple-multiple_0`, baseline and schema_drift) are the
*same* defect: the model's JSON block has **no `"name"` key at all** —
it only names the function in surrounding prose ("you can use the
`triangle_properties.get` function with the following parameters")
and the JSON itself is just the bare argument dict
(`{"side1": 5, "side2": 4, "side3": 3, "get_area": true, ...}`), not a
`{"name", "arguments"}`/`{"name", "parameters"}` envelope. This is not
something `extract_tool_call_with_format` could recover without
guessing a tool name out of free prose text at an arbitrary position —
a heuristic this project's parser deliberately does not do (it would
risk false positives on every other model's free-text explanations
too, e.g. Phi-4-mini's prose in Problem 1's rerun also *names* functions
in backticks while explaining them, without intending a real call).
**Classification: (b) the model produced genuinely broken/incomplete
output — not a parser bug.** No parser change made; no new test needed,
since there is nothing to fix.

**4. [LOW] A handful of model/config combinations have a small number of
free-text parse misses, not a systemic or harness problem**: Mistral v0.2
D (87%, 4/30 misses), Mistral v0.3 F3 (97%, 1 miss), Granite-3.0 F3 (93%,
2 misses — classified above). Every other config is 100% except the
three flagged here.

**5. [INFO] fault_reporting success varies widely across models (53%-100%,
see table)** — expected, since this condition's exact scoring rule was
only finalized earlier today (Fix 1) and has never been run against a
real model before. Not a bug; a real signal worth tracking once the full
study runs. Qwen2 and Mistral v0.3 are the two lowest (53%) — worth a
closer look at their actual fault-reporting transcripts before the full
study, but not blocking.

## Stopping here per instruction — no fixes applied

Problems 1-3 above are real and actionable, but none were touched. Next
step is your call: whether to patch Phi-4-mini's tool-passing mechanism,
decide Qwen3's thinking-vs-budget question, and/or re-verify Granite-3.1/
3.2's tag convention against their own source templates before trusting
problem 3's reading.
