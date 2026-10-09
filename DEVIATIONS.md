# Deviations from PLAN.md (v1, binding 2026-10-05)

Every change to the plan after PLAN.md was committed as v1 (git tag
`plan-v1`) is logged here with the date and reason, instead of editing
PLAN.md itself. Newest first.

## 2026-10-09 — F4 complete: Qwen3-only repetition loop found at full scale

All 48 F4 runs completed (20.2 hours; grammar-constrained decoding is
CPU-bound token-masking overhead, not GPU-accelerated, hence much
slower than D -- not a bug). The quick test (5 tasks/suite) found 0/270
truncated `baseline`/`schema_drift` records and concluded the grammar
does not cause endless whitespace or loops -- **true at that sample
size, but incomplete**: at full scale (100 tasks), Qwen3 shows a real
instance of exactly the loop pattern asked about, in a minority of its
tool-call records. Confirmed directly by reading the raw truncated
outputs, e.g.:

```
...": "theft crimes", "crime_type_v2": "theft crimes", "crime_type_v2":
"theft crimes", "crime_type_v2": "theft crimes", "crime_type_v2": ...
```

**47/1800 (2.6%) of Qwen3's `baseline`/`schema_drift` records** hit
this (6/600 `synthetic`, 16/600 `bfcl_simple`, 25/600 `bfcl_multiple`):
the model gets stuck repeating the same key-value pair inside the
`"arguments"` object until `max_tokens` cuts it off. Likely cause: the
`generic_json` schema's `"arguments": {"type": "object"}` has no
property constraints, so the grammar permits unlimited repeated
key-value pairs there, and losing the `<think>` scratchpad (this
protocol's other Qwen3 effect, logged above) removes whatever lets it
normally converge on one answer and stop. **Scanned all 15 other
models' `baseline`/`schema_drift` records (27,000 total) for the same
pattern: zero occurrences.** This is a Qwen3-only effect, not a general
risk of the `generic_json` grammar -- consistent with it being the
one model whose `<think>` block the grammar also blocks. Logged here,
not fixed (would require changing the grammar or dropping Qwen3, both
out of scope for this already-labeled "grammar + thinking blocked"
variant); counted as a real finding, not a harness bug.

**Manifest diff vs. D (all 48 runs)**: exactly one field differs,
identical across every run: `run_factors.F4_constrained_decoding: D =
'off', F4 = 'generic_json'`. No other field differs on any of the 48
runs.

## 2026-10-08 — Analysis conventions fixed before any verdict is computed

Set here, before any pair difference exists, so none is chosen after seeing results. Implemented in `configs/analysis_official_folders.yaml` and `vdanalysis/` on branch `analysis-prep`.

- **Stress diff.** PLAN.md section 4 says "the stress conditions, as in the existing pipeline" without listing them; the old pipeline used schema_drift + runtime_fault, and runtime_fault is not rerun (section 3). Decision: the stress conditions are **schema_drift + fault_reporting**, and the stress diff is the **average of the two per-condition paired diffs, equal weight per condition** (not a pooled record mean). The CI gate's cluster bootstrap resamples tasks and recomputes that same average (10,000 reps, seed 1234). Baseline is never part of the stress diff.
- **F6.** Main number: only pairs where at least one model's sampling changed (qwen2, qwen25, qwen3, llama3, llama31, gemma3_4b). All pairs also reported.
- **F3.** F3 ran on the 8 models with a native tool template (llama31, qwen25, mistral_v03, granite30, granite31, granite32, qwen3, phi4_mini; the F3 orchestrator's `NATIVE_TEMPLATE_MODELS`). **F3 main flip count = both-native pairs only: qwen25->qwen3, granite30->granite31, granite31->granite32, i.e. 9 decisions (small).** All pairs where at least one model ran F3 are also reported, as a mixed comparison (native new vs shared-prompt old, so two things differ). Official data: granite30 from `results_v2/F3_rerun/`; phi4_mini from the rescored `results_v2/F3/`; `results_v2/F3/granite30/` is audit-only and the analysis loader refuses it.
- **F4.** Generic JSON only. Qwen3 under F4 and under R is labeled "grammar + thinking blocked", excluded from the main F4 number, reported as its own variant, and compared with Qwen3 F2 (F2−D thinking only, F4−D both, F4−F2 grammar only).
- **H4.** Computed for each nuisance factor (F3, F5, F6) separately and pooled; D is read with the point gate, R with the CI gate. **Primary = any held-out pair where that factor changed at least one model** (so for F3 this includes mixed pairs); the same test on all held-out pairs is also reported, and for F3 a both-native variant is also reported.
- **Size-changing pairs** (qwen25->qwen3, gemma2_2b->gemma3_4b) are tagged and reported separately everywhere.
- **Controls (PLAN.md section 6).** A/A (R vs R_AA): design mistral_v02, qwen2, qwen25; held-out llama31, phi35_mini, granite31 (3 + 3). Positive controls (Q2_K and no-description): mistral_v03, qwen25, llama31, granite32.
- **Folder names** assumed for F5 and R: F5, R, R_F3, R_F5, R_F6, R_unconstrained, R_AA, R_PC_Q2K, R_PC_NODESC.
- **Parser.** The Granite-3.0 `"tool"`-key gap stays unfixed in strict parsing; F7 lenient parsing repairs invalid backslash escapes only.

## 2026-10-08 — F4/R: Qwen3's generic-JSON grammar also blocks thinking

Confirmed directly (ran a real Qwen3 generation with and without the
`generic_json` grammar, identical prompt/temperature/seed): the grammar
forces the first emitted token to be `{`, so Qwen3's `<think>` block is
not truncated or malformed, it is **never emitted at all** --
`LlamaGrammar`'s constraint applies from the very first token, with no
allowance for a free-form preamble. Decision (asked explicitly, given
two real options -- leave as-is, or build a custom think-block-optional
GBNF grammar for Qwen3 only): **leave as-is**, run Qwen3 under the same
plain `generic_json` grammar as every other model. No per-model special
case in the F4 code path.

**Consequence, labeled explicitly so it isn't mixed into a clean
single-factor reading**: for every other model, F4 changes exactly one
thing from D (constrained decoding). **For Qwen3 specifically, F4
changes two things**: the JSON grammar itself, AND (as a structural
side effect of that grammar, not a separate config choice) thinking
gets blocked -- the same behavioral effect F2 deliberately produced via
`thinking: off`. Qwen3's F4 results will be reported separately with
this label (e.g. "Qwen3/F4 -- grammar + thinking blocked") rather than
folded into the other 15 models' "constrained decoding only" reading,
and compared against F2 specifically to help separate how much of
Qwen3's F4 effect is the grammar versus how much is the loss of
thinking.

**Protocol R** (PLAN.md section 7) also specifies generic-JSON
constrained decoding for its decision score. The exact same mechanism
applies: **Qwen3 under R will also have thinking blocked**, for the
same reason, and should carry the same two-things-changed label when R
is eventually run. Noting this now, before R exists, so it isn't
rediscovered as a surprise later.

**Quick test (5 tasks/suite, qwen3/mistral_v02/phi35_mini) -- grammar
loop/whitespace check**: parse rate 1.000 for all 3 models (the
grammar structurally guarantees valid JSON). **Truncation on the
grammar-constrained conditions (`baseline`/`schema_drift`) was 0/270
(0.000) for all 3 models** -- confirms the grammar does not cause
endless whitespace or looping before `max_tokens`. All observed
truncation was on `fault_reporting` (qwen3 26/45 = 0.578, phi35_mini
15/45 = 0.333, mistral_v02 0/45 = 0.000) -- that condition is **not**
grammar-constrained under any protocol (`runner.py` never passes
`response_schema` to its `client.generate()` call, since
`GENERIC_JSON_RESPONSE_SCHEMA`'s `{"name","arguments"}` shape doesn't
match `fault_reporting`'s `{"status","answer"}` envelope), so this
truncation is the same pre-existing unconstrained-rambling behavior
already documented for phi35_mini under D/F1 (`F1_report.md`), not a
new F4 effect. **Qwen3-specific check**: every one of its 90
`baseline`/`schema_drift` raw outputs starts with `{` and contains
zero occurrences of `<think>`/`</think>` anywhere in the text,
including inside any JSON string value -- 0/90 violations, confirmed
directly, not just inferred from the single example above.

## 2026-10-08 — F6 flip-rate reporting convention (set before any analysis)

F6 changed sampling for only 6 of 16 models (qwen2, qwen25, qwen3,
llama3, llama31, gemma3_4b) -- the other 10 have no official
recommendation and kept D's exact sampling values (confirmed directly:
18,000/18,000 of their sampled-trial records are byte-identical to D's,
zero mismatches). Any future F6 flip-rate analysis will be reported
two ways: **(a) on pairs where at least one model's sampling actually
changed (the 6 models above) -- this is the main F6 number**, and (b)
on all 48 pairs, for reference. Reporting only (b) would dilute any
real sampling effect with 10 models' worth of pairs that are
structurally guaranteed to show nothing (not because sampling has no
effect, but because sampling didn't change for them). Set here, before
any analysis, so the convention isn't chosen after seeing results.

## 2026-10-08 — F4 full-schema constrained decoding cut; generic-JSON only

PLAN.md's F4 factor lists two constrained-decoding levels:
`generic_json` (any valid JSON, no schema) and `full_schema` (the
model's actual tool schema baked into the grammar). Only `generic_json`
will be run. **Reasons**: (1) time -- a second full 48-run batch
(`full_schema`) would roughly double F4's wall-clock cost on top of
`generic_json`'s own ~48-run batch, and (2) `full_schema` changes what
`schema_drift` measures: baking the (possibly drifted) schema directly
into the decoding grammar would force every sampled token to already
conform to that schema, which would mechanically inflate
`args_valid_under_drift` regardless of the model's own drift-adaptation
behavior -- the grammar, not the model, would be doing the adapting.
`generic_json` (any valid JSON accepted, no schema steering) has no
such confound and is the more informative of the two for this
project's purposes.

## 2026-10-08 — F6 complete: 1 greedy mismatch, pre-existing GPU nondeterminism

All 48 F6 runs completed (11.4 hours). The greedy-record check (every
trial-0 record vs. D's matching record, 14,400 total) found **1
mismatch**: `qwen3/bfcl_simple`, task `bfcl-simple_python_279`,
`schema_drift` condition -- same prompt, same temperature (0.0) and
seed (1234) in both, byte-identical for most of the (truncated)
`<think>` block, then diverging into two different continuations.
Consistent with this project's own documented caveat (`README.md`:
"llama.cpp seeding is best-effort on GPU"), not caused by F6's
per-trial sampling mechanism (the other 14,399 greedy records all
matched exactly, confirming the mechanism correctly pins greedy to D's
own sampling values). Logged here per instruction ("report any
mismatch"); full detail in `analysis/plan/F6_report.md`. No harness
change made -- this is a pre-existing GPU-determinism property of the
backend, not something F6 introduced.

## 2026-10-07 — F6 (sampling preset): per-trial overrides added, table + plan before running

**Applied values table** (sampled trials 1/2 only; greedy, trial 0, always
uses D's own `top_p=0.95, top_k=40, min_p=0.05, repeat_penalty=1.0,
temperature=0.0` -- see mechanism below). Source for every row:
`docs/sampling_presets.md` (fetched live 2026-10-04 from each model's own
`generation_config.json` and/or model card; full citations there).

| Model | temperature | top_p | top_k | min_p | repeat_penalty | Recommendation? |
|---|---|---|---|---|---|---|
| gemma2_2b | 0.7 (D) | 0.95 (D) | 40 (D) | 0.05 (D) | 1.0 (D) | none -- keep D |
| gemma3_4b | 0.7 (D, no temp rec.) | 0.95 | 64 | 0.05 (D) | 1.0 (D) | partial (top_p/top_k only) |
| phi3_mini | 0.7 (D) | 0.95 (D) | 40 (D) | 0.05 (D) | 1.0 (D) | none -- keep D |
| qwen2 | 0.7 | 0.8 | 20 | 0.05 (D) | 1.05 | yes |
| llama31 | 0.6 | 0.9 | 40 (D) | 0.05 (D) | 1.0 (D) | partial (temp/top_p only) |
| mistral_v01 | 0.7 (D) | 0.95 (D) | 40 (D) | 0.05 (D) | 1.0 (D) | none -- keep D |
| qwen25 | 0.7 | 0.8 | 20 | 0.05 (D) | 1.05 | yes |
| mistral_v03 | 0.7 (D) | 0.95 (D) | 40 (D) | 0.05 (D) | 1.0 (D) | none -- keep D |
| llama3 | 0.6 | 0.9 | 40 (D) | 0.05 (D) | 1.0 (D) | partial (temp/top_p only) |
| granite32 | 0.7 (D) | 0.95 (D) | 40 (D) | 0.05 (D) | 1.0 (D) | none -- keep D |
| granite31 | 0.7 (D) | 0.95 (D) | 40 (D) | 0.05 (D) | 1.0 (D) | none -- keep D |
| granite30 | 0.7 (D) | 0.95 (D) | 40 (D) | 0.05 (D) | 1.0 (D) | none -- keep D |
| phi4_mini | 0.7 (D) | 0.95 (D) | 40 (D) | 0.05 (D) | 1.0 (D) | none -- keep D |
| mistral_v02 | 0.7 (D) | 0.95 (D) | 40 (D) | 0.05 (D) | 1.0 (D) | none -- keep D |
| phi35_mini | 0.7 (D) | 0.95 (D) | 40 (D) | 0.05 (D) | 1.0 (D) | none -- keep D |
| qwen3 (thinking stays on, default) | 0.6 | 0.95 (D, same) | 20 | 0.0 | 1.0 (D) | yes, thinking-ON values |

**Mechanism -- per-trial sampling overrides added, not a client-level
change**: `top_p`/`top_k`/`min_p`/`repeat_penalty` were previously set
once per model client and applied to every trial including greedy
(`upgradecanary/model/llama_cpp_client.py`). In llama.cpp's sampling
pipeline, `temperature=0` (greedy) bypasses `top_p`/`top_k`/`min_p`, but
**`repeat_penalty` is a logit-level penalty applied regardless of
temperature** -- a client-level change would have silently made Qwen2/
Qwen2.5's greedy trial (the only two models with a `repeat_penalty`
recommendation != D's `1.0`) diverge from D, breaking "change only one
thing." Added real per-trial overrides instead: `runner.build_trials()`
now accepts optional `trial_top_p`/`trial_top_k`/`trial_min_p`/
`trial_repeat_penalty` config lists (parallel to the existing
`trial_temperatures`/`trial_seeds`, same length-`trials` convention),
and `ModelClient.generate()` (both `LlamaCppClient` and `MockModelClient`)
now accepts `top_p`/`top_k`/`min_p`/`repeat_penalty` as optional per-call
kwargs, falling back to the client's own default when omitted. Every
existing D/F1/F2/F3 config has none of these keys, so `build_trials()`
produces trial dicts with no extra keys and every `client.generate()`
call site sends an empty `**sampling_kwargs` -- byte-identical to before
this change (confirmed: full test suite passes, 166/168 -- 2 pre-existing
skips -- plus 4 new tests added for this mechanism in `tests/
test_pilot.py`). `scripts/real_run_one.py`'s F6 branch sets `trial_top_p`
etc. to `[D_default, recommended, recommended]` per model from the table
above, and leaves the model-level `top_p`/`top_k`/`min_p`/`repeat_penalty`
keys unset (so the client's own default, used for any call with no
per-trial override, stays exactly D's).

**Quick test (5 tasks/suite, gemma2_2b/qwen2/llama31 -- one with no
recommendation, one with a repeat_penalty change, one without)**:
manifest's `run_factors.F6_sampling_preset` correctly reads
`"recommended"` for all 3; generated YAML configs show the exact
per-trial lists from the table above. **Greedy-record check**: compared
every trial-0 `raw_output` against the matching D record (by task_id +
condition) for all 3 models x all 3 suites (9 combinations, 15 greedy
records each) -- **0/135 mismatches**, including qwen2 (the
repeat_penalty=1.05 case), confirming the per-trial mechanism genuinely
isolates greedy from the sampling-preset change. **Sampled-trial sanity
check**: qwen2/synthetic's trial 1/2 raw outputs differ from D's on 3/30
records -- confirms the override is actually reaching generation, not a
silent no-op.

## 2026-10-07 — Granite-3.0 parser fix: verification follow-up, no GPU

Follow-up checks on the fix below, run before touching F6 (sampling
preset). All via `scripts/rescore_with_fixed_parser.py`, which replays
the real `evaluator.evaluate()`/`_safe_execute()` against each stored
`raw_output` with the current parser -- never re-generates model text.

**Correction to the 12/447 figure below**: that number came from a
regex match against one specific literal shape and undercounted the
fix's real scope. An exact, code-level rescore of granite30's F3 data
(all 3 suites, baseline + schema_drift records only -- fault_reporting
uses a separate, untouched extraction function) found **28 total
record-level diffs** out of 1800 tool-call-eligible records (1.6%): 10
on `synthetic`, 9 on `bfcl_simple`, 9 on `bfcl_multiple`. The gap: some
diffs recover via `function_name_alias` alone, but several recover via
`function_name_alias` *combined* with the pre-existing `parameters_alias`
-- a shape like `{"function": "<name string>", "parameters": {...}}`
with no `"name"` or `"arguments"` key at all, which was fully
unparseable before (name was `None`, so even the old `parameters_alias`
branch never triggered). The regex only caught the narrower
`{"type":"function","function":"<name>","arguments":{...}}` shape.
Confirmed raw model text is **100% byte-identical** between
`results_v2/F3/granite30/` and `results_v2/F3_rerun/granite30/`
(checked directly, 0/900 diffs on `synthetic`) -- every parse/score
change between them is attributable to the parser fix alone, nothing
about the model run differs.

**`results_v2/F3_rerun/granite30/` is now the official granite30 F3
result.** `results_v2/F3/granite30/` is kept on disk, unmodified, as
the pre-fix original for audit purposes only -- not used in any report
table going forward.

**phi4_mini F3 rescored in place** (no rerun needed -- deterministic,
same raw outputs, just reparsed): 4 diffs total (2 `synthetic`, 0
`bfcl_simple`, 2 `bfcl_multiple`), all `None -> correctly parsed`, same
`function_name_alias`/combined-`parameters_alias` mechanism as
granite30. Applied directly to `results_v2/F3/phi4_mini/*/
parsed_results.jsonl` and `summary.json` (raw_outputs.jsonl untouched).
New parse rates: `synthetic` 0.295 -> 0.298, `bfcl_simple` 0.212
(unchanged), `bfcl_multiple` 0.158 -> 0.162. Greedy-trial (trial_index
0) baseline accuracy unaffected on phi4_mini (all 4 diffs were sampled
trials); granite30's greedy accuracy did shift (`synthetic` 0.88 ->
0.90, `bfcl_multiple` 0.41 -> 0.42) since some of its 28 diffs land on
trial_index 0.

**D, F1, F2 rescored for comparison** (99 run directories: D's 48,
F1's 48, F2's 3) -- **zero diffs everywhere**, confirmed directly, not
assumed. Expected: all three use `prompt_format: shared`, whose prompt
explicitly instructs `{"name": ..., "arguments": {...}}`, so the
native-only `"function"`/`"type"` shapes this fix targets essentially
never occur there. Confirms the fix's blast radius is confined to F3's
native-template output, as designed.

**15-sample check on F3_rerun/granite30's remaining
`unrecognized_format` failures** (random sample, seed 42, 159 eligible
failures after the fix): 11/15 are correctly left unparsed -- prose
that states an intended tool call with the tool name only in free
text, never inside any JSON-like structure, plus one case where the
model fabricates a fake tool *response* rather than attempting a call.
**2/15 are unambiguous correct tool calls the parser still misses**,
using a third, different key convention: `{"tool": "<name>",
"arguments": {...}}`. **2/15 more are borderline**: Python
function-call syntax (e.g. `get_stock_price({"ticker": "GLOB"})`) --
unambiguous intent but not JSON, and consistent with this session's
established treatment of Python-syntax output elsewhere (phi4_mini's
F3 quick-test finding, 2026-10-06) as model non-compliance, not a
parser gap -- not counted as a parser miss.

**Decision (per explicit instruction: stop and fix again only if more
than 2/15 are correct calls)**: counted 2/15 using the `"tool"`-key
convention -- at, not over, the threshold. **No further parser change
will be made.** The `"tool"`-key gap is logged here as a known,
deliberately unfixed residual (asked the user directly given the exact
threshold and the Python-syntax ambiguity; decision confirmed: treat
as 2/15, proceed, do not extend the parser). This fix is closed.

**This fix was found and justified entirely from parse rates and
direct raw-output inspection -- never from any upgrade-verdict or
pair-difference computation** (none has been computed anywhere in this
project to date, per standing instruction). No more parser changes
will be made beyond what is logged in this entry and the one below it.

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
