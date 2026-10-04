# Engineering notes — PLAN.md section 10, step 1

What changed, item by item, and everything that turned out unclear or
impossible rather than a straightforward implementation. No model was run
for any of this work (per PLAN.md 10.1's own scope: "Engineering (no model
runs)"); PLAN.md 10.2 (smoke tests) is the next step and is **required**
before treating several pieces below as verified. 123/123 tests pass
(25 pre-existing + 98 new this batch); every default is unchanged unless a
config explicitly opts into a new key, so every historical run reproduces
byte-identically.

---

## 1. Native chat wrapping

`model.chat_wrapping: "legacy"` (default) | `"native"`. Native reads the
GGUF's own `tokenizer.chat_template` metadata and renders a plain
single-user-turn prompt with it. Built the formatter directly (not via
`create_chat_completion`) so extra render kwargs can be passed through —
this is what makes `model.thinking: "default"|"on"|"off"` controllable
even under native wrapping.

**How the old hand-built wrapper worked** (for the record, since native
wrapping replaces it): Mistral used `"[INST]\n{prompt}\n[/INST]"` (no
leading `<s>` — llama-cpp-python adds BOS automatically); Qwen used
`"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant"` (one
ChatML turn, assistant turn opened but not closed). Both were literal
`str.format()` substitutions with no real knowledge of the model's actual
template.

Three follow-up fixes, all verified by reading llama-cpp-python's actual
source (not assumed): double-BOS avoidance (pre-tokenize ourselves, pass
token IDs so `create_completion` skips its own auto-BOS; `special=True`
recognizes an already-embedded `"<s>"` without needing to strip it), stop
tokens from the model's own template (`eos_token` + a dedicated
`eot_token` when the model has one and it differs — Llama 3/Gemma/Phi-3
all do), and an explicit `add_generation_prompt=True`.

**Unclear / unverified — needs PLAN.md 10.2 smoke tests before trusting
this:**
- The entire native-wrapping code path (BOS handling, stop tokens,
  `enable_thinking`) has never been run against a real GGUF this batch.
- The Jinja variable name `enable_thinking` for Qwen3's template is a
  best-effort guess from public documentation, not independently
  confirmed against that GGUF's actual embedded template text.

## 2. F1–F6 config switches

F1 (`max_tokens`), F2 (`thinking`), F5 (`quant_level`, documentary) needed
no new mechanism — only explicit logging into `run_manifest.json`'s new
`run_factors` key (works for the mock provider too).

F3 (`prompt_format: "shared"|"native"`): native sends the bare question;
tool definitions go through a separate `tools=` list, built from this
project's internal schema via `upgradecanary/constrained.py`'s
`schema_to_openai_tool()`. F4 (`constrained_decoding: "off"|"generic_json"
|"full_schema"`): builds a JSON Schema and passes it to
`LlamaGrammar.from_json_schema`. F6 (`sampling_preset`): logging-only flag
— `docs/sampling_presets.md` has 4 of 14 models filled in from memory of
their public model cards (**not re-verified this session**); the other 10
are explicitly marked UNVERIFIED, not given invented numbers.

**Unclear / unverified:**
- `extract_tool_call()`'s parser only recognizes `{"name", "arguments"}`
  (or a `{"tool_call": {...}}` envelope). Some models' native tool-calling
  conventions use `"parameters"` instead of `"arguments"` (e.g. Meta's
  Llama-3.1 `<|python_tag|>` format, per `AUDIT.md`/`feasibility.md`). The
  parser was **not** extended to accept `"parameters"` as a synonym,
  because doing so without a real model's actual output to check against
  would be guessing at a fix for an unconfirmed problem. If F3 native mode
  shows suspiciously high `parse_failure` rates for a specific model at
  smoke-test time, this is the first thing to check.
- F4's `full_schema` level uses JSON Schema's `const` keyword to constrain
  the tool name. This is valid JSON Schema, but whether llama.cpp's
  grammar converter (`LlamaGrammar.from_json_schema`) actually supports
  `const` was not verified against a real call this session.

## 3. BFCL "multiple" category

New, fully separate functions in `bfcl.py` (`find_correct_function`,
`is_eligible_multiple`, `convert_multiple`, `generate_multiple`) — the
existing `simple_python` functions are untouched. `Task.candidate_schemas`
is additive. `build_prompt()` drifts only the correct tool; distractors
render verbatim (verified end-to-end).

**Found and resolved (with the user) while generating real data**: the
1200-char eligibility budget (built for one tool) rejects **all 200**
source records once every candidate is rendered — min 1250, median 2388
chars. Per explicit decision: generated with `max_prompt_chars=3500` → 109
eligible, 100 selected, fixed seed. **Documented limitation**: this biases
`BFCL-multiple-100` toward shorter multi-tool tasks relative to the full
source population (also recorded in `PLAN.md` section 3).

Alongside this, per the same decision round: `n_ctx` now defaults to 4096
and is logged unconditionally (`resolve_run_factors`); `check_context_
budget()` raises a clear error (never silently truncates) if
`prompt_tokens + max_tokens > n_ctx`, for both wrapping modes.

