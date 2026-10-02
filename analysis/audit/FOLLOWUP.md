# Audit follow-up — summary

Companion to `AUDIT.md`. **No existing result folder was deleted, overwritten,
or modified; no models were run.** Code was changed this time (the previous
audit was read-only by request; this follow-up explicitly asked for configs,
a parser feature, and logging changes), but every change is additive and
backward-compatible: a 25/25 `pytest` pass and a from-scratch mock-pilot run
confirm nothing broke, and `_parity_check.py` confirms the new recompute
engine reproduces all 9,000 existing scores across the 10 final runs with
**zero mismatches** before it was trusted for any diagnostic number below.

## What changed, by item

### 1. Backslash/escape check — `analysis/audit/escape_check.py` / `.md`

Added `extract_tool_call(raw, lenient=True)` to `upgradecanary/parsing.py`
(default `lenient=False`, so every existing call site and every historical
result is unaffected). Lenient mode retries JSON extraction after repairing
invalid backslash-escapes like `\_` -> `_`; since the repair can only make
an unparseable string parseable (never the reverse), any strict/lenient
score difference is attributable *solely* to an escape fix.

**Headline result: all 71/71** of Mistral v0.2's synthetic `runtime_fault`
`executor_failure` records (AUDIT.md E13's finding) flip to a passing score
under lenient retry-parsing — Mistral v0.2's synthetic `runtime_fault` mean
score moves from **0.757 (strict) to 0.993 (lenient)**, i.e. nearly the
*entire* fault-condition regression for this model disappears once the
stray-backslash artifact is repaired. The same model shows smaller but
nontrivial flips on BFCL (31 records). Mistral v0.1 (BFCL: 7 records),
Mistral v0.3, Qwen2.5, and Qwen3 show zero or near-zero flips everywhere —
this is a Mistral v0.1/v0.2-specific retry-generation quirk, not a general
parser problem. **This is arguably the single most consequential new
finding in this follow-up**: it does not just add nuance to a claim, it
removes most of the empirical basis for "Mistral v0.1→v0.2 is harmful on
`runtime_fault`" as currently measured. Strict scoring remains the official
metric per your instruction; treat this as a strong flag that the escape
bug should be fixed and the synthetic Mistral trials rerun before relying on
that decision.

**BFCL strict vs lenient table** (requested separately; synthetic was shown
above, this is the BFCL half of the same `escape_check.md` run — no new
computation, just surfaced here too):

| suite | model | condition | n | strict mean | lenient mean | records flipped 0->1 |
|---|---|---|---|---|---|---|
| BFCL | Mistral v0.1 | baseline | 300 | 0.890 | 0.900 | 3 |
| BFCL | Mistral v0.1 | schema_drift | 300 | 0.690 | 0.697 | 2 |
| BFCL | Mistral v0.1 | runtime_fault | 300 | 0.883 | 0.890 | 2 |
| BFCL | Mistral v0.2 | baseline | 300 | 0.807 | 0.827 | 6 |
| BFCL | Mistral v0.2 | schema_drift | 300 | 0.623 | 0.643 | 6 |
| BFCL | Mistral v0.2 | runtime_fault | 300 | 0.720 | 0.783 | 19 |
| BFCL | Mistral v0.3 | baseline/schema_drift/runtime_fault | 300 each | 0.943/0.777/0.940 | same | 0 |
| BFCL | Qwen2.5 | baseline/schema_drift/runtime_fault | 300 each | 0.950/0.923/0.950 | same | 0 |
| BFCL | Qwen3 | baseline/schema_drift/runtime_fault | 300 each | 0.850/0.693/0.720 | same | 0 |

Note the escape artifact is **not confined to `runtime_fault`** on BFCL — it
also flips 3-6 `baseline` and `schema_drift` records per Mistral run (it can
occur on any first attempt, not just retries; `runtime_fault` just has far
more of them because every retryable-fault record gets a second,
feedback-prompted generation, and the quirk appears to be triggered more
often in that second turn specifically — see the harness-vs-model
investigation below). Still exclusively Mistral v0.1/v0.2; zero flips for
Mistral v0.3, Qwen2.5, Qwen3 on either suite.

### 1b. Is the retry prompt itself contaminated, or does the model introduce the escape? (new since last message)

Checked directly against existing logs (`analysis/audit/retry_prompt_check.py`,
new read-only script; **no code or config changed this turn**). The retry
prompt is fully deterministic and reconstructible from stored data:
`retry_prompt = base_prompt + "\nYour previous tool call failed: {feedback}\n" + "Provide a corrected JSON answer:"`
(`upgradecanary/runner.py:182-186`, unchanged), then wrapped in the model's
`prompt_template` exactly as configured. `feedback` is the first attempt's
stored error message (e.g. `"response payload truncated by gateway"`,
`"{tool} returned an empty payload"`) — these are fixed English strings
from `upgradecanary/perturbations/runtime_faults.py`, and `base_prompt` is
a `json.dumps(...)` of the tool schema, which never escapes a bare
underscore. So there was never a mechanical reason to expect `\_` to leak
in from the prompt side — this confirms it empirically:

**Example (Mistral v0.2, synthetic, task-001, 3 of the 71 records) — full wrapped retry prompt sent to the model:**
```
[INST]
You are an agent that answers questions by calling tools.
Available tool schema:
{
  "tools": [
    {
      "args": {
        "city": {"required": true, "type": "string"},
        "unit": {"enum": ["celsius", "fahrenheit"], "required": true, "type": "string"}
      },
      "description": "Get the current weather for a city.",
      "name": "get_weather"
    }
  ]
}
Reply with ONLY a single JSON object of the form {"name": <tool name>, "arguments": {<args>}}. No markdown fences, no explanation, no text before or after the JSON.
Question: What is the current weather in Berlin? Give me the temperature in celsius.
Answer:
Your previous tool call failed: response payload truncated by gateway
Provide a corrected JSON answer:
[/INST]
```
Contains `\_` anywhere? **No** (all 3 examples checked). Model's retry output for all 3: `{"name": "get\_weather", "arguments": {"city": "Berlin", "unit": "celsius"}}` — the escape appears only in the model's own completion, never in anything it was shown.

**All models, both suites, every retried `runtime_fault` record (n=2280 total, 228 per model):**

| suite | model | retried records | prompt contains `\_` | output contains `\_` |
|---|---|---|---|---|
| synthetic | Mistral v0.1 | 225 | 0 | 0 |
| synthetic | **Mistral v0.2** | 225 | 0 | **72** |
| synthetic | Mistral v0.3 | 225 | 0 | 0 |
| synthetic | Qwen2.5 | 225 | 0 | 0 |
| synthetic | Qwen3 | 225 | 0 | 0 |
| BFCL | Mistral v0.1 | 231 | 0 | 1 |
| BFCL | **Mistral v0.2** | 231 | 0 | **18** |
| BFCL | Mistral v0.3 | 231 | 0 | 0 |
| BFCL | Qwen2.5 | 231 | 0 | 0 |
| BFCL | Qwen3 | 231 | 0 | 0 |

**Totals: 0/2280 retry prompts contain `\_`; 91/2280 retry outputs do.**

**Verdict: MODEL-CAUSED, not harness-caused.** The retry prompt never
contains the sequence across any of the 2,280 retried records in any run.
Only Mistral v0.1 and (overwhelmingly) Mistral v0.2 ever produce it, and
only in their own completions — this looks like those two Mistral
checkpoints having a learned habit of backslash-escaping underscores in
identifiers (plausibly a markdown-italics-escaping reflex, `get_weather` ->
`get\_weather`, as if guarding against Markdown rendering) that surfaces
more often in the longer, feedback-appended retry turn. (Housekeeping note:
the 72 for synthetic Mistral v0.2 here vs. the 71-record `executor_failure`
bucket in `escape_check.md` differ by exactly one record,
`task-045`/`runtime_fault`/`empty_result`/trial 1 — checked directly: that
retry output contains *two* JSON-looking blocks, the model's genuinely
correct first one and a second, `\_`-corrupted restatement with wrong
values in a trailing "explanation"; `extract_tool_call` takes the first
valid object it finds, so that record already scored 1.0 and was correctly
excluded from the failing-records bucket — not a bug, just two different
denominators.)

### 2. Qwen3 thinking control — configs only, not run

New configs (all write to **new** result folders; nothing existing is
touched):
- `configs/real_trials_qwen3_nothink.yaml` / `configs/bfcl_trials_qwen3_nothink.yaml` — thinking disabled via the standard empty-`<think></think>`-prefill trick, `max_tokens` unchanged at 256.
- `configs/real_trials_qwen3_think_long.yaml` / `configs/bfcl_trials_qwen3_think_long.yaml` — thinking left on, `max_tokens` raised to 2048 (`n_ctx` raised to 4096 to fit it).

Supporting code (backward-compatible, off by default):
- `upgradecanary/parsing.py`: `extract_tool_call(..., strip_think=True)` removes a *complete* `<think>...</think>` block before scanning for JSON; a truncated/unclosed block is left alone (so truncation still shows up as a parse failure, never silently papered over). Enabled via a new optional config key `parsing.strip_think_block`, read in `upgradecanary/runner.py`; absent in every existing config, so existing behavior is unchanged.
- `upgradecanary/model/llama_cpp_client.py` + `upgradecanary/model/base.py` + `upgradecanary/model/mock_llm.py`: every client now exposes `last_truncated()` (`True`/`False` for llama.cpp, based on the completion's `finish_reason == "length"`; `None` = not applicable, for the mock client). `upgradecanary/runner.py` logs this into `raw_outputs.jsonl` as `truncated` (first attempt) and `retry_truncated` (retry, if one happened) for **every** model/config, not just Qwen3 — so the next real run of *any* config gets this diagnostic for free.

**UPDATE 2026-10-02: done.** All four configs were run (900/900 records
each, verified) with explicit permission to run models for that task.
Headline result: the thinking-mode truncation really was driving most of
the apparent Qwen3 regression -- under both `nothink` and `think_long`,
Qwen2.5->Qwen3 flips from **harmful (BFCL) / neutral (synthetic)** to
**neutral-to-beneficial on both suites**, and synthetic Qwen3 reaches a
perfect 1.0/1.0/1.0. Full tables, bootstrap CIs, failure breakdown, and gate
verdicts: `analysis/audit/qwen3_rerun.md`.

### 3. Fault scoring fix — `analysis/audit/fault_rescore.py` / `.md`

Recomputed from existing logs only (no reruns), using the same
parity-checked recompute engine. For every `runtime_fault` record:
`first_try_score` (ignoring any retry), `final_score` recomputed
consistently on the *actual final attempt* (retry's own parsed call + exec,
not the previous mix of first-attempt metrics + retry's `ok` flag),
`recovered` (fail→pass across the retry), `broken_by_retry` (pass→fail
across the retry — **0 in every cell**, confirming AUDIT.md's structural
point that the retry can only help or be neutral under this design, never
hurt, since it's unfaulted). `stale_result` is reported separately (it
cannot fail by construction) and excluded from the main aggregate.

The "fixed, consistent" final score differs from the currently-published
("mixed") number in both directions depending on model — e.g. BFCL Qwen3
0.788 (fixed) vs 0.719 (mixed, +0.069) and BFCL Mistral v0.2 0.758 vs 0.701
(+0.057), but synthetic Mistral v0.3 1.000 vs 0.960 (+0.040) the other way
on a different run. This confirms the inconsistency flagged in AUDIT.md E10
is not a rounding-error-sized issue — it moves several cells by 0.04–0.07.

**Rename**: per your instruction, `fault_rescore.md` labels the four
retryable fault types **"retry_after_tool_failure"** and reports
`stale_result` separately. I deliberately did **not** rename the actual
`runtime_fault` condition identifier in configs/data files/`upgradecanary/`
— that string is load-bearing in `task.condition_tags` (every task row in
`data/base_tasks.jsonl`/`data/bfcl_tasks.jsonl`), in the RNG seeding key
(`rng_for(seed, task_id, condition)` — renaming it would change which fault
is drawn for which task in any new run), and in every existing config and
script (`scripts/analyze_*.py` all hardcode `"runtime_fault"`). Renaming it
project-wide is a real, mechanical, moderate-sized change but a different
piece of work with its own blast radius — I scoped this follow-up to
relabeling in generated outputs, which is what was explicitly requested
("outputs/docs"), and flagging the engine-level rename as a decision for
you rather than making it silently. Say the word and I'll do the full
rename (configs, data files' `condition_tags`, `upgradecanary/runner.py`,
all five `scripts/analyze_*.py` files, plus a migration note) as its own
change.

### 4. Logging — `run_manifest.json` (code change, takes effect on next run)

`upgradecanary/model/llama_cpp_client.py` now captures the installed
`llama_cpp_python` version and the effective sampling params (`top_p`,
`top_k`, `min_p`, `repeat_penalty` — previously never passed to
`create_completion`, so only implicit library defaults applied and were
unlogged) via a new `backend_info()` method; the four sampling params are
also now explicitly passed to `create_completion` (equal to the library's
own defaults unless a config overrides them, so **rerunning any existing
config is unaffected** — verified by the mock-pilot/parity checks above,
and these params only apply to the `llama_cpp` provider anyway).
`upgradecanary/runner.py` writes this into every new run's
`run_manifest.json` under the key `"model_backend"`. "llama.cpp build info"
specifically (the underlying C++ library's git commit/build number, as
opposed to the `llama-cpp-python` wheel version) is **NOT exposed** by the
installed `llama-cpp-python==0.3.35`'s Python API that I could find — the
wheel version is the closest available proxy and is what gets logged.
**This has no effect on any existing run**; it only changes what's recorded
starting with the next run you launch with any config.

### 5. Baseline-only gate — `analysis/audit/gate_vs_baseline.py` / `.md`

Computed for all 8 decisions (4 pairs x 2 suites): baseline-only gate
verdict vs. the published stress-based verdict, plus selected-30-task-canary
vs. random-30-task-canary (1000 reps) match rate, same table.

**Headline result, sharpening AUDIT.md K24**: on **BFCL, the baseline-only
gate reaches the identical correct verdict as the full stress-based gate on
all 4 of 4 pairs** (harmful/beneficial/beneficial/harmful). On synthetic,
baseline-only gets the two *decisive* pairs wrong (calls both "neutral"
when the stress truth is harmful/beneficial — consistent with the 96%
baseline ceiling effect from AUDIT.md I18) but happens to agree on the two
already-borderline-neutral pairs. In other words: for this specific public
suite, running `schema_drift`/`runtime_fault` at all was not necessary to
reach the correct accept/reject/inspect verdict on any of the four
decisions — only to see the magnitude and the category-level detail. This
is a stronger, decision-level version of the K24 statistical-significance
finding and should be read together with it.

### 6. Intent spot-check — `analysis/audit/intent_spotcheck.csv`

40 `schema_drift` records (20 `rule_verdict=True`, 20 `False`), spread
across 5 drift types, all 5 models, and both suites (seed `20261002`,
documented in the script for reproducibility). Columns: `suite`, `model`,
`task_id`, `trial_index`, `drift_type`, `question`, `schema_shown_args`
(the actual drifted schema shown at prompt time, reconstructed via the
unmodified `drifted_schema()`), `expected_args`, `parsed_args`,
`model_output` (first 400 chars), `rule_verdict`, and an empty
`human_verdict` column for you to fill in.

**You need to**: open `analysis/audit/intent_spotcheck.csv`, fill in
`human_verdict` (e.g. `true`/`false`/`unsure`) for each row based on your
own read of whether the parsed call means the same thing as the expected
call, and let me know if you want a disagreement-rate summary computed
afterward.

## Files added/changed

**New analysis outputs** (all in `analysis/audit/`): `escape_check.py`/`.md`,
`fault_rescore.py`/`.md`, `gate_vs_baseline.py`/`.md`, `intent_spotcheck.py`/`.csv`,
`_parity_check.py` (self-test, not a deliverable but kept for traceability),
plus the `recompute_record`/`task_lookup` additions to `common.py` (shared by
all four).

**New configs**: `configs/real_trials_qwen3_nothink.yaml`,
`configs/real_trials_qwen3_think_long.yaml`,
`configs/bfcl_trials_qwen3_nothink.yaml`,
`configs/bfcl_trials_qwen3_think_long.yaml`.

**Code changes** (additive/backward-compatible, verified via 25/25 pytest +
a fresh mock-pilot run + the 9,000-record zero-mismatch parity check):
`upgradecanary/parsing.py` (lenient + strip_think, both opt-in),
`upgradecanary/runner.py` (reads `parsing.strip_think_block`, logs
`truncated`/`retry_truncated` and `run_manifest.json["model_backend"]`),
`upgradecanary/model/base.py`, `upgradecanary/model/mock_llm.py`,
`upgradecanary/model/llama_cpp_client.py` (`last_truncated()`,
`backend_info()`, explicit sampling-param pass-through).

## What you need to run / do next

1. **Run the 4 new Qwen3 configs** (GPU) to get real nothink/think-long
   numbers — I cannot run models.
2. **Decide on the condition rename** (item 3): relabel-only (done, in
   `fault_rescore.md`) vs. full engine rename (configs + data +
   `upgradecanary/` + all `scripts/analyze_*.py` — a separate, larger
   change I scoped out of this follow-up; say the word if you want it).
3. **Fill in `human_verdict`** in `analysis/audit/intent_spotcheck.csv`.
4. Given the escape-check result (item 1), consider whether to **fix the
   escape bug and rerun the synthetic Mistral v0.1/v0.2/v0.3 trials** before
   treating the v0.1→v0.2 `runtime_fault` regression as real — right now a
   large share of it looks like a parsing artifact, not a model difference.
