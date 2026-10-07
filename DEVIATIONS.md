# Deviations from PLAN.md (v1, binding 2026-10-05)

Every change to the plan after PLAN.md was committed as v1 (git tag
`plan-v1`) is logged here with the date and reason, instead of editing
PLAN.md itself. Newest first.

## 2026-10-07 — Granite-3.0's F3 parse rate: real parser gap found and fixed

Granite-3.0's full-run F3 parse rate (0.68-0.87) was notably lower than
Granite-3.1/3.2's (near-100%) and not explained by the 2026-10-06
investigation (which only quick-tested Granite-3.1). Investigated
directly against the real run data in `results_v2/F3/granite30/`.

**Classified every failed parse (447 total across 3 suites) into four
buckets**: `no_tool_call` (219: pure prose, no JSON-like structure at
all), `unrecognized_format` (187: some JSON structure present, but not
a shape the parser accepted), `truncation` (41: `truncated=True`), and
`invalid_json_in_tag` (0: never happened -- no case of a recognized tag
with unparseable content inside).

**Granite-3.0's native template was checked directly** (its embedded
`chat_template`, not assumed): it gives **no explicit natural-language
instruction** for the tool-call format at all -- the tools list is
rendered under `<|start_of_role|>available_tools<|end_of_role|>` with
no accompanying text telling the model how to respond. The
`<|tool_call|>` convention exists only as a template-rendering rule for
*prior-turn history* (the `assistant_tool_call` message role), never as
an in-context instruction for the *current* turn. This likely explains
why the model sometimes drifts to a different, OpenAI-flavored shape
instead.

**Within `unrecognized_format`, 12/447 (2.7%) matched one specific,
unambiguous shape**: `{"type": "function", "function": "<name>",
"arguments": {...}}` -- the tool name as a bare JSON string under
`"function"` instead of under `"name"`. Inspected 5 raw outputs
directly (mix of this shape and genuinely ambiguous ones): for every
example of this specific shape, a reasonable human reading it would
call it a correct, complete tool call (e.g. `{"type": "function",
"function": "get_weather", "arguments": {"city": "Phoenix", "unit":
"celsius"}}` unambiguously calls `get_weather(city="Phoenix",
unit="celsius")`). **This is a parser bug**, not model behavior: the
parser's `_normalize()` only recognized the tool name under `"name"`,
with no alias for this (real, observed) convention.

**Fix** (`upgradecanary/parsing.py`): `_normalize()` now also accepts
`"function"` as a name alias *only* when its value is a plain string
(deliberately distinct from true OpenAI format, where `"function"` is
a nested object with its own `"name"` inside -- that shape was already
parseable before this fix too, via the existing nested-object scan in
`_call_candidates()`, confirmed by a dedicated test). Labeled
`"function_name_alias"` in `detected_format`, consistent with this
project's existing per-alias labeling convention. Two new tests added
in `tests/test_native_tool_formats.py`.

**Rescored all other 7 native-template models' existing F3 raw outputs**
with the fixed parser (not re-run, just re-parsed) to check for
regressions: 6 of 7 (llama31, qwen25, mistral_v03, granite31, granite32,
qwen3) show **zero changes** across all 1800 tool-call-condition records
each. **phi4_mini shows 4 changes** (2 on `synthetic`, 2 on
`bfcl_multiple`, out of 1800 each) -- inspected all 4 directly: every
one is a `None -> successfully parsed` flip (never an already-correct
parse changing value), and every one uses the *same* hybrid shape
Granite-3.0 does (`"function"` as a string, sometimes combined with the
pre-existing `"parameters"` alias too). This is a genuine improvement
for phi4_mini, not a regression, but it is a real change and is
reported as such rather than claimed as "zero impact."

**Rerun**: `granite30` x 3 suites under F3 only, written to
`results_v2/F3_rerun/granite30/` (the original `results_v2/F3/
granite30/` data is kept, untouched). Parse rate improved modestly,
consistent with the fix recovering only the 2.7% `function_name_alias`
subset: synthetic 0.873 -> 0.890, bfcl_simple 0.702 -> 0.717,
bfcl_multiple 0.680 -> 0.695. The bulk of Granite-3.0's F3 failures
remain genuine model non-compliance (prose with no structured call, or
a structure with no recoverable name field at all) -- not touched by
this fix, and not a parser gap.

## 2026-10-06 — F3 native-template parse rates: root causes found, no harness changes