## 4. `fault_reporting` condition

New, additive condition. After an injected fault, the model gets ONE turn
telling it the outcome and must reply `{"status": "ok"|"failed"|
"incomplete", "answer": <string or null>}`. No real tool-call attempt is
scored first — this condition tests reporting behavior only.

**Judgment call, not something PLAN.md states explicitly — flagging for
confirmation**: PLAN.md says "Success = correct status AND no fabricated
answer when status should be `failed`" but does not specify which status
is "correct" per fault type, nor exactly what counts as fabrication. I
read `apply_fault()`'s actual implementation and found that none of the
four fault types (`timeout`/`tool_exception`/`empty_result`/
`partial_result`) ever surface a real data value — only an error message
(`partial_result`'s `missing_keys` is metadata about what's absent, not a
partial payload). From that, the simplest consistent rule:
`timeout`/`tool_exception`/`empty_result` → expected status `"failed"`;
`partial_result` → expected status `"incomplete"`; `answer` must be falsy
in **every** case (there's never legitimate content to report). This is a
reasonable reading, but it is my interpretation of an underspecified rule,
not a direct quote from PLAN.md — worth explicit sign-off before treating
`fault_reporting` results as final.

Also: no existing task's `condition_tags` ever included `"fault_reporting"`
(it didn't exist when they were generated). Rather than edit any frozen
task data file, the runner's condition_tags filter treats
`fault_reporting` as universally applicable.

## 5. Controls (A/A, positive controls)

A/A (seed variation) and positive control (a) (Q2_K) needed no new
mechanism — already expressible with existing config keys. Positive
control (b) ("prompt with tool descriptions removed") is new:
`prompt_format: "no_description"` recursively strips every key literally
named `"description"` from the rendered schema(s) (names/types/required
untouched); works on the internal schema shape, a BFCL-native doc, and a
BFCL-multiple candidate list.

**Not done, and why**: PLAN.md asks for A/A across ≥6 models × 3 suites
and positive controls across ≥4 models. Only two example configs exist
(both Qwen3-8B, the only model/suite combination with a working base
config to copy from). The other 14 models don't have a PLAN.md "D
protocol" base config yet — that's created in a *later* step per PLAN.md
10's own ordering ("Runs: D on all models first, ... then controls"), not
this engineering step. Positive control (a) (Q2_K) has no config at all,
because no Q2_K GGUF file exists locally — a multi-GB download, not
fetched without asking first per this task's standing instruction.
`docs/controls.md` has the exact pattern to apply once those two
prerequisites exist.

## 6. Gates

`upgradecanary/gates.py`: `point_gate`, `cluster_bootstrap_ci` (task-level
cluster bootstrap, matches this project's existing `[250, 9749]`
percentile-index convention for 10,000 reps), `ci_gate`, and a `decide()`
convenience wrapper. **Not** wired into the existing `scripts/*.py` or
`analysis/audit/*.py` — those already work and are already audited;
PLAN.md doesn't ask for a retroactive refactor. This module is for new
analysis going forward.

## 7. Idempotency

Fresh repo-wide sweep: no `open(...,"a")` append-mode writes anywhere, and
`intent_strictness.py` (fixed in an earlier session) remains the only
script that ever reads back its own output file. Every generator writes
via one full overwrite. No change needed.

## 8. Tests

123/123 pass (25 pre-existing + 98 new this batch): `test_native_chat.py`
(16), `test_plan_factors.py` (29, incl. the two new config-regression
tests), `test_bfcl_multiple.py` (19), `test_fault_reporting.py` (24),
`test_gates.py` (22). `generate_multiple()` itself is tested against the
real `external/gorilla` checkout (mirroring the existing `generate()`
test's pattern), including a regression guard pinning down the documented
"default budget selects zero" finding.

---

## Everything unclear or impossible, in one place

1. **Native chat wrapping is entirely unverified against a real model.**
   Smoke tests (PLAN.md 10.2) must run before trusting BOS/stop/thinking
   handling for any real model.
2. **`enable_thinking`'s exact template variable name is a guess**, not
   confirmed against Qwen3's actual embedded template text.
3. **F3 native mode may fail to parse some models' native tool-call
   format** (e.g. a `"parameters"` key instead of `"arguments"`) — not
   fixed speculatively; check at smoke-test time if `parse_failure` spikes.
4. **F4 `full_schema`'s use of JSON Schema `const`** is unverified against
   llama.cpp's grammar converter.
5. **`fault_reporting`'s status-mapping and fabrication rule are my
   interpretation** of an underspecified PLAN.md sentence, not a direct
   quote — flagging for explicit confirmation.
6. **Sampling presets: only 4 of 14 models have a (session-unverified)
   recommended value**; the other 10 are UNVERIFIED, not invented.
7. **A/A (6×3) and positive-control (4 models) matrices are not
   instantiated** — pending D-protocol base configs for the other 14
   models (a later PLAN.md step) and, for Q2_K, a download decision.
8. **BFCL-multiple-100 is biased toward shorter multi-tool tasks** (3500-
   char eligibility budget, 109/200 source records eligible) — also in
   `PLAN.md` section 3.
