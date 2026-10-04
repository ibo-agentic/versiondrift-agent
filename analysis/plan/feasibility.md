# Model Feasibility Check — Candidate Models for UpgradeCanary

Research only. No experiments run, no files over 1 GB downloaded (all model
weight sizes below come from Hugging Face's repo file-listing / API, not
from downloading the file). Nothing under `upgradecanary/` was modified.
Machine: Windows, RTX 4060, 8GB VRAM. Stack: `llama-cpp-python==0.3.35` in
`.venv`, `n_gpu_layers=-1`, `n_ctx=2048` standard (`4096` for think-long
variants). Calibration points: Mistral-7B Q4_K_M (~4.07 GB) and Qwen3-8B
Q4_K_M (~5.03 GB, `models/qwen/Qwen3-8B-Q4_K_M.gguf`) both fit comfortably at
`n_ctx=2048`; Qwen3-8B also fit fine at `n_ctx=4096`.

## Summary

**Clearly feasible (weights comfortably under the empirical ~5 GB/8B
headroom point, standard architecture, Q4_K_M available from a verified
repo):** Qwen2-7B-Instruct, Llama-3-8B-Instruct, Llama-3.1-8B-Instruct,
Phi-3-mini-instruct, Phi-3.5-mini-instruct, Phi-4-mini-instruct,
Granite-3.0/3.1/3.2-8B-instruct, Gemma-2-2b-it, Gemma-3-4b-it, Gemma-3-1b-it.
All of these have a single consistent community quantizer across the whole
family where a family exists (bartowski, in every new case below), matching
this project's itlwas-for-Mistral precedent.

**Borderline:** Gemma-2-9b-it. Its Q4_K_M file (5.76 GB) is noticeably
larger than the Qwen3-8B calibration point (5.03 GB) because of Gemma-2's
256K-token vocabulary (larger embedding/output tensors baked into that
file size already). On an 8GB card with the OS/display also resident on
the GPU, the free margin above weights (~2.2 GB nominal) is smaller than in
any model this project has actually run. Likely still fits at `n_ctx=2048`
by the same reasoning used for Qwen3-8B, but has not been empirically
confirmed and should be sanity-checked with a short completion before a
full run. The smaller Gemma-2-2b-it (1.71 GB) is the safe fallback if it
does not.

**Not feasible as-is:** none of the requested models are outright too big
for Q4_K_M at this VRAM budget — the project did not ask about any 13B+
model, and the one borderline case (Gemma-2-9b-it) has a same-family smaller
fallback (Gemma-2-2b-it) already identified above.

**On native tool-calling templates (item c):** this project's harness
(`upgradecanary/runner.py:build_prompt`) calls `Llama.create_completion()`
with a hand-built raw prompt string — it never calls
`create_chat_completion(tools=...)` and never uses any model's native
chat/tool template, for any model, old or new (confirmed again by reading
`upgradecanary/model/llama_cpp_client.py`, which only exposes
`create_completion`). Separately, as a capability check: llama-cpp-python
0.3.35 *can* drive genuine native per-model tool templates generically
(`Llama.__init__` auto-builds a `Jinja2ChatFormatter` from the GGUF's own
embedded `tokenizer.chat_template` metadata and passes `tools=`/`tool_choice=`
straight into that template's render context — see `llama.py:505-536` and
`llama_chat_format.py:257-282`), but only for models whose chat template
actually defines tool-calling behavior. Verified from each model's source
`tokenizer_config.json`/`chat_template.jinja` on Hugging Face: Llama-3.1,
Phi-4-mini, and all three Granite versions (3.0/3.1/3.2) have a native
`tools`-aware template; Mistral v0.1/v0.2, Qwen2, Llama-3 (non-.1), Phi-3-mini,
Phi-3.5-mini, and both Gemma-2/Gemma-3 checked do not. Mistral v0.3 and
Qwen2.5/Qwen3's native tool templates were already documented as existing
(but unused) in `AUDIT.md` A1.

---

## Mistral-7B-Instruct v0.1 / v0.2 / v0.3 (confirm only)

Per `docs/model_manifest.md` §2 (canonical itlwas set) and §4:

| | v0.1 | v0.2 | v0.3 |
|---|---|---|---|
| a) Q4_K_M repo/file/size | `itlwas/Mistral-7B-Instruct-v0.1-Q4_K_M-GGUF` / `mistral-7b-instruct-v0.1-q4_k_m.gguf` / 4.07 GiB | `itlwas/Mistral-7B-Instruct-v0.2-Q4_K_M-GGUF` / 4.07 GiB | `itlwas/Mistral-7B-Instruct-v0.3-Q4_K_M-GGUF` / 4.07 GiB |
| | Same uploader (itlwas) across all three — exactly the pattern this project already standardized on. |
| b) Fits 8GB @ n_ctx=2048 | Yes — already run in this project at this exact setting. | Yes — already run. | Yes — already run. |
| c) Native tool template | Not in v0.1/v0.2 tokenizer (reverified here: `mistralai/Mistral-7B-Instruct-v0.1` and `-v0.2` tokenizer_config.json chat_template has no `tools`/`AVAILABLE_TOOLS`/`TOOL_CALLS`). v0.3 has the native `[AVAILABLE_TOOLS]`/`[TOOL_CALLS]` format per `AUDIT.md` A1 — present but unused by this harness. llama-cpp-python's hard-coded `"mistral-instruct"` chat_format (`llama_chat_format.py:1358`) does basic `[INST]` turn wrapping only, no tool JSON; genuine v0.3 native tool behavior would require the GGUF-embedded-template path described above, not independently re-verified against the actual itlwas GGUF files. |
| d) Q8_0 available | Not re-checked at this pass (manifest only records Q4_K_M; out of scope for "confirm only"). |

