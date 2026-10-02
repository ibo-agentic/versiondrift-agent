# UpgradeCanary — Reviewer Audit

Scope: verify whether the main results come from real robustness differences
or from harness/setup artifacts (prompting, decoding, quantization, scoring).
**No code, configs, or result files were modified. No models were run.**
All findings are from reading the existing source (`upgradecanary/`,
`configs/`, `scripts/`), the existing dated log (`docs/experiment_log.md`),
`git log`, and cheap read-only analyses over the existing
`results/*/parsed_results.jsonl` / `raw_outputs.jsonl` logs. New analysis
code lives in `analysis/audit/` (`common.py`, `failure_breakdown.py`,
`fault_mechanics.py`, `ceiling_effects.py`, `random_baseline_check.py`,
`ranking_check.py`, `prefix_vs_postfix.py`) and can be rerun with
`python analysis/audit/<script>.py`.

## Summary verdict table

| Q | Topic | Verdict |
|---|---|---|
| A1 | Tool-call elicitation format | **CONFOUND RISK** |
| A2 | Rendered prompts shown | OK |
| A3 | Output parsing / markdown / think tags | **CONFOUND RISK** |
| B4 | Qwen3 thinking mode on/off | **BUG** (never controlled) |
| B5 | Decoding settings per model | OK (identical where set) |
| B6 | Qwen3 truncation / leftover `<think>` | **CONFOUND RISK** (confirmed, large) |
| C7 | GGUF/quant/backend version | **CONFOUND RISK** (minor; backend version not logged per run) |
| D8 | Failure breakdown table | OK (computed below) |
| D9 | % of failures that are parse/format | **CONFOUND RISK** (Qwen3: 67–69%) |
| E10 | Fault-trial mechanics | OK (described, verified) |
| E11 | Can fault leave score unchanged if 1st call correct | **BUG** (design-level) |
| E12 | Baseline vs fault per-task flips | OK (computed below) |
| E13 | Real failing fault examples | OK (computed below; reveals E11) |
| F14 | Does model see drifted schema | OK now (was BUG, fixed, see H) |
| F15 | Correct behavior per drift type | OK (documented in code) |
| G16 | Intent-match implementation / human validation | **CONFOUND RISK** (no human validation; NOT FOUND) |
| H17 | Git history of the "corrected" BFCL fix | OK (documented; was BUG, now fixed) |
| I18 | Ceiling effects | **CONFOUND RISK** (synthetic baseline: 96% ceiling) |
| J19 | Canary selection methodology | OK (leave-one-out, no leakage in validated pipeline) |
| J20 | Circularity check | OK for published LOUO numbers; **CONFOUND RISK** (disclosed) for the in-distribution exploratory script |
| J21 | Number of upgrade pairs | OK (4 per suite, 8 total) |
| J22 | Calibration fit sample size | **CONFOUND RISK** (n=1 for Qwen→Mistral direction) |
| J23 | Random-subset baseline (1000 reps, k=30) | OK (computed below; reveals risk for borderline-neutral truths) |
| K24 | Ranking/gap consistency across conditions | **CONFOUND RISK** (BFCL baseline already significant for all 4 pairs) |

## Top 5 risks to the paper's main claims (ranked)