**Phi-4-mini**: F3's quick test (5 tasks/suite) showed 0-37% parse rate,
much lower than the 50% seen in the original smoke test. Root-caused
directly, not assumed: the smoke test ran *before* the F3/D task-text
parity fix (see commit `ea992eb`), so it used the bare-question prompt;
this quick test ran *after* that fix, using `"You are an agent that
answers questions by calling tools.\nQuestion: {task.prompt}"`. Tested
both prompt forms back-to-back against the identical model/seed/
temperature: the bare-question form reliably produces clean JSON
(`[{"name": "get_weather", ...}]`); the exact same task with the added
framing sentence reliably produces prose + a Python call instead. **The
task-framing sentence itself is what changes Phi-4-mini's native
tool-use compliance.** This is not a harness bug -- the fix that added
the framing was correct and intentional (explicit instruction: F3 must
carry the same task text as D, only the tool format should differ), and
changing it back now would reintroduce the very confound that fix was
meant to remove. Verified the prompt is otherwise fully correct for F3
(tools present in a `system` message via the existing fallback, correct
tool name, correct task text, prompt correctly ends on `<|assistant|>`).
**Decision: no harness change. Phi-4-mini's low F3 parse rate (0% on
bfcl_multiple, worse on more complex/multi-tool prompts) is logged as a
real finding** -- this model's native tool-template compliance is
sensitive to the exact framing of the preceding user turn, and gets
substantially worse as task complexity increases, even though the
prompt and tool list are both unambiguously correct.

**Qwen3**: F3's quick test showed truncation rates of 71% (`bfcl_simple`)
and 98% (`bfcl_multiple`) -- markedly worse than D's 38%/55% on the same
suites. Split every failed parse into format-failure vs. truncation: of
54 total failures across both suites, **all 54 were truncation (0 were
format failures)** -- inspected 3 examples directly, all three are still
mid-`<think>` reasoning block, with no closing tag, when the 256-token
cap hits. Likely cause: the native template's own tool-definition
rendering (Qwen's `<tools>` XML-tag convention in the system message)
gives the model more to reason about than D's in-prompt schema dump,
pushing an already-tight thinking budget further over. **Decision: no
harness change** -- this is the same accepted F1/D finding (Qwen3's
default thinking competes with a fixed token budget), observed again
and intensified under F3; D itself was already left unchanged for the
same reason (see `smoke_report.md` Problem 2).

**Granite-3.1** (the third quick-test model): 1/90 format failures,
otherwise clean -- not investigated further, negligible.

**Preemptive split for qwen3/F3**: given the quick test's truncation
rates (71%/98% on `bfcl_simple`/`bfcl_multiple`), both suites are at
real risk of exceeding the 2-hour background-execution ceiling (D's
equivalent runs already took 81-85 minutes at much lower truncation).
Generalized the F1 split mechanism into `scripts/split_run.py` (any
protocol/model/suite, not just the one F1 case) and used it
preemptively for `qwen3/F3/bfcl_simple` and `qwen3/F3/bfcl_multiple`,
rather than waiting to hit the ceiling twice as happened under F1.
`qwen3/F3/synthetic` was left as a single run (truncation improved to
4.4% in the quick test, no risk).

## 2026-10-06 — F1's qwen3/bfcl_multiple run split into two halves

**Reason**: this one run consistently exceeded the ~2-hour background-
execution ceiling on this session (two consecutive full-length attempts
each ran the full 2 hours without completing). That ceiling is a
constraint of this session's tooling, not a property of the experiment
or the protocol — F1 itself (`max_tokens=1024`, everything else
identical to D) was not changed in any way.

**What was done**: split the 100-task `bfcl_multiple` run into two
50-task halves (`scripts/f1_qwen3_bfcl_multiple_split.py`), ran each
separately (each comfortably under 2 hours: 3742s and 4076s), and
merged their `raw_outputs.jsonl`/`parsed_results.jsonl` into a single
900-record run, recomputing `summary.json` from the merged records via
the real `evaluator.summarize()`. The merged `run_manifest.json` carries
an explicit `"note"` field documenting the split.

**Why this is safe**: every task's randomness is keyed by `rng_for(seed,
task_id, condition)` (see `upgradecanary/utils.py`) — never by the
task's position in the list or by which process/invocation generated
it. Splitting the task file into two subsets and running each under the
same global seed (1234) and the same trial seeds therefore produces,
for each individual task, the exact same generation as if all 100 tasks
had been run together in one invocation. Only the physical grouping
into two subprocess calls differs; nothing about the model, prompts,
conditions, trials, or sampling changes.

**Proof, not just assertion** (`scripts/prove_split_equivalence.py`):
took 10 tasks from the synthetic suite for a fast model (gemma2_2b,
protocol D, to keep the proof itself cheap), ran them once as a single
10-task run and once as two 5-task halves, and compared every record.
**Result: 90/90 records identical** in both `parsed_results.jsonl` and
`raw_outputs.jsonl` (excluding the `run_id` field, which legitimately
differs between the two invocations' timestamps) — confirmed by direct
comparison, not assumed from the seeding argument alone.