Manifest info otherwise unchanged; no new downloads needed, no action required for these three.

## Qwen2.5-7B-Instruct (confirm only)

Per `docs/model_manifest.md` §3: `Qwen/Qwen2.5-7B-Instruct-GGUF`, split
`qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf` (3.72 GiB) +
`-00002-of-00002.gguf` (0.64 GiB) = ~4.36 GiB total. Fits 8GB @ n_ctx=2048
(already run). Native tool template: documented in `AUDIT.md` A1 as present
(Qwen `<tools>`/`<tool_call>` ChatML-based format) but unused by this
harness. Q8_0 not re-checked (out of scope for confirm-only).

## Qwen3-8B (confirm only)

Per `docs/model_manifest.md` §3: `Qwen/Qwen3-8B-GGUF`,
`Qwen3-8B-Q4_K_M.gguf`, 5,027,783,488 bytes (4.68 GiB / 5.03 GB decimal).
Fits 8GB @ n_ctx=2048 **and** n_ctx=4096 (both already run — this is the
project's own empirical calibration point for the whole report). Native
tool template: present (ChatML `<tool_call>` style, same family as
Qwen2.5), unused by this harness per `AUDIT.md` A1. Q8_0 not re-checked.

---

## Qwen2-7B-Instruct

| | |
|---|---|
| a) Q4_K_M | **Official**: `Qwen/Qwen2-7B-Instruct-GGUF`, `qwen2-7b-instruct-q4_k_m.gguf`, ~4.7 GB (single file, not split like Qwen2.5). Matches this project's established preference for the official Qwen org repo (same choice made for Qwen2.5 and Qwen3). Cross-check: `bartowski/Qwen2-7B-Instruct-GGUF`, `Qwen2-7B-Instruct-Q4_K_M.gguf`, 4.68 GB — close agreement, confirms the official number. |
| b) Fits 8GB @ n_ctx=2048 | Yes. File size (~4.7 GB) is between the Mistral-7B (4.07 GB) and Qwen3-8B (5.03 GB) calibration points, same dense-transformer/GQA architecture family as Qwen2.5/Qwen3. Expect comparable or better headroom than Qwen3-8B, which already fit at n_ctx=4096. |
| c) Native tool template | **Verified NOT present.** Fetched `Qwen/Qwen2-7B-Instruct` `tokenizer_config.json`: `chat_template` has no `tools`/`<tool_call>` logic — only plain ChatML turns. (Tool-calling templates were introduced starting with Qwen2.5, not Qwen2.) llama-cpp-python's hard-coded `"qwen"` chat_format (`llama_chat_format.py:1096`) is also plain ChatML with no tool support. So there is no native-template path for this model either way. |
| d) Q8_0 | Official `Qwen/Qwen2-7B-Instruct-GGUF`: `qwen2-7b-instruct-q8_0.gguf`, ~8.1 GB. Also `bartowski/Qwen2-7B-Instruct-GGUF`: `Qwen2-7B-Instruct-Q8_0.gguf`, 8.10 GB. (Note: Q8_0 at ~8.1 GB would **not** fit comfortably in 8GB VRAM alongside KV cache/overhead — flag for CPU-offload or reduced-GPU-layer precision-sensitivity runs only, not full-GPU-offload runs.) |

## Llama-3-8B-Instruct

| | |
|---|---|
| a) Q4_K_M | `bartowski/Meta-Llama-3-8B-Instruct-GGUF`, `Meta-Llama-3-8B-Instruct-Q4_K_M.gguf`, 4.92 GB. Meta does not publish an official GGUF; bartowski is used here because the same uploader also covers Llama-3.1 below (preferred consistent-quantizer pattern). |
| b) Fits 8GB @ n_ctx=2048 | Yes. 4.92 GB is close to, and slightly below, the Qwen3-8B calibration point (5.03 GB), same 8B dense/GQA architecture class (32 layers, 8 KV heads, head_dim 128) — expect comparable VRAM behavior, i.e. fits with headroom to spare. |
| c) Native tool template | **Verified NOT present.** Checked two ungated mirrors (`NousResearch/Meta-Llama-3-8B-Instruct` and `unsloth/llama-3-8b-Instruct`) — `chat_template` has no `tools`/`builtin_tools`/`ipython`/`python_tag`. Llama-3 (non-.1) predates Meta's tool-calling template; it was introduced in 3.1. llama-cpp-python's hard-coded `"llama-3"` chat_format (`llama_chat_format.py:1065`) also only does header-role turn formatting, no tool JSON. |
| d) Q8_0 | `bartowski/Meta-Llama-3-8B-Instruct-GGUF`, `Meta-Llama-3-8B-Instruct-Q8_0.gguf`, 8.54 GB (too large for comfortable full-GPU-offload at 8GB; precision-sensitivity-only). |