1. **Qwen3 thinking-mode truncation under a shared `max_tokens=256` budget** inflates Qwen3's apparent robustness regression. 67–69% of all of Qwen3's failures (both suites) are parse/format failures, and ~80–90% of those are an unclosed `<think>` block (hit the token limit before emitting JSON). This directly threatens the "Qwen2.5→Qwen3 is a robustness downgrade" claim, which is one of only two cross-family upgrade results in the study.
2. **Runtime-fault scoring does not test fault handling for most records.** For the four retryable fault types, `apply_fault` unconditionally fails the first attempt regardless of call correctness, then the retry runs with the fault removed — so the final score mostly measures "can the model repeat a correct call a second time," not fault handling. For `stale_result` (~25% of fault records), the executor always returns `ok: True`, so this fault type can never change the score. `runtime_fault` is 50% of the primary "stress" metric.
3. **All 5 models share one hand-rolled JSON-in-prompt tool format**, not each model's native tool-calling chat template (no Mistral `[AVAILABLE_TOOLS]`, no Qwen tool-schema block). The study measures compliance with an ad hoc instruction format, not native/deployed tool-calling behavior — a possible confound for any cross-model or cross-version claim.
4. **On the corrected BFCL suite, the clean baseline condition is already statistically significant and same-signed as drift/fault for all four upgrade decisions** (task-cluster bootstrap CIs exclude zero). This weakens the paper's central claim that upgrade robustness regressions are "invisible to clean-task accuracy" — that claim holds cleanly on the synthetic suite but not on the public suite.
5. **The BFCL drift-prompt bug (fixed 2026-10-01) changed schema_drift scores by +0.43 to +0.71** (e.g., Mistral v0.1 0.223→0.690) and flipped a decision label (v0.1→v0.3 neutral→beneficial). The fix is well-documented and pre-fix runs are excluded from all current claims, but the size of this bug is a strong prior that another undiscovered scoring subtlety (e.g., risk #2) is plausible and warrants independent re-verification before submission.

---

## A. Tool-call prompting

### A1. How is the tool call elicited — native chat template or shared JSON-in-prompt?

**Answer: one shared JSON-in-prompt format for all 5 models. No native tool-calling template is used for any model.**

`build_prompt()` in [upgradecanary/runner.py:42-59](upgradecanary/runner.py#L42-L59) builds a single text block: a fixed instruction string + a JSON dump of the tool schema + "Reply with ONLY a single JSON object..." + the question. This is identical in structure for Mistral v0.1/v0.2/v0.3 and Qwen2.5/Qwen3 — no `[AVAILABLE_TOOLS]`/`[TOOL_CALLS]` (Mistral v0.3's native function-calling format) and no Qwen `<tools>...</tools>` / `<tool_call>` template are used anywhere in the codebase (confirmed by `grep -ri "AVAILABLE_TOOLS\|tool_call>" upgradecanary/` — no matches).

What *does* differ per model is the outer chat-turn wrapper, applied only inside `LlamaCppClient.generate()` ([upgradecanary/model/llama_cpp_client.py:78-79](upgradecanary/model/llama_cpp_client.py#L78-L79)) via the config's `prompt_template` string:
- Mistral: `"[INST]\n{prompt}\n[/INST]"` ([configs/real_trials_itlwas_v0.1.yaml:28](configs/real_trials_itlwas_v0.1.yaml#L28), same in v0.2/v0.3/BFCL configs)
- Qwen2.5 and Qwen3: `"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant"` ([configs/real_trials_qwen25.yaml:28](configs/real_trials_qwen25.yaml#L28), [configs/real_trials_qwen3.yaml:28](configs/real_trials_qwen3.yaml#L28))

This wraps the *entire* generic JSON-in-prompt text in the right chat delimiters so the base chat model responds in-turn — it is not the same as using the model's dedicated tool-calling schema/grammar.

**Verdict: CONFOUND RISK.** This is a defensible, deliberate design choice for a controlled study (one fixed protocol applied identically to all models removes template-specific variance), but it means no result in this study reflects how any of these models perform through their native/deployed tool-calling interface. This should be stated explicitly as a scope limitation, and claims should not be phrased as being about "tool-calling ability" in general — only about compliance with this specific prompting protocol.

### A2. Fully-rendered baseline prompt per model

The internal `prompt` field logged in `raw_outputs.jsonl` is **before** `prompt_template` wrapping (the wrapping happens only inside the client, see A1); the prompt actually sent to the model is `prompt_template.format(prompt=prompt)`.

**Mistral v0.1** (`results/upgradecanary-real-trials-itlwas-v0.1_seed1234_20260929T120210Z/raw_outputs.jsonl`, task-001 baseline trial 0), logged prompt:
```
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
```
Actually sent to the model (per `configs/real_trials_itlwas_v0.1.yaml:28`): the above wrapped as `[INST]\n<above>\n[/INST]`. Raw output: `{"name": "get_weather", "arguments": {"city": "Berlin", "unit": "celsius"}}`.

**Mistral v0.2 / v0.3**: identical prompt body (same task, same `build_prompt`); only the GGUF file differs. Confirmed via `results/upgradecanary-real-trials-itlwas-v0.{2,3}_.../raw_outputs.jsonl`, task-001 baseline trial 0 — same output.

**Qwen2.5**: same prompt body, wrapped as `<|im_start|>user\n<body><|im_end|>\n<|im_start|>assistant` per `configs/real_trials_qwen25.yaml:28`. Confirmed in `results/upgradecanary-real-trials-qwen25_seed1234_20260929T222007Z/raw_outputs.jsonl`.

**Qwen3**: same body/wrapper; raw output (`results/upgradecanary-real-trials-qwen3_seed1234_20260929T230135Z/raw_outputs.jsonl`, task-001 baseline trial 0):
```
.<think>
Okay, the user is asking for the current weather in Berlin with the temperature in Celsius. Let me check the available tools. There's a get_weather tool that requires city and unit. The city here is Berlin, and the unit should be celsius as specified. So I need to call get_weather with those parameters. Just make sure the arguments are correctly formatted as JSON.
</think>

{"name": "get_weather", "arguments": {"city": "Berlin", "unit": "celsius"}}
```
(see B4/B6 — thinking mode was never disabled).

For BFCL-derived tasks the prompt differs in schema shape (native BFCL function-document form, via `to_native_doc`, [upgradecanary/bfcl.py:132-169](upgradecanary/bfcl.py#L132-L169)); example (`results/upgradecanary-bfcl-trials-itlwas-v0.3_seed1234_20261001T160749Z/raw_outputs.jsonl`, baseline trial 0):
```
Available tool schema:
{
  "tools": [{
    "description": "Calculate the area of a triangle...",
    "name": "calculate_triangle_area",
    "parameters": {"properties": {"base": {...}, "height": {...}, "unit": {...}}, "required": ["base","height"], "type": "dict"}
  }]
}
```
Same instruction/question/answer scaffold otherwise.

**Verdict: OK** (evidence provided; this is a documentation question, not a defect).

### A3. Output parsing — extra text, markdown fences, `<think>` tags

`extract_tool_call()` ([upgradecanary/parsing.py:14-44](upgradecanary/parsing.py#L14-L44)) scans the raw text left-to-right for every `{` character and attempts `json.JSONDecoder().raw_decode()` from that position; the **first** position that yields a dict with `name: str` and `arguments: dict` (directly, or inside a `tool_call` envelope) wins. It does not special-case markdown fences or `<think>...</think>` — it works for them only incidentally, because fenced/thought text rarely contains a top-level `{...}` that happens to parse as a dict with those two keys.

This is **not robust against thinking-mode content that itself contains a brace-delimited object before the intended tool call**, and it is **not robust against truncation**: if generation is cut off (hits `max_tokens` or the `stop` sequence) before a complete, parseable `{` object appears, `extract_tool_call` returns `None` regardless of why the output is incomplete — the parser cannot distinguish "model never produced valid JSON" from "model was still thinking when the token budget ran out." Verified empirically in B6: ~90% (synthetic) / ~79% (BFCL) of all Qwen3 parse failures have an opened-but-unclosed `<think>` tag in the raw output (`analysis/audit/failure_breakdown.py` + ad hoc check against `raw_outputs.jsonl`, see B6 below).

**Verdict: CONFOUND RISK.** The parser's "first valid JSON object wins" design is reasonable for well-behaved models but interacts badly with a reasoning model that emits a long `<think>` prefix under a fixed token budget (see B/top risk #1).

---

## B. Qwen3 thinking mode + decoding

### B4. Is Qwen3 thinking mode on or off?

**Answer: ON (the default), and it is never explicitly controlled anywhere in this codebase.**

`grep -rni "think" upgradecanary/ configs/ docs/` returns **no matches** — there is no `enable_thinking`, no `/no_think` directive, no system prompt suppressing it, and no mention of thinking mode in any config or doc. `configs/real_trials_qwen3.yaml` and `configs/bfcl_trials_qwen3.yaml` use the raw-completion ChatML wrapper (`<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant`, [configs/real_trials_qwen3.yaml:28](configs/real_trials_qwen3.yaml#L28)) via `llama_cpp.Llama.create_completion` (a low-level text-completion call, not a chat-template-aware helper), so nothing in the pipeline could have disabled thinking even if intended.

Direct evidence: **900/900** records in `results/upgradecanary-real-trials-qwen3_seed1234_20260929T230135Z/raw_outputs.jsonl` contain the literal string `<think>` (checked with a one-off script against the raw outputs). Qwen2.5 raw outputs contain `<think>` in **0/900** records in both the synthetic and BFCL runs — confirming this is Qwen3-specific, consistent with Qwen3 being a hybrid reasoning model that thinks by default.

**Verdict: BUG** (an unintentional, uncontrolled default, not a deliberate experimental condition) — this is not stated anywhere as a design choice in `docs/protocol.md` or `docs/model_manifest.md`.

### B5. Exact decoding settings per model/trial

From `build_trials()` ([upgradecanary/runner.py:81-102](upgradecanary/runner.py#L81-L102)) and every `real_trials_*` / `bfcl_trials_*` config (identical across all 5 models on this point):

| Trial | temperature | seed |
|---|---|---|
| 0 (greedy, reproducibility anchor) | 0.0 | 1234 |
| 1 (sampled) | 0.7 | 1235 |
| 2 (sampled) | 0.7 | 1236 |

`max_tokens: 256` for every model, every suite (`configs/real_trials_itlwas_v0.{1,2,3}.yaml`, `real_trials_qwen{25,3}.yaml`, `bfcl_trials_*.yaml` — all set `max_tokens: 256`).

`top_p`, `top_k`, `repeat_penalty` are **not set in any config** and are **not passed** by `LlamaCppClient.generate()` ([upgradecanary/model/llama_cpp_client.py:82-89](upgradecanary/model/llama_cpp_client.py#L82-L89) only forwards `prompt`, `temperature`, `max_tokens`, `seed`, `stop`). They therefore fall back to the installed `llama-cpp-python`'s library defaults: `top_p=0.95`, `min_p=0.05`, `repeat_penalty=1.0`, `top_k=40` (confirmed by reading `create_completion`'s signature in the installed package, `.venv/Lib/site-packages/llama_cpp/llama.py:1815-1841`, version `llama_cpp_python==0.3.35` per `.venv/Lib/site-packages/llama_cpp_python-0.3.35.dist-info`). These defaults are identical for all 5 models (nothing model-specific overrides them), so this specific setting is **not** a cross-model confound — but it is also not stated or pinned anywhere in `docs/protocol.md` or `docs/model_manifest.md`, so there is no record of what version's defaults were actually in effect at run time (see C7).

**Verdict: OK** for what is actually configured (genuinely identical across models); the unlogged implicit decoding defaults (top_p/top_k/repeat_penalty, backend version) are a minor reproducibility gap, covered under C7.

### B6. Are Qwen3 failures caused by truncation or leftover `<think>` content?

**Yes, confirmed and quantified** (`analysis/audit/failure_breakdown.py` output):

| Run | parse failures | of which: unclosed `<think>` |
|---|---|---|
| synthetic Qwen3 | 31 / 900 | 28 (90%) |
| BFCL Qwen3 | 148 / 900 | 117 (79%) |

Per-condition breakdown (ad hoc script against `raw_outputs.jsonl`/`parsed_results.jsonl`):

| Suite | condition | parse_fail | unclosed think |
|---|---|---|---|
| synthetic | baseline | 1 | 1 |
| synthetic | schema_drift | 28 | 26 |
| synthetic | runtime_fault | 2 | 1 |
| BFCL | baseline | 34 | 24 |
| BFCL | schema_drift | 76 | 65 |
| BFCL | runtime_fault | 38 | 28 |

On the BFCL suite, even the clean `baseline` condition loses 24/300 (8%) of its records to thinking-mode truncation, and `schema_drift` loses 65/300 (21.7%) — BFCL prompts are longer (native BFCL function documents are more verbose than the synthetic schemas), leaving less of the 256-token budget for both a `<think>` block and the final JSON. Qwen2.5 (no thinking, same 256-token budget, same prompts) has **0** parse failures with unclosed-think markers on either suite (it has no think tags at all).

**Verdict: CONFOUND RISK, and the most severe one found in this audit** (see Top 5, #1). This directly inflates Qwen3's measured failure rate on both suites, and inflates it *more* on BFCL (longer prompts) and *more* under `schema_drift` (longest prompts, since BFCL renders a full native-style function document) — both conditions where the paper's core "Qwen3 is a robustness downgrade" claim rests on Qwen3 scoring lower than Qwen2.5.

---

## C. Quantization / runtime

### C7. GGUF file, quant type, source, inference backend + version per model

From `docs/model_manifest.md` §2–3 (canonical matched set):

| Model | File | Quant | SHA-256 | Source |
|---|---|---|---|---|
| Mistral v0.1 | `models/itlwas/mistral-7b-instruct-v0.1-q4_k_m.gguf` | Q4_K_M | `1af6bf966c4113f0cb5de7af42f38572075c9798bc16e6c72faee051bd7d6d33` | itlwas/Mistral-7B-Instruct-v0.1-Q4_K_M-GGUF |
| Mistral v0.2 | `models/itlwas/mistral-7b-instruct-v0.2-q4_k_m.gguf` | Q4_K_M | `aaae8abe274e1521d5aa80bf32cf18b408fc44b9d6869acbdc815440296d275e` | itlwas/Mistral-7B-Instruct-v0.2-Q4_K_M-GGUF |
| Mistral v0.3 | `models/itlwas/mistral-7b-instruct-v0.3-q4_k_m.gguf` | Q4_K_M | `9a643d2815e427e6622c3ef7f284af942bd0c58463a7c94f726fa882f487a404` | bartowski/Mistral-7B-Instruct-v0.3-GGUF (itlwas build) |
| Qwen2.5-7B | `models/qwen/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf` | Q4_K_M (split, part 1) | `dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db` | Qwen/Qwen2.5-7B-Instruct-GGUF |
| Qwen3-8B | `models/qwen/Qwen3-8B-Q4_K_M.gguf` | Q4_K_M | `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785` | Qwen/Qwen3-8B-GGUF |

All five use the same quantizer level (Q4_K_M) — this is not a confound across the canonical matched set.

Backend: `llama-cpp-python` via `upgradecanary/model/llama_cpp_client.py`. The **currently installed** version in this repo's `.venv` is `0.3.35` (`.venv/Lib/site-packages/llama_cpp_python-0.3.35.dist-info`). However, **`run_manifest.json` does not record the llama-cpp-python version** — it only logs `package_version` (the `upgradecanary` package itself, `"0.1.0"`), `python`, and `platform` (verified against `results/upgradecanary-real-trials-qwen3_seed1234_20260929T230135Z/run_manifest.json`). Runs were produced 2026-09-29 to 2026-10-01; whether `0.3.35` (or a different version with different llama.cpp-side defaults/sampling behavior) was installed at that time **cannot be confirmed from the logs**.

**Verdict: CONFOUND RISK (minor).** Quantizer/source/hash are fully pinned and identical across the matched set (good); the exact backend version actually used per run is **NOT FOUND** in any artifact and should be added to `run_manifest.json` before further runs.

---

## D. Failure breakdown (computed from existing logs)

Full table (`analysis/audit/failure_breakdown.py`, exclusive bucket priority: parse → wrong_tool_name → intent_mismatch → invalid_under_drift → executor_failure → other; `other` is 0 everywhere, confirming the bucketing is exhaustive and consistent with the scoring formula in `upgradecanary/evaluator.py:95-101`):

| suite | model | cond | n | fail | parse | wrong_tool | intent | invalid_drift | exec_fail |
|---|---|---|---|---|---|---|---|---|---|
| synthetic | Mistral v0.1 | baseline | 300 | 0 | 0 | 0 | 0 | 0 | 0 |
| synthetic | Mistral v0.1 | schema_drift | 300 | 3 | 0 | 0 | 2 | 1 | 0 |
| synthetic | Mistral v0.1 | runtime_fault | 300 | 0 | 0 | 0 | 0 | 0 | 0 |
| synthetic | Mistral v0.2 | baseline | 300 | 0 | 0 | 0 | 0 | 0 | 0 |
| synthetic | Mistral v0.2 | schema_drift | 300 | 31 | 0 | 0 | 19 | 12 | 0 |
| synthetic | Mistral v0.2 | runtime_fault | 300 | 73 | 0 | 0 | 2 | 0 | 71 |
| synthetic | Mistral v0.3 | baseline | 300 | 9 | 0 | 0 | 9 | 0 | 0 |
| synthetic | Mistral v0.3 | schema_drift | 300 | 21 | 0 | 0 | 19 | 2 | 0 |
| synthetic | Mistral v0.3 | runtime_fault | 300 | 9 | 0 | 0 | 9 | 0 | 0 |
| synthetic | Qwen2.5 | baseline | 300 | 0 | 0 | 0 | 0 | 0 | 0 |
| synthetic | Qwen2.5 | schema_drift | 300 | 19 | 0 | 0 | 19 | 0 | 0 |
| synthetic | Qwen2.5 | runtime_fault | 300 | 0 | 0 | 0 | 0 | 0 | 0 |
| synthetic | Qwen3 | baseline | 300 | 1 | 1 | 0 | 0 | 0 | 0 |
| synthetic | Qwen3 | schema_drift | 300 | 28 | 28 | 0 | 0 | 0 | 0 |
| synthetic | Qwen3 | runtime_fault | 300 | 16 | 2 | 0 | 0 | 0 | 14 |
| BFCL | Mistral v0.1 | baseline | 300 | 33 | 6 | 0 | 27 | 0 | 0 |
| BFCL | Mistral v0.1 | schema_drift | 300 | 93 | 5 | 0 | 39 | 49 | 0 |
| BFCL | Mistral v0.1 | runtime_fault | 300 | 35 | 5 | 0 | 28 | 0 | 2 |
| BFCL | Mistral v0.2 | baseline | 300 | 58 | 6 | 3 | 49 | 0 | 0 |
| BFCL | Mistral v0.2 | schema_drift | 300 | 113 | 7 | 3 | 69 | 34 | 0 |
| BFCL | Mistral v0.2 | runtime_fault | 300 | 84 | 4 | 3 | 51 | 0 | 26 |
| BFCL | Mistral v0.3 | baseline | 300 | 17 | 0 | 0 | 17 | 0 | 0 |
| BFCL | Mistral v0.3 | schema_drift | 300 | 67 | 0 | 0 | 33 | 34 | 0 |
| BFCL | Mistral v0.3 | runtime_fault | 300 | 18 | 0 | 0 | 18 | 0 | 0 |
| BFCL | Qwen2.5 | baseline | 300 | 15 | 0 | 0 | 15 | 0 | 0 |
| BFCL | Qwen2.5 | schema_drift | 300 | 23 | 0 | 0 | 20 | 3 | 0 |
| BFCL | Qwen2.5 | runtime_fault | 300 | 15 | 0 | 0 | 15 | 0 | 0 |
| BFCL | Qwen3 | baseline | 300 | 45 | 34 | 0 | 11 | 0 | 0 |
| BFCL | Qwen3 | schema_drift | 300 | 92 | 76 | 0 | 16 | 0 | 0 |
| BFCL | Qwen3 | runtime_fault | 300 | 84 | 38 | 0 | 14 | 0 | 32 |

### D9. % of all failures that are parse/format failures, per model

| suite | model | total failures | parse failures | % |
|---|---|---|---|---|
| synthetic | Mistral v0.1 | 3 | 0 | 0.0% |
| synthetic | Mistral v0.2 | 104 | 0 | 0.0% |
| synthetic | Mistral v0.3 | 39 | 0 | 0.0% |
| synthetic | Qwen2.5 | 19 | 0 | 0.0% |
| synthetic | **Qwen3** | 45 | 31 | **68.9%** |
| BFCL | Mistral v0.1 | 161 | 16 | 9.9% |
| BFCL | Mistral v0.2 | 255 | 17 | 6.7% |
| BFCL | Mistral v0.3 | 102 | 0 | 0.0% |
| BFCL | Qwen2.5 | 53 | 0 | 0.0% |
| BFCL | **Qwen3** | 221 | 148 | **67.0%** |

**Verdict: CONFOUND RISK.** Two-thirds of all Qwen3 failures, on both suites, are parse/format failures (overwhelmingly thinking-mode truncation, see B6) rather than wrong-tool-name/intent/validity/execution failures. "Robustness" differences for Qwen3 specifically should be re-examined after fixing the decoding setup (disable thinking or raise `max_tokens`), since a large share of its measured degradation is not a semantic/robustness failure mode at all.

---

## E. Runtime fault scoring

### E10. Exact fault-trial mechanics

From `upgradecanary/runner.py:137-217` and `upgradecanary/perturbations/runtime_faults.py:39-80` / `upgradecanary/tools.py:121-139`:

1. A fault type is chosen once per `(task, condition)` — **not per trial** — from a seeded RNG (`rng_for(seed, task.task_id, condition)`, [runner.py:142](upgradecanary/runner.py#L142), [runner.py:150-151](upgradecanary/runner.py#L150-L151)), so all 3 trials of a given task share the same fault type.
2. The model generates its first attempt against the normal prompt (the fault is **not shown to the model in the prompt** — it is injected purely at the executor level, after generation).
3. `execute()` ([upgradecanary/tools.py:121-139](upgradecanary/tools.py#L121-L139)) first runs `validate_call` and (if valid) the canned handler, **then** wraps the handler's successful result with `apply_fault()` ([upgradecanary/perturbations/runtime_faults.py:39-80](upgradecanary/perturbations/runtime_faults.py#L39-L80)).
4. `apply_fault` unconditionally returns `ok: False` for `timeout`, `tool_exception`, `empty_result`, `partial_result` (lines 43-69) — **regardless of whether the handler's result was correct** — and unconditionally returns `ok: True` (just annotated `stale: True`) for `stale_result` (lines 72-79).
5. If the fault is one of the four retryable types (`RETRYABLE`, line 16) and the first attempt's `exec_result.ok` is `False`, the runner issues **one retry** ([runner.py:174-204](upgradecanary/runner.py#L174-L204)): a new prompt is built (original prompt + `"Your previous tool call failed: {feedback}"` + "Provide a corrected JSON answer:"), and the retry is executed with **`fault=None`** ([runner.py:195-198](upgradecanary/runner.py#L195-L198): `_safe_execute(retry_parsed, schema, drift, None, strict, ...)`) — i.e., the fault is not reapplied on retry.
6. The final `exec_result.ok` (and hence `executor_ok`) is the **retry's** outcome when a retry happened ([runner.py:199-204](upgradecanary/runner.py#L199-L204): `exec_result = {"first_attempt": ..., "retry": ..., "ok": retry_exec.get("ok", False)}`), but the other four metric components (`parse_ok`, `tool_name_ok`, `args_intent_match`, `args_valid_under_drift`) are computed from the **first attempt's** parsed call only ([runner.py:167](upgradecanary/runner.py#L167) `parsed = extract_tool_call(raw)`, carried unchanged into [runner.py:206-217](upgradecanary/runner.py#L206-L217) `metrics = evaluate(..., parsed, exec_result, ...)`). This is an asymmetry: four of five score components reflect attempt 1, one reflects attempt 2 (when a retry occurred).

**Verdict: OK** as a factual description (this is what the code does); the implications are covered in E11.

### E11. Can the fault ever change the score if the model's first tool call is correct?

**Yes and no, depending on fault type — and this substantially explains the reviewer's "fault score ≈ baseline score" observation.**

- **`stale_result`** (not retryable): `apply_fault` always returns `ok: True`. If the model's first call was correct, the score is **always** 1 regardless of the fault — the fault literally cannot change the outcome. Verified empirically: `stale_result` mean score is 0.97–1.00 for every one of the 5 models on the synthetic suite (`analysis/audit/fault_mechanics.py`), i.e., indistinguishable from each model's own baseline-level correctness. `stale_result` is ~25% of all `runtime_fault` records (75/300 for the synthetic Mistral runs).
- **The four retryable types**: `apply_fault` always flips the first attempt to `ok: False`, so a retry is **always** triggered (confirmed: `analysis/audit/fault_mechanics.py` shows "retried" count equals the full record count for every retryable fault type, every model). The retry runs with no fault, so whether the final score is 1 depends entirely on whether the **second** generation (same temperature/seed re-supplied, but a longer, different prompt) reproduces a valid, correctly-parsed call. At temperature 0.0 this is highly likely if the model is confident, which is exactly what makes "fault score ≈ baseline score" true for strong models (Mistral v0.1, v0.3, Qwen2.5 all score 1.000 on 3 of 4 retryable types in the synthetic suite).

So: for ~1/4 of fault records the fault **cannot** change a correct score; for the other ~3/4, the fault forces a retry whose success is governed mostly by second-attempt reproducibility (a different, weaker signal than "can the agent detect and recover from a degraded backend").

**Verdict: BUG (design-level).** As implemented, `runtime_fault` does not test fault *detection* or *handling* in the sense the paper's framing implies (e.g., staleness is never actually tested — see `docs/protocol.md`'s own admission that "detecting staleness needs a real model and is left for later phases," which is more consequential than stated, since it means the 25% `stale_result` share of this condition carries zero fault-specific signal by construction). Given `runtime_fault` is one of the two components of the primary "stress" metric, this should be flagged prominently as a methodological limitation, and ideally fixed (e.g., require the retry to acknowledge/explain the fault, or score staleness detection) before treating `runtime_fault` deltas as evidence of "fault-handling robustness" rather than "second-attempt reproducibility plus baseline correctness."

### E12. Baseline vs fault outcome per task, per model — flip counts

(`analysis/audit/fault_mechanics.py`, paired per `(task_id, trial_index)`)

**Synthetic:**

| model | pass→fail | fail→pass | both pass | both fail |
|---|---|---|---|---|
| Mistral v0.1 | 0 | 0 | 300 | 0 |
| Mistral v0.2 | 73 | 0 | 227 | 0 |
| Mistral v0.3 | 0 | 0 | 291 | 9 |
| Qwen2.5 | 0 | 0 | 300 | 0 |
| Qwen3 | 15 | 0 | 284 | 1 |

**BFCL:**

| model | pass→fail | fail→pass | both pass | both fail |
|---|---|---|---|---|
| Mistral v0.1 | 3 | 1 | 264 | 32 |
| Mistral v0.2 | 30 | 4 | 212 | 54 |
| Mistral v0.3 | 1 | 0 | 282 | 17 |
| Qwen2.5 | 0 | 0 | 285 | 15 |
| Qwen3 | 50 | 11 | 205 | 34 |

Mistral v0.2 and Qwen3 are the only two models with a substantial `pass→fail` count under fault on the synthetic suite, consistent with D8's finding that their `runtime_fault` failures are dominated by `executor_failure` (Mistral v0.2, retry-reproducibility failures) and parse failures (Qwen3, thinking truncation on the longer retry prompt), not fault-specific semantics.

### E13. Three real failing fault examples each, Mistral v0.2 and Qwen3

**Mistral v0.2**, task-001, 3 of its `partial_result` fault trials (`results/upgradecanary-real-trials-itlwas-v0.2_seed1234_20260929T121701Z/`):
- First attempt: `{"name": "get_weather", "arguments": {"city": "Berlin", "unit": "celsius"}}` — correct, intent-matched, schema-valid. `apply_fault` forces this to fail (`"response payload truncated by gateway"`), triggering a retry.
- Retry output: `{"name": "get\_weather", "arguments": {"city": "Berlin", "unit": "celsius"}}` — note the literal backslash before the underscore (`get\_weather`). `\_` is **not a valid JSON escape sequence**, so `json.JSONDecodeError` is raised at that `{`, `extract_tool_call` finds no other candidate, and the retry is scored `parse_failure` → final score 0 — **despite the arguments being correct and the only problem being a single spurious backslash the retry prompt itself induced** (same pattern repeats byte-for-byte across all 3 trials of this task).
- **Why it failed**: not a robustness/semantic failure — a model-specific formatting quirk (escaping an underscore as if inside markdown) triggered specifically by the retry prompt wording, that happens to break strict JSON parsing.

**Qwen3**, tasks 025/037/038, `empty_result` fault (`results/upgradecanary-real-trials-qwen3_seed1234_20260929T230135Z/`):
- First attempt: begins `<think>\nOkay, the user is asking for documentation about vector index compaction...` and is cut off mid-thought (no closing `</think>`, no JSON ever emitted) — scored `parse_failure`, triggering a retry.
- Retry (with the added "previous call failed" feedback, making the prompt longer): again begins a fresh `<think>` block reasoning about *why* the empty result happened, and is again cut off before producing JSON.
- **Why it failed**: the retry prompt is strictly longer than the original (it appends the failure feedback), leaving even less of the 256-token budget for Qwen3 to finish thinking and emit the call — so faults that trigger a retry are systematically *more* likely to truncate for Qwen3, compounding B6's finding.

---

## F. Schema drift

### F14. Does the model see the drifted schema, or the old schema while the executor uses the new one?

**For synthetic tasks: the model always sees the drifted schema** — `drifted_schema(base_schema, drift)` is computed once ([runner.py:154](upgradecanary/runner.py#L154)) and the *same* `schema` variable is passed into both `build_prompt()` ([runner.py:156](upgradecanary/runner.py#L156)) and later into `evaluate()`/`execute()` ([runner.py:168-217](upgradecanary/runner.py#L168-L217)) — prompt and scoring always use the identical schema object.

**For BFCL tasks: this was a confirmed BUG, now fixed.** Before the 2026-10-01 fix (commit `93c092d`, "Fix BFCL drift prompt rendering"), `build_prompt` rendered the task's **static original** native schema (`task.tool_schema`) for BFCL tasks regardless of `drift`, while the evaluator/executor used the drifted schema — the model was being scored against a drift it was never shown. The fix (`to_native_doc(schema, native)`, [upgradecanary/bfcl.py:132-169](upgradecanary/bfcl.py#L132-L169)) rebuilds the BFCL-native document from the *actual* (possibly drifted) schema before rendering, so prompt and evaluator now agree. This is documented in `docs/experiment_log.md` (2026-10-01 "INVALIDATION" and "Corrected" entries) and verified directly against the old vs. new result folders in section H below. All current BFCL claims use only post-fix runs.

**Verdict: OK now** (post-fix, verified both by code reading and by data). The historical bug is real and large (see H) but is fully disclosed and excluded from current claims.

### F15. Correct behavior per drift type

Defined by `drifted_schema()` / `to_canonical_args()` / `compatible()` in [upgradecanary/perturbations/schema_drift.py](upgradecanary/perturbations/schema_drift.py):
- **`field_rename`**: agent must use the new field name in its call to pass `args_valid_under_drift`; either old or new name's *value* counts for `args_intent_match` (keys are canonicalized back, lines 295-300, before semantic comparison).
- **`field_drop`**: the dropped field must not be required by the new schema; a call omitting it is valid; intent is judged only on the fields that still exist in the canonical expectation.
- **`type_mutation`**: the new type (e.g. `string` for a `number` field) must validate; `to_canonical_args`/executor coerce unambiguous string→number/int/bool conversions for execution ([schema_drift.py:250-270](upgradecanary/perturbations/schema_drift.py#L250-L270)).
- **`unexpected_field`**: a new required field is added; the agent is expected to supply it to be schema-valid, but intent is judged only on the originally-expected arguments (a pre-upgrade agent correctly omitting the new field still gets intent credit per [schema_drift.py:365-371](upgradecanary/perturbations/schema_drift.py#L365-L371)).
- **`enum_drift`**: new enum values replace old ones; the agent must emit a new-space value to validate; intent maps old↔new values via `old_to_new`.

**Verdict: OK** (documented in code comments and docstrings; consistent with how the metrics are implemented).

---

## G. Semantic intent match

### G16. How is "semantic intent match" computed? Any human-label validation?

Purely rule-based, no embeddings, no LLM judge. `compatible()` ([upgradecanary/perturbations/schema_drift.py:344-375](upgradecanary/perturbations/schema_drift.py#L344-L375)) normalizes both parsed and expected arguments into the drifted schema's key-space (`to_new_space`), maps keys back to canonical names (`_canonical_key`), and compares values with `_value_matches` ([schema_drift.py:103-109](upgradecanary/perturbations/schema_drift.py#L103-L109)): exact equality for everything except the `expression` argument, which uses AST-based arithmetic-equivalence (`expressions_equivalent`, [schema_drift.py:89-100](upgradecanary/perturbations/schema_drift.py#L89-L100), never `eval()`). For BFCL tasks, `_acceptable_intent` ([schema_drift.py:312-341](upgradecanary/perturbations/schema_drift.py#L312-L341)) instead checks membership in BFCL's multi-value acceptable set plus omission-tolerance semantics.

`grep -rni "human" tests/ docs/ upgradecanary/` returns **no matches**.

**Verdict: CONFOUND RISK (minor/disclosed-by-omission).** The rule set is sound and the arithmetic-equivalence case is specifically regression-tested (`tests/test_pilot.py`, confirmed present per the `add9301` commit diff), but there is **no human-labeled validation set** confirming that the rule-based intent definition matches what a human rater would consider "the same intent" across all five drift types and all task tools — this is **NOT FOUND**, not merely unconfirmed. Given the entire "intent match vs. schema validity" gap is the paper's core upgrade-drift signal, a small human-annotated spot check (even 20-30 examples) would materially strengthen the construct-validity case a reviewer is likely to ask for.

---

## H. "Corrected" BFCL suite — git history and old vs. new numbers

### H17. What changed, which commits, why, and old vs. new numbers

Relevant commits (`git log --oneline`, newest first):

| Commit | Message | What changed |
|---|---|---|
| `93c092d` | Fix BFCL drift prompt rendering | `upgradecanary/bfcl.py` (+`to_native_doc`, +`internal_from_native`), `upgradecanary/runner.py` (`build_prompt` now renders `to_native_doc(schema, native)` for BFCL tasks instead of the static `native` doc) — the fix behind F14/Top-risk-#5 |
| `48bdc7c` | Add corrected cross-suite analysis | `scripts/analyze_cross_suite.py` updated to default to the post-fix run directories |
| `13811ec` | Support BFCL acceptable-value intent semantics | `upgradecanary/evaluator.py`, `upgradecanary/perturbations/schema_drift.py` (+`_acceptable_intent`), `upgradecanary/bfcl.py` — BFCL multi-value/omission intent amendment |
| `651e100` | Make drift evaluation semantics fairer | `upgradecanary/perturbations/schema_drift.py` (+140 lines), `upgradecanary/tools.py` — canonical-type coercion / drift-only field dropping before execution |
| `9cb204b` | Use functional score for tool-use success | `upgradecanary/evaluator.py` — redefined `score` to the current AND-chain formula, decoupled from `args_exact` |
| `add9301` | Fix canonical expression intent matching | `upgradecanary/perturbations/schema_drift.py` — the `_canonical_key` fix for the `expression`→`expr` rename artifact |

Full commit messages/diffstats confirmed via `git show --stat` and `git show <hash> -- <path>` for each (see `docs/experiment_log.md` dated entries, which match the commits 1:1 with dates 2026-09-28 through 2026-10-01).

**Old vs. new numbers — computed directly from the still-present pre-fix and post-fix result folders** (`analysis/audit/prefix_vs_postfix.py`, not just read from docs):

| Model | condition | pre-fix | post-fix | Δ |
|---|---|---|---|---|
| Mistral v0.1 | baseline | 0.890 | 0.890 | +0.000 |
| Mistral v0.1 | schema_drift | 0.223 | 0.690 | **+0.467** |
| Mistral v0.1 | runtime_fault | 0.883 | 0.883 | +0.000 |
| Mistral v0.2 | schema_drift | 0.190 | 0.623 | **+0.433** |
| Mistral v0.3 | schema_drift | 0.237 | 0.777 | **+0.540** |
| Qwen2.5 | schema_drift | 0.217 | 0.923 | **+0.707** |
| Qwen3 | schema_drift | 0.187 | 0.693 | **+0.507** |

`baseline` is unaffected for all 5 models (Δ=0.000, as expected — the bug was drift-prompt-specific). `runtime_fault` shows tiny (±0.003–0.007) differences between the two full reruns, consistent with the documented GPU-sampling non-determinism caveat for temperature-0.7 trials (`README.md`: "llama.cpp seeding is best-effort on GPU"), not a residual bug. `schema_drift` jumps by +0.43 to +0.71 for every model — the single largest score change anywhere in this project's history, and it flips the v0.1→v0.3 decision label from "neutral" to "beneficial" (per `docs/results_summary.md` and `docs/experiment_log.md`, confirmed consistent with the recomputed deltas above).

**Verdict: documented BUG, now fixed, with full before/after traceability.** All current claims in `docs/results_summary.md` / `docs/experiment_report.md` correctly use only the post-fix runs (verified directly: the folder names cited there, e.g. `..._20261001T142620Z`, match the post-fix directories above, not the pre-fix `..._20261001T042558Z` ones).

---

## I. Ceiling effects

### I18. Tasks passed by all 5 models in all trials, baseline

(`analysis/audit/ceiling_effects.py`)

**Synthetic suite:**

| Model | all-trials-pass (baseline) |
|---|---|
| Mistral v0.1 | 100/100 |
| Mistral v0.2 | 100/100 |
| Mistral v0.3 | 97/100 |
| Qwen2.5 | 100/100 |
| Qwen3 | 99/100 |
| **Ceiling (all 5 agree)** | **96/100 (96.0%)** |

**BFCL suite:**

| Model | all-trials-pass (baseline) |
|---|---|
| Mistral v0.1 | 84/100 |
| Mistral v0.2 | 71/100 |
| Mistral v0.3 | 93/100 |
| Qwen2.5 | 93/100 |
| Qwen3 | 70/100 |
| **Ceiling (all 5 agree)** | **46/100 (46.0%)** |

**Verdict: CONFOUND RISK on the synthetic suite.** 96% of synthetic baseline tasks carry zero model-discriminating signal — consistent with the synthetic suite being deliberately easy at baseline by construction (this is explicitly the intended design per `docs/protocol.md`: baseline is a secondary metric, stress conditions carry the signal), but it means synthetic *baseline* comparisons in particular should never be read as informative, and the K24 finding (BFCL baseline is informative, synthetic baseline mostly isn't) is partly explained by this ceiling gap between suites. BFCL's lower ceiling rate (46%) means baseline there is a genuinely more discriminating condition — reinforcing K24's concern rather than explaining it away.

---

## J. Canary / release gate

### J19. How are canary tasks selected, and whose data?

Two distinct selection procedures exist in the codebase:
- **Cross-pair leave-one-out informativeness** (`scripts/analyze_gate_threshold_sensitivity.py:136-144`, the procedure behind the published `tables/gate_accuracy.csv` "selected" column per `docs/results_summary.md`'s footnote): for the decision under evaluation, task informativeness is the mean `|stress diff|` over the **other three** decisions only (`others = [d for d,_,_ in DECISIONS if d != name]`, line 141) — the decision being evaluated never contributes to its own canary's selection.
- **Train/test split** (`scripts/validate_release_gate_splits.py:128-145`): tasks are ranked by `|diff|` on a training upgrade pair, then the resulting canary is evaluated on a **different, held-out** upgrade pair (`pairs[test_idx]` ≠ `pairs[train_idx]`).

Both procedures use a coverage pass (`select_canary`, same logic in both scripts) that greedily adds the highest-|diff| task that introduces an uncovered drift/fault category before filling the remainder by rank.

**Verdict: OK** — no circularity in either of these two procedures.

### J20. Circularity check — does ground truth include the canary tasks?

**Yes, trivially, by design — but this is not the same as circular selection bias.** A "canary" is defined as a subset of the same 100-task suite that also defines the full-suite ground truth (the canary and the full suite share the same task pool; that's what makes it a cheap proxy for the full suite). The question that matters is whether the *selection* of which tasks go in the canary uses the outcome being predicted — and per J19, it does not, for the two methods that produce the published numbers.

There **is** one place with genuine (disclosed) in-distribution circularity: `scripts/analyze_release_gate.py`'s "random"-subset baseline draws `random.sample(task_ids, size)` from the exact same `task_ids` set used to compute `full_diff` (lines 107-129) — this is explicitly flagged as a limitation already in `docs/experiment_log.md` (2026-09-29 entry: "subsets sampled from the same 100 tasks that define the ground truth (in-distribution)"). It affects only this one exploratory script's "random" numbers, not the leave-one-out "selected" numbers that back the main claims.

**Verdict: OK** for the published LOUO-based numbers; **CONFOUND RISK (already disclosed)** for the exploratory in-distribution random-subset script.

### J21. Exactly how many upgrade pairs exist in the gate evaluation?

**4 per suite, 8 total** — confirmed by `DECISIONS` in `scripts/analyze_gate_threshold_sensitivity.py:44-49`:
1. Mistral v0.1→v0.2
2. Mistral v0.2→v0.3
3. Mistral v0.1→v0.3
4. Qwen2.5→Qwen3

...each run on both the synthetic and BFCL suites (= 8 decisions total, matching `tables/upgrade_decisions.csv`'s 8 rows).

**Verdict: OK.** Explicitly and correctly disclosed in `docs/results_summary.md`/`docs/experiment_report.md` as a small-N limitation ("one three-version family, one Qwen pair").

### J22. How is calibration/shrinkage fit, and on how many points?

`fit_alpha()` (`scripts/analyze_gate_threshold_sensitivity.py:107-109`): ordinary least squares through the origin, `alpha = sum(full_i * canary_i) / sum(canary_i^2)`. Fit three ways:
- **LOUO** (lines 168-174): for each of the 4 decisions, `alpha` is fit on the **other 3** decisions (n=3 training points) and applied to the held-out one.
- **Mistral→Qwen family transfer** (lines 174-176): `alpha` fit on the 3 Mistral decisions (n=3), applied to predict Qwen2.5→Qwen3.
- **Qwen→Mistral family transfer** (lines 177-179): `alpha` fit on the **single** Qwen2.5→Qwen3 decision (n=1), applied to predict all 3 Mistral decisions.

**Verdict: CONFOUND RISK**, already disclosed in `docs/experiment_log.md` ("alpha(Qwen->Mistral) = 0.42–1.11 (unstable, single training decision)"), but worth re-flagging prominently for a reviewer: a least-squares fit on a **single data point** (n=1) is not a fit in any statistically meaningful sense — it is one ratio, with no way to assess its stability, and the reported 0.42–1.11 "range" in the log is itself only a range across different canary sizes `k`, not a confidence interval. Any claim of calibration transfer in this direction should be described as a single anecdotal data point, not validated.

### J23. Random-subset baseline: 1000× 30-task subsets, verdict-match rate per upgrade pair

No existing script runs exactly 1000 reps at the single fixed size k=30 and reports per-pair match rate against the full-suite verdict in this form (existing scripts use 200 reps, swept across 5 sizes). Computed directly from the existing logs (`analysis/audit/random_baseline_check.py`, seed `20261002`, documented in the script, GATE_THRESHOLD=0.05 — same threshold as `docs/protocol.md`):

**Synthetic:**

| Pair | full-suite truth | random-k=30 match rate |
|---|---|---|
| Mistral v0.1→v0.2 | harmful (−0.168) | 1.000 |
| Mistral v0.2→v0.3 | beneficial (+0.123) | 0.929 |
| Mistral v0.1→v0.3 | **neutral** (−0.045) | **0.648** |
| Qwen2.5→Qwen3 | **neutral** (−0.042) | **0.663** |

**BFCL:**

| Pair | full-suite truth | random-k=30 match rate |
|---|---|---|
| Mistral v0.1→v0.2 | harmful (−0.115) | 0.887 |
| Mistral v0.2→v0.3 | beneficial (+0.187) | 1.000 |
| Mistral v0.1→v0.3 | beneficial (+0.072) | 0.747 |
| Qwen2.5→Qwen3 | harmful (−0.230) | 1.000 |

**Verdict: OK**, but reveals a real, already-partially-disclosed nuance: for decisive truths (|Δ|≥0.11), a random 30-task canary gets the right verdict 89–100% of the time with **no selection at all** — meaning the paper's "selected canary beats random" claim (H4) is weak precisely where it would matter most (decisive decisions are easy for anyone), and strongest exactly where the truth is borderline-neutral — but there, even the best case match rate is only 65–75%, i.e., a random 30-task canary gives the **wrong accept/reject/inspect verdict roughly a third of the time** for a borderline-neutral upgrade. This is consistent with, and sharpens, the existing `docs/results_summary.md` caveat that synthetic gate accuracy is "threshold-sensitive" for the two borderline-neutral truths — reviewers should read any single canary-based release decision on a near-threshold upgrade with real caution, selected or not.

---

## K. Ranking check

### K24. Does the model ranking on baseline match drift/fault? Per-pair gaps with bootstrap CIs

(`analysis/audit/ranking_check.py`, task-level cluster bootstrap, 10,000 reps, seed 1234 — same convention as `scripts/analyze_version_trials.py`)

**Synthetic:**

| Pair | baseline Δ [CI] | schema_drift Δ [CI] | runtime_fault Δ [CI] | same sign? |
|---|---|---|---|---|
| M v0.1→v0.2 | +0.000 [+0.000,+0.000] n.s. | −0.093 [−0.143,−0.047] **sig.** | −0.243 [−0.323,−0.167] **sig.** | yes |
| M v0.2→v0.3 | −0.030 [−0.070,+0.000] n.s. | +0.033 [−0.023,+0.090] n.s. | +0.213 [+0.123,+0.303] **sig.** | **no** (baseline/drift sign vs fault sign disagree, though baseline/drift themselves are n.s.) |
| M v0.1→v0.3 | −0.030 [−0.070,+0.000] n.s. | −0.060 [−0.107,−0.020] **sig.** | −0.030 [−0.070,+0.000] n.s. | yes |
| Qwen2.5→Qwen3 | −0.003 [−0.010,+0.000] n.s. | −0.030 [−0.100,+0.037] n.s. | −0.053 [−0.083,−0.027] **sig.** | yes |

**BFCL:**

| Pair | baseline Δ [CI] | schema_drift Δ [CI] | runtime_fault Δ [CI] | same sign? |
|---|---|---|---|---|
| M v0.1→v0.2 | −0.083 [−0.153,−0.017] **sig.** | −0.067 [−0.143,+0.010] n.s. | −0.163 [−0.247,−0.083] **sig.** | yes |
| M v0.2→v0.3 | +0.137 [+0.080,+0.200] **sig.** | +0.153 [+0.087,+0.227] **sig.** | +0.220 [+0.147,+0.297] **sig.** | yes |
| M v0.1→v0.3 | +0.053 [+0.013,+0.097] **sig.** | +0.087 [+0.033,+0.147] **sig.** | +0.057 [+0.017,+0.103] **sig.** | yes |
| Qwen2.5→Qwen3 | −0.100 [−0.157,−0.047] **sig.** | −0.230 [−0.303,−0.160] **sig.** | −0.230 [−0.297,−0.163] **sig.** | yes |

**Verdict: CONFOUND RISK.** On synthetic, baseline is essentially flat (n.s. for 3/4 pairs, exactly 0 for the 4th) while drift/fault carry the signal — this is exactly the "clean accuracy is insufficient" story the paper tells. **On BFCL, baseline is statistically significant and same-signed as both stress conditions for all four pairs.** This means that on the public suite, a reviewer could reasonably argue that simply measuring clean-task accuracy would have already told you the correct direction (though not magnitude) of every one of the four upgrade decisions — directly cutting against Main Claim #1/#2 of the report ("clean-task accuracy is insufficient... invisible to clean-task accuracy") when generalized to the public suite. The paper should either soften this claim to "primarily supported on the synthetic suite" or add a dedicated analysis of how much *additional* decision-relevant information drift/fault conditions provide beyond baseline alone on BFCL (e.g., would baseline-only gating reach the same accept/reject/inspect verdicts as the full stress-based gate on BFCL's 4 decisions?).

---

## Files added by this audit

- `analysis/audit/common.py` — shared read-only loaders (final-run paths, functional score, pre-fix run paths)
- `analysis/audit/failure_breakdown.py` — D8/D9
- `analysis/audit/fault_mechanics.py` — E10-E13
- `analysis/audit/ceiling_effects.py` — I18
- `analysis/audit/random_baseline_check.py` — J23
- `analysis/audit/ranking_check.py` — K24
- `analysis/audit/prefix_vs_postfix.py` — H17

No file outside `analysis/audit/` and this `AUDIT.md` was created or modified.
