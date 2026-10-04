# Sampling presets (PLAN.md F6)

`model.sampling_preset: "shared" | "recommended"` (default `"shared"`) is a
**logging/documentation flag only** — it does not itself change any
sampling behavior. The actual values always come from the existing
`model.temperature`/`top_p`/`top_k`/`min_p`/`repeat_penalty` config keys
(already supported by `upgradecanary/model/llama_cpp_client.py`). To run
"recommended" for a model, set those keys explicitly to the values below
and set `sampling_preset: recommended` so `run_manifest.json`'s
`run_factors.F6_sampling_preset` records that choice. "shared" means every
model uses this project's one common setting (the current
`top_p=0.95, top_k=40, min_p=0.05, repeat_penalty=1.0` defaults, `model.
temperature`/trial temperatures as already configured).

**Provenance (2026-10-04 full re-verification)**: every row below was
fetched live this session, directly from each model's own
`generation_config.json` (raw file on its Hugging Face repo) and/or its
model card text — not recalled from memory. Where a repo is gated
(`meta-llama/*`, `google/gemma-3-4b-it`, returned HTTP 401), an ungated
community mirror of the *same unmodified file* was used instead (the same
mirrors already cross-checked in `analysis/plan/feasibility.md`:
`unsloth/llama-3-8b-Instruct`, `unsloth/Meta-Llama-3.1-8B-Instruct`,
`unsloth/gemma-2-2b-it`, `unsloth/gemma-3-4b-it`), and this is noted per
row. A code example inside a model card that merely illustrates
deterministic/greedy usage (`"temperature": 0.0, "do_sample": False`) is
**not** treated as a sampling recommendation — several model cards below
include exactly this kind of example and are still marked "no
recommendation."

## Models with an official recommended sampling preset

| Model | Recommended sampling | Source |
|---|---|---|
| Qwen2-7B-Instruct | `temperature=0.7, top_p=0.8, top_k=20, repeat_penalty=1.05` | `Qwen/Qwen2-7B-Instruct/generation_config.json`, fetched 2026-10-04 |
| Qwen2.5-7B-Instruct | `temperature=0.7, top_p=0.8, top_k=20, repeat_penalty=1.05` | `Qwen/Qwen2.5-7B-Instruct/generation_config.json`, fetched 2026-10-04 (identical values to Qwen2) |
| Qwen3-8B (thinking on, `enable_thinking=True`) | `temperature=0.6, top_p=0.95, top_k=20, min_p=0.0` | `Qwen/Qwen3-8B` model card, "Best Practices" section, fetched 2026-10-04 ("For thinking mode ... use Temperature=0.6, TopP=0.95, TopK=20, and MinP=0"); matches the model's `generation_config.json` default (`temperature=0.6, top_p=0.95, top_k=20`) |
| Qwen3-8B (thinking off, `enable_thinking=False`) | `temperature=0.7, top_p=0.8, top_k=20, min_p=0.0` | `Qwen/Qwen3-8B` model card, "Best Practices" section, fetched 2026-10-04 ("For non-thinking mode ... Temperature=0.7, TopP=0.8, TopK=20, and MinP=0"). Not the `generation_config.json` default (that file encodes only the thinking-mode value); this row is text-only. |
| Llama-3-8B-Instruct | `temperature=0.6, top_p=0.9` | `generation_config.json`, fetched 2026-10-04 via `unsloth/llama-3-8b-Instruct` (official `meta-llama/Meta-Llama-3-8B-Instruct` is gated, HTTP 401) |
| Llama-3.1-8B-Instruct | `temperature=0.6, top_p=0.9` | `generation_config.json`, fetched 2026-10-04 via `unsloth/Meta-Llama-3.1-8B-Instruct` (official `meta-llama/Meta-Llama-3.1-8B-Instruct` is gated, HTTP 401); identical values to Llama-3 |
| Gemma-3-4b-it (partial — see caveat) | `top_p=0.95, top_k=64` (`do_sample=true`; `temperature` is not set in the file, so it falls back to the HF `GenerationConfig` library default of `1.0` — not an explicit per-model recommendation) | `generation_config.json`, fetched 2026-10-04 via `unsloth/gemma-3-4b-it` (official `google/gemma-3-4b-it` is gated, HTTP 401). The model card text itself (also fetched 2026-10-04) states no sampling parameters at all. Treat this row as weaker evidence than the others above — it's a shipped default, not a stated recommendation, and the mirror's generation_config.json is the only source for it. |

## Models with no official recommendation — use `sampling_preset: shared`

For every model below, neither its `generation_config.json` (fetched
2026-10-04, raw file on the model's own Hugging Face repo) nor its model
card text (also fetched 2026-10-04) states a recommended sampling value.
Where `generation_config.json` has no `temperature`/`top_p`/`top_k`
key at all, that is reported explicitly rather than left ambiguous.

| Model | What was checked |
|---|---|
| Mistral-7B-Instruct-v0.1 | `generation_config.json`: only `bos_token_id`/`eos_token_id` (no sampling keys). Model card: no stated recommendation (one code example uses `temperature=0.0` as an illustrative deterministic call, not a recommendation). |
| Mistral-7B-Instruct-v0.2 | Same as v0.1 — `generation_config.json` has no sampling keys; model card has no stated recommendation. |
| Mistral-7B-Instruct-v0.3 | Same as v0.1/v0.2 — `generation_config.json` has no sampling keys; model card has no stated recommendation (mentions evaluating "at temperature 0" for benchmarking only, not a usage recommendation). |
| Phi-3-mini-4k-instruct | `generation_config.json`: only bos/eos/pad token ids (no sampling keys). Model card's sample inference code uses `"temperature": 0.0, "do_sample": False` — an explicitly deterministic example, not a recommendation. |
| Phi-3.5-mini-instruct | `generation_config.json`: only bos/eos/pad token ids (no sampling keys). Model card: no stated recommendation. |
| Phi-4-mini-instruct | `generation_config.json`: only bos/eos/pad token ids (no sampling keys). Model card's vLLM/Transformers examples use `"temperature": 0.0` illustratively, not as a recommendation. |
| Granite-3.0-8b-instruct | `generation_config.json`: only placeholder `bos/eos/pad_token_id: 0` (no sampling keys). Model card: no stated recommendation. |
| Granite-3.1-8b-instruct | Same as 3.0 — `generation_config.json` has no sampling keys; model card has no stated recommendation. |
| Granite-3.2-8b-instruct | Same as 3.0/3.1 — `generation_config.json` has no sampling keys; model card has no stated recommendation. |
| Gemma-2-2b-it | `generation_config.json` (via `unsloth/gemma-2-2b-it`, official repo gated): only `cache_implementation`/`max_length`/token ids, no sampling keys. Model card: no stated recommendation (one `torch.compile` example uses `temperature=1.0` illustratively). |

Until a cited recommendation exists for a model above, `sampling_preset:
recommended` must not be used for it — use `sampling_preset: shared` (the
default).