## Llama-3.1-8B-Instruct

| | |
|---|---|
| a) Q4_K_M | `bartowski/Meta-Llama-3.1-8B-Instruct-GGUF`, `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf`, 4.92 GB. Same uploader as Llama-3 above — bartowski covers both consistently. |
| b) Fits 8GB @ n_ctx=2048 | Yes, same reasoning as Llama-3-8B (identical architecture/size; only RoPE scaling and training data differ, not VRAM footprint). |
| c) Native tool template | **Verified present.** `unsloth/Meta-Llama-3.1-8B-Instruct` `tokenizer_config.json` chat_template contains `tools`, `builtin_tools`, `Environment: ipython`, and `<\|python_tag\|>` — this is Meta's official JSON tool-calling template (confirmed by explicit keyword match; a `NousResearch` mirror gave an inconclusive negative read on the same question, likely a partial/truncated read of a very long single-line template by the fetch summarizer — the unsloth result with quoted matches is the more reliable positive signal and matches widely-documented Llama-3.1 tool-calling behavior). Mechanism check: llama-cpp-python has **no** hard-coded `"llama-3.1"` chat_format (only `"llama-3"`, which doesn't carry the tool logic), so using this natively would require the auto-detected GGUF-embedded-template path (`llama.py:530-536`, `Jinja2ChatFormatter`) rather than the `chat_format="llama-3"` string — i.e. leave `chat_format`/`chat_handler` unset and pass `tools=` to `create_chat_completion`, relying on the GGUF having preserved the original `tokenizer.chat_template` metadata. Not independently verified that `bartowski`'s specific GGUF file preserves this metadata (would require reading the GGUF header/downloading — out of scope here), but bartowski's llama.cpp-based conversions from this period routinely do by default. |
| d) Q8_0 | `bartowski/Meta-Llama-3.1-8B-Instruct-GGUF`, `Meta-Llama-3.1-8B-Instruct-Q8_0.gguf`, 8.54 GB (precision-sensitivity-only, same caveat as Llama-3). |

## Phi-3-mini-instruct

| | |
|---|---|
| a) Q4_K_M | **Microsoft's own official GGUF repo exists but does not have Q4_K_M** — `microsoft/Phi-3-mini-4k-instruct-gguf` only ships `Phi-3-mini-4k-instruct-fp16.gguf` (7.64 GB) and a legacy `Phi-3-mini-4k-instruct-q4.gguf` (2.39 GB, an older non-K quant, not Q4_K_M). For true Q4_K_M: `bartowski/Phi-3-mini-4k-instruct-GGUF`, `Phi-3-mini-4k-instruct-Q4_K_M.gguf`, 2.39 GB. bartowski is the consistent-uploader choice because it also covers Phi-3.5-mini and Phi-4-mini below. |
| b) Fits 8GB @ n_ctx=2048 | Yes, trivially — 2.39 GB is roughly half the size of the Mistral-7B calibration point (~3.8B params vs 7B). Large VRAM headroom; could likely also run at n_ctx=4096 without issue. |
| c) Native tool template | **Verified NOT present.** `microsoft/Phi-3-mini-4k-instruct` `tokenizer_config.json` chat_template has no `tools`. llama-cpp-python has no dedicated Phi chat_format at all (only the generic `"chatml"`/fallback paths), so there is no built-in native path here regardless. |
| d) Q8_0 | NOT FOUND on `bartowski/Phi-3-mini-4k-instruct-GGUF` in this check (only Q4_K_M was confirmed directly); the sibling repo `bartowski/Phi-3.5-mini-instruct-GGUF` does have one (below) — UNVERIFIED whether the 3-mini repo also has Q8_0, would need a direct file-listing recheck. |

## Phi-3.5-mini-instruct

| | |
|---|---|
| a) Q4_K_M | `bartowski/Phi-3.5-mini-instruct-GGUF`, `Phi-3.5-mini-instruct-Q4_K_M.gguf`, 2.39 GB. Same bartowski family as Phi-3-mini/Phi-4-mini. |
| b) Fits 8GB @ n_ctx=2048 | Yes, trivially (same ~3.8B size class as Phi-3-mini). |
| c) Native tool template | **Verified NOT present.** `microsoft/Phi-3.5-mini-instruct` `tokenizer_config.json` chat_template has no `tools`. |
| d) Q8_0 | `bartowski/Phi-3.5-mini-instruct-GGUF`, `Phi-3.5-mini-instruct-Q8_0.gguf`, 4.06 GB — comfortably fits 8GB too, useful since it's small enough to actually run as a genuine precision-sensitivity pair on this GPU (unlike the 7-9B Q8_0 files above, which don't fit for full GPU offload). |

## Phi-4-mini-instruct

| | |
|---|---|
| a) Q4_K_M | `bartowski/microsoft_Phi-4-mini-instruct-GGUF`, Q4_K_M ≈ 2.49 GB. Naming convention shifted to an `microsoft_`-prefixed repo name starting at this release, but it's still the same bartowski uploader as Phi-3-mini/Phi-3.5-mini — consistent family coverage holds. |
| b) Fits 8GB @ n_ctx=2048 | Yes, trivially (~3.8B size class, same as Phi-3/3.5-mini). |
| c) Native tool template | **Verified present.** `microsoft/Phi-4-mini-instruct` `tokenizer_config.json` chat_template explicitly checks `'tools' in message` and wraps tool definitions in `<\|tool\|>...<\|/tool\|>` tags — Phi-4-mini was specifically built/marketed for function-calling. llama-cpp-python has no hard-coded Phi chat_format, so (same as Llama-3.1) using this natively requires the GGUF-embedded-template auto-detection path (`llama.py:530-536`), not the literal `chat_format=` string registry. GGUF-metadata preservation not independently re-verified (would require reading the GGUF header). |
| d) Q8_0 | `bartowski/microsoft_Phi-4-mini-instruct-GGUF`, Q8_0 ≈ 4.08 GB — fits 8GB comfortably, same note as Phi-3.5's Q8_0 (small enough for a real full-offload precision-sensitivity pair). |

## Granite-3.0-8b-instruct / Granite-3.1-8b-instruct / Granite-3.2-8b-instruct

| | 3.0 | 3.1 | 3.2 |
|---|---|---|---|
| a) Q4_K_M repo/file/size | `bartowski/granite-3.0-8b-instruct-GGUF`, `granite-3.0-8b-instruct-Q4_K_M.gguf`, 4.94 GB | `bartowski/granite-3.1-8b-instruct-GGUF`, Q4_K_M 4.94 GB | `bartowski/ibm-granite_granite-3.2-8b-instruct-GGUF`, Q4_K_M 4.94 GB |
| | Same uploader (bartowski) across all three — exactly the itlwas-style consistent-quantizer pattern this project wants. Repo naming shifts slightly at 3.2 (adds `ibm-granite_` prefix) but it's still bartowski. IBM's own `ibm-granite` org does publish some official GGUF repos (confirmed for 3.3, not confirmed for 3.0/3.1/3.2 in this check) — bartowski is the safer uniform choice across exactly this three-version set. |
| b) Fits 8GB @ n_ctx=2048 | Yes — 4.94 GB, essentially the same size class as the Qwen3-8B calibration point (5.03 GB), which already fit at n_ctx=4096. All three versions have identical file size (same architecture/param count across the point releases), so the same verdict applies to all three. |
| c) Native tool template | **Verified present, all three.** `ibm-granite/granite-3.0-8b-instruct`: chat_template renders an `<\|start_of_role\|>available_tools<\|end_of_role\|>` block when `tools` is set and supports `assistant_tool_call` / `<\|tool_call\|>`. `ibm-granite/granite-3.1-8b-instruct` and `.../granite-3.2-8b-instruct`: both templates explicitly instruct "respond with `<\|tool_call\|>` followed by a JSON list of tools" when `tools` is present — same mechanism, consistent across the family. Granite was explicitly designed for function-calling. llama-cpp-python has no hard-coded Granite chat_format, so (as above) using this natively needs the GGUF-embedded-template auto-detect path, not the literal registry. |
| d) Q8_0 | 3.0: `bartowski/granite-3.0-8b-instruct-GGUF`, Q8_0 8.68 GB. 3.1/3.2: not independently re-confirmed in this pass but same bartowski repos list the same quant ladder in their model cards per the 3.0 pattern — UNVERIFIED exact size for 3.1/3.2 Q8_0 specifically (would need a direct file-listing recheck; expect ~8.6-8.7 GB by analogy). All ~8.7 GB Q8_0 files would **not** fit comfortably for full GPU offload at 8GB — precision-sensitivity-only, same as the other 8B Q8_0 files above. |

## Gemma-2 small instruct models

Sizes that exist: **2B** (`gemma-2-2b-it`) and **9B** (`gemma-2-9b-it`); a
27B also exists but is out of scope (far too large for 8GB).

| | Gemma-2-2b-it | Gemma-2-9b-it |
|---|---|---|
| a) Q4_K_M | `bartowski/gemma-2-2b-it-GGUF`, `gemma-2-2b-it-Q4_K_M.gguf`, 1.71 GB | `bartowski/gemma-2-9b-it-GGUF`, `gemma-2-9b-it-Q4_K_M.gguf`, 5.76 GB |
| | Same bartowski uploader covers both sizes. |
| b) Fits 8GB @ n_ctx=2048 | Yes, trivially (far smaller than any calibration point). | **Borderline/likely-yes, not empirically confirmed.** 5.76 GB is ~0.7 GB above the Qwen3-8B calibration point (5.03 GB), and Gemma-2 has a much larger 256K-token vocabulary (already reflected in that 5.76 GB file size via bigger embedding/LM-head tensors) plus Gemma-2's mixed local/global sliding-window attention. Headroom math (8 GB − 5.76 GB weights ≈ 2.2 GB left for KV cache + CUDA context + any OS/display VRAM use) is still generically enough for a 2048-token KV cache on an 8-9B model (Mistral/Qwen3 needed only a few hundred MB for this), but this project has not run anything this close to the edge before. **Recommend a quick single-completion smoke test before committing to a full run; if it fails, fall back to Gemma-2-2b-it.** |
| c) Native tool template | **Verified NOT present** (checked `unsloth/gemma-2-9b-it` and `unsloth/gemma-2-2b-it`; neither chat_template mentions `tools`). Gemma-2 has no native tool-calling template at all; llama-cpp-python's hard-coded `"gemma"` chat_format (`llama_chat_format.py:1438`) is plain turn formatting only. |
| d) Q8_0 | `bartowski/gemma-2-2b-it-GGUF`, `gemma-2-2b-it-Q8_0.gguf`, 2.78 GB (fits comfortably, usable as a real full-offload precision pair) | `bartowski/gemma-2-9b-it-GGUF`, `gemma-2-9b-it-Q8_0.gguf`, 9.83 GB (does **not** fit in 8GB at all, even partially offloaded it would be tight; precision-sensitivity would need CPU/GPU split, not full offload). |

## Gemma-3 small instruct models

Sizes that exist: **1B**, **4B**, 12B, 27B (the last two out of scope —
too large for 8GB). 1B and 4B are the "small" sizes relevant here.

| | Gemma-3-1b-it | Gemma-3-4b-it |
|---|---|---|
| a) Q4_K_M | `bartowski/google_gemma-3-1b-it-GGUF`, `google_gemma-3-1b-it-Q4_K_M.gguf`, 806 MB (0.8 GB) | `bartowski/google_gemma-3-4b-it-GGUF`, `google_gemma-3-4b-it-Q4_K_M.gguf`, 2,489,758,112 bytes ≈ 2.49 GB (decimal) |
| | Same bartowski uploader covers both sizes (and 12B/27B, not needed here). |
| b) Fits 8GB @ n_ctx=2048 | Yes, trivially — smallest model on this entire list. | Yes, trivially — same size class as Phi-3.5-mini/Phi-4-mini. |
| c) Native tool template | **Verified NOT present** for 4B (`unsloth/gemma-3-4b-it` chat_template.jinja has no `tools`; the source `google/gemma-3-4b-it` repo is gated — 401 — so this was confirmed via the unsloth mirror instead). **Verified NOT present** for 1B as well (`unsloth/gemma-3-1b-it` chat_template.jinja, same check). Gemma-3, like Gemma-2, has no native structured tool-calling template; Google's documented function-calling approach for Gemma is prompt-based, not template-based. |
| d) Q8_0 | `bartowski/google_gemma-3-1b-it-GGUF`, `google_gemma-3-1b-it-Q8_0.gguf`, 1.07 GB | `bartowski/google_gemma-3-4b-it-GGUF`, `google_gemma-3-4b-it-Q8_0.gguf`, 4,130,226,592 bytes ≈ 3.85 GB (decimal) — both fit 8GB comfortably, both usable as genuine full-offload precision pairs. |

---

## e) llama-cpp-python 0.3.35 grammar / JSON-schema constrained decoding

Checked directly in `.venv/Lib/site-packages/llama_cpp/`:

- **`llama_grammar.py`**: `class LlamaGrammar` (line 19) with
  `LlamaGrammar.from_string(grammar: str, ...)` (line 25, raw GBNF text) and
  **`LlamaGrammar.from_json_schema(json_schema: str, ...)`** (line 46) — the
  latter converts an arbitrary JSON Schema straight into a GBNF grammar object
  and is exactly the mechanism needed to force syntactically-valid JSON tool
  calls. There's also a free function `json_schema_to_gbnf` used internally
  (referenced in `llama_chat_format.py` lines ~1729, ~2087) for the same
  conversion when building chat-completion-level tool constraints.
- **`llama.py`**: `grammar: Optional[LlamaGrammar] = None` is a first-class
  parameter on both `create_completion` (line 1815 signature area, passed
  through `_create_completion`, applied via `sampler.add_grammar` at line
  758-759) and `create_chat_completion` (line 2004/2019-2030). This means the
  project's current `create_completion(prompt=...)` call in
  `llama_cpp_client.py` could add a `grammar=LlamaGrammar.from_json_schema(...)`
  kwarg today with no other code changes, to force the model's raw-text
  completion to conform to a JSON schema derived from the active tool schema.
- **`response_format`**: `create_chat_completion`'s `response_format`
  parameter (line 2019, documented at line 2053: `{"type": "json_object"}`
  constrains to valid JSON) auto-builds a grammar for you —
  `_grammar_for_response_format` (line 1017) calls `_grammar_for_json_schema`
  (line 1005) when `response_format` includes a `"schema"` key, which in turn
  calls `LlamaGrammar.from_json_schema`. This same `response_format`→grammar
  auto-build path is wired into every chat-completion handler in
  `llama_chat_format.py` (`chatml-function-calling` at line 4131, the base
  `Jinja2ChatFormatter`-driven handler, and others) — e.g. lines 672-674,
  3042-3043, 3580-3581 all do
  `if response_format is not None and response_format["type"] == "json_object": grammar = _grammar_for_response_format(...)`.
  There's also explicit per-tool-choice grammar construction: when a specific
  `tool_choice` names a function, several handlers build
  `grammar = llama_grammar.LlamaGrammar.from_json_schema(...)` directly from
  that function's parameter schema (e.g. lines 714, 3082, 3617) so the output
  is constrained to that exact function's argument shape, not just "any JSON
  object."

**Bottom line for this project:** constrained decoding is readily available
and would be a strict improvement over (or complement to) the current
prompt-only "reply with ONLY a JSON object" instruction. The minimal-effort
option is adding `grammar=LlamaGrammar.from_json_schema(json.dumps(schema_as_json_schema))`
to the existing `create_completion` call in `llama_cpp_client.py`, built from
each task's active tool schema (already available as `schema`/`task_base_schema`
in `runner.py`). This would eliminate "parse_failure" / malformed-JSON
failures entirely (seen in `AUDIT.md` — e.g. Qwen3's unclosed `<think>`
truncations) at the cost of a documented, logged deviation from the frozen
protocol, since it changes what's being measured (schema-constrained
compliance vs. free-text instruction-following). Not evaluated here: whether
constraining *decoding* syntax also still permits the model to express
intentionally-wrong-but-schema-valid answers under the drift/fault
conditions — that would need to be checked against each perturbation's
intended behavior before switching.

## f) BFCL "multiple" category feasibility with the existing loader

Read in full: `upgradecanary/bfcl.py` and the BFCL-100 selection-protocol
section of `docs/protocol.md`.

**(1) Checks that currently assume exactly one function:**

- `upgradecanary/bfcl.py:84-86`:
  ```python
  functions = record.get("function") or []
  if len(functions) != 1:
      return False, "function_count"
  ```
  This is eligibility rule 3 in `docs/protocol.md` ("it has exactly one
  function") — the hard gate that excludes every BFCL `multiple`-category
  record today (those records carry a `function` list with several candidate
  schemas).
- `upgradecanary/bfcl.py:87-89` (`ground_truth` length == 1) is a **separate**
  check (protocol rule 4) that does **not** need to change: BFCL `multiple`
  tasks still have exactly one correct call, so `len(ground_truth) != 1`
  should still reject anything that isn't single-answer, which `multiple`
  tasks are.
- `upgradecanary/bfcl.py:98`: `fn = functions[0]` — hardcodes "the one
  function" as the eligibility-rule-checking target (grounding checks,
  required-arg checks). For `multiple` tasks this would need to become
  "the function whose name matches the ground-truth call's key", not simply
  index 0 (the correct function is not guaranteed to be `functions[0]` once
  there are several candidates).
- `upgradecanary/bfcl.py:210-212` (`convert()`): `fn = record["function"][0]`
  — same index-0 assumption, used to build `tool_schema`/`internal_schema`/
  `expected_call["name"]`. Same fix needed: look up the function by the
  ground-truth call's key, not by position.
- `upgradecanary/bfcl.py:295` (`generate()`): `fn_name = record["function"][0]["name"]`
  — used purely for the "keep first eligible occurrence per function name"
  dedup rule (protocol rule 11). For `multiple` tasks this should almost
  certainly dedup on the *correct* function's name (same one used for
  `expected_call`), not `functions[0]`'s name, for the same reason as above.

**(2) Can `build_prompt`/`task_base_schema` render more than one schema per
task today? No — both assume a single schema.**
- `upgradecanary/runner.py:42-59` (`build_prompt`): for BFCL tasks it does
  `json.dumps({"tools": [to_native_doc(schema, native)]}, ...)` — the list
  literal has exactly one element, built from `task.tool_schema` (singular,
  see below). Nothing iterates a list of candidates.
- `upgradecanary/runner.py:105-109` (`task_base_schema`): returns
  `task.internal_schema` (a single dict) or `BASE_SCHEMAS[task.tool]`
  (one schema keyed by one tool name) — again singular.
- `upgradecanary/tasks.py:31-32`: `Task.tool_schema: dict[str, Any] | None`
  and `Task.internal_schema: dict[str, Any] | None` are both typed as a
  single dict, not a list — the data model itself has no slot for multiple
  candidate schemas per task.

**(3) `tool_name_ok` scoring — confirmed unchanged.**
`upgradecanary/evaluator.py:69`:
`tool_name_ok = bool(parse_ok and parsed_call["name"] == expected_call["name"])`
— a pure string comparison against `task.expected_call["name"]`, which is
set once at conversion time and is independent of how many tool schemas were
shown in the prompt. This logic needs no change for `multiple`-category
support.

**(4) Concrete minimal change list (not implemented, plan only):**
1. Loosen `upgradecanary/bfcl.py:85-86`'s `len(functions) != 1` gate to allow
   `len(functions) >= 1` (or a new explicit category flag), while keeping
   `len(ground_truth) != 1` (line 88-89) as-is.
2. Change `fn = functions[0]` (line 98) and `fn = record["function"][0]`
   (line 211) to resolve the correct function by matching
   `next(iter(answer["ground_truth"][0]))` (the ground-truth call's function
   name) against the `functions` list, falling back to a clear rejection if
   no match is found (defends against malformed BFCL records).
3. Extend the Task/data-file schema: add a `candidate_schemas: list[dict] | None`
   field to `Task` (`upgradecanary/tasks.py`) and to `convert()`'s output
   dict (`upgradecanary/bfcl.py:241-253`), carrying all native function docs
   for the task; keep `tool_schema`/`internal_schema` pointing at the single
   *correct* one (so all existing single-schema code paths, including
   drift/execution/scoring, keep working unchanged for non-`multiple` tasks).
4. Extend `build_prompt` (`upgradecanary/runner.py:42-59`) to render
   `to_native_doc(schema, native)` for the correct schema **plus** the other
   candidates verbatim (undrifted) in the `"tools": [...]` list, when
   `task.candidate_schemas` is present.
5. Open design decision (not resolved here): whether/how `schema_drift`
   should apply when there are multiple tools in view — options are (a) only
   drift the correct tool's schema (simplest, keeps the drift-detection
   semantics this project already measures), (b) drift all candidates
   identically, or (c) drift a random subset. (a) is the least disruptive to
   the existing drift machinery (`apply_drift`/`drifted_schema` already take
   a single `schema=task_base_schema(task)`), and keeps `args_valid_under_drift`
   scoring meaningful without inventing new semantics for "drift across
   multiple schemas at once."
6. `tool_name_ok` (`upgradecanary/evaluator.py:69`) needs no change (point 3
   above) — included here only as an explicit confirmation step so a future
   implementer doesn't assume it needs touching.

No other eligibility rule (printable-ASCII, length, URL, grounding, scalar
values, prompt-length) is function-count-specific and none would need to
change for `multiple` support.

## g) Estimated runtime per full run (100 tasks x 3 conditions x 3 trials)

Calibration (given, all on this RTX 4060, Qwen3-8B Q4_K_M,
`n_gpu_layers=-1`): `max_tokens=256`/nothink/`n_ctx=2048` ≈ **24 min** per
full run (both synthetic and BFCL suites); `max_tokens=2048`/think_long/
`n_ctx=4096` ≈ **65-77 min**. ≈1,125 total generations per run (900 base +
up to 225 fault-retry). These are rough linear-in-compute scaling estimates
from that single calibration point, not independently measured — treat them
as planning-grade, not committed numbers.

| Model | Params | Budget/mode | Estimate | Basis |
|---|---|---|---|---|
| Mistral v0.1/v0.2/v0.3 | 7B dense | 256 tok, no thinking, n_ctx=2048 | already run in this project; exact minute figures not found logged in `docs/experiment_log.md`/`AUDIT.md` (UNVERIFIED exact number) — expect ≈20-24 min by analogy to Qwen3 nothink | 7B vs 8B is a small difference next to the fixed 256-token budget |
| Qwen2.5-7B-Instruct | 7B dense | 256 tok, no thinking, n_ctx=2048 | already run; exact minutes not found logged — expect ≈20-24 min | same reasoning; no thinking overhead at all (unlike Qwen3) |
| Qwen3-8B (nothink) | 8B dense | 256 tok, thinking off, n_ctx=2048 | **≈24 min (measured, this is the calibration point itself)** | direct measurement |
| Qwen3-8B (think_long) | 8B dense | 2048 tok, thinking on, n_ctx=4096 | **≈65-77 min (measured)** | direct measurement; highly variable on how much the model "thinks" |
| Qwen2-7B-Instruct | 7B dense | 256 tok, no thinking, n_ctx=2048 | ≈20-24 min | same size/budget class as Mistral/Qwen2.5, no thinking mode |
| Llama-3-8B-Instruct | 8B dense | 256 tok, no thinking, n_ctx=2048 | ≈24 min | same size/budget class as Qwen3 nothink |
| Llama-3.1-8B-Instruct | 8B dense | 256 tok, no thinking, n_ctx=2048 | ≈24 min | identical architecture/size to Llama-3-8B |
| Phi-3-mini-instruct | ~3.8B dense | 256 tok, no thinking, n_ctx=2048 | ≈12-16 min | meaningfully smaller than 7-9B; max_tokens budget dominates, so improvement is sublinear with param count, not proportional |
| Phi-3.5-mini-instruct | ~3.8B dense | 256 tok, no thinking, n_ctx=2048 | ≈12-16 min | same size class as Phi-3-mini |
| Phi-4-mini-instruct | ~3.8B dense | 256 tok, no thinking, n_ctx=2048 | ≈12-16 min | same size class as Phi-3/3.5-mini |
| Granite-3.0-8b-instruct | 8B dense | 256 tok, no thinking, n_ctx=2048 | ≈24 min | same size/budget class as Qwen3 nothink |
| Granite-3.1-8b-instruct | 8B dense | 256 tok, no thinking, n_ctx=2048 | ≈24 min | same as 3.0 (identical file size) |
| Granite-3.2-8b-instruct | 8B dense | 256 tok, no thinking, n_ctx=2048 | ≈24 min | same as 3.0/3.1 (identical file size) |
| Gemma-2-9b-it | 9B dense | 256 tok, no thinking, n_ctx=2048 | ≈26-30 min | slightly larger than the 8B calibration point plus a bigger (256K) vocab marginally increasing per-token softmax/logit cost |
| Gemma-2-2b-it | 2B dense | 256 tok, no thinking, n_ctx=2048 | ≈8-10 min | much smaller than any measured point; fixed per-run overhead (load, prompt processing) keeps this from scaling all the way down to 2/8 of 24 min |
| Gemma-3-4b-it | ~4B dense | 256 tok, no thinking, n_ctx=2048 | ≈12-16 min | same size class as Phi-3.5/Phi-4-mini |
| Gemma-3-1b-it | ~1B dense | 256 tok, no thinking, n_ctx=2048 | ≈5-8 min | smallest model on this list; mostly fixed-overhead-bound at this size |

Note: any model run with a `think_long`-style config (larger `max_tokens`,
thinking enabled if the model supports it, `n_ctx=4096`) should be expected
to scale toward the 65-77 min range instead, dominated by `max_tokens`/
thinking-budget, not by the small param-count differences within 7-9B.
Only Qwen3 among this list is known to have an explicit thinking mode;
none of the newer candidates (Llama-3/3.1, Phi-3/3.5/4-mini, Granite 3.x,
Gemma-2/3) are reasoning/thinking-mode models, so the "think_long" scenario
likely does not apply to them unless a config intentionally raises
`max_tokens` for some other reason.

---

## What I could not verify

- Exact wall-clock minutes for Mistral v0.1/v0.2/v0.3 and Qwen2.5-7B-Instruct
  full runs — not found logged in `docs/experiment_log.md`, `AUDIT.md`, or
  `analysis/audit/FOLLOWUP.md` in a reusable "N minutes" form; g)'s numbers
  for these two are scaling estimates, not re-derived measurements.
- Whether the specific Q4_K_M/Q8_0 GGUF *files* named above (as opposed to
  their source `tokenizer_config.json` on Hugging Face) actually preserve
  the `tokenizer.chat_template` metadata inside the GGUF itself — checking
  this would require reading each GGUF's header (effectively requiring the
  file to be fetched), which is out of scope for a research-only, no-large-
  download pass. Flagged per-model above wherever it matters (Llama-3.1,
  Phi-4-mini, Granite 3.0/3.1/3.2).
- `bartowski/Phi-3-mini-4k-instruct-GGUF`'s Q8_0 file — existence/size NOT
  independently confirmed in this pass (only Q4_K_M was checked directly for
  that specific repo).
- Granite-3.1-8b-instruct and Granite-3.2-8b-instruct Q8_0 exact sizes — not
  independently re-confirmed; estimated by analogy to Granite-3.0's Q8_0
  (8.68 GB) since all three share an identical Q4_K_M size (4.94 GB),
  implying an identical architecture/param count.
- Llama-3.1-8B-Instruct's native tool-template presence gave an inconsistent
  read across two mirrors (`NousResearch`: not found; `unsloth`: found, with
  explicit keyword matches). Resolved in favor of the positive/unsloth result
  per explicit keyword quotes and well-documented public knowledge of
  Llama-3.1's tool-calling format, but noting the discrepancy for the
  record.
- Gemma-2-9b-it's actual fit at `n_ctx=2048` on this specific 8GB card —
  reasoned from file size and the project's existing calibration points, not
  empirically run; flagged as the one genuinely borderline case in this
  report.
- IBM's own `ibm-granite` org GGUF repos for 3.0/3.1/3.2 specifically
  (confirmed to exist for 3.3 in a search result, not directly confirmed for
  3.0/3.1/3.2) — bartowski was used as the cross-version-consistent choice
  regardless, so this doesn't block anything, but it means "does IBM publish
  its own official GGUF for these three" is UNVERIFIED either way.
