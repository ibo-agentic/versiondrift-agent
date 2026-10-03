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

**Provenance note**: the four entries below are well-documented public
values I'm reasonably confident of from memory of each model's official
model card / `generation_config.json`, but **none were re-verified against
a live source this session** (no web lookup was done for this file). Treat
them as a starting point to double-check, not as independently confirmed
citations, before using them for an actual F6 "recommended" run. Every
other model on PLAN.md's list is marked UNVERIFIED below rather than
filled in with an invented number.

## Verified-from-memory (needs a quick re-check before relying on it)

| Model | Recommended sampling | Source (as recalled, not re-fetched) |
|---|---|---|
| Qwen2.5-7B-Instruct | `temperature=0.7, top_p=0.8, top_k=20, repeat_penalty=1.05` | Qwen2.5 model card / `generation_config.json` |
| Qwen3-8B (thinking on) | `temperature=0.6, top_p=0.95, top_k=20, min_p=0.0` | Qwen3 model card / README (thinking-mode section) |
| Qwen3-8B (thinking off) | `temperature=0.7, top_p=0.8, top_k=20, min_p=0.0` | Qwen3 model card / README (non-thinking section) |
| Llama-3-8B-Instruct | `temperature=0.6, top_p=0.9` | Meta Llama 3 `generation_config.json` |
| Llama-3.1-8B-Instruct | `temperature=0.6, top_p=0.9` | Meta Llama 3.1 `generation_config.json` (same as 3) |

## UNVERIFIED — no confident citation, do not use until checked

- Mistral-7B-Instruct v0.1 / v0.2 / v0.3
- Phi-3-mini-instruct / Phi-3.5-mini-instruct / Phi-4-mini-instruct
- Granite-3.0-8b-instruct / Granite-3.1-8b-instruct / Granite-3.2-8b-instruct
- Gemma-2-2b-it / Gemma-2-9b-it
- Gemma-3-1b-it / Gemma-3-4b-it
- Qwen2-7B-Instruct

For these, `sampling_preset: recommended` should not be used in an actual
run until someone looks up that model's own model card / `generation_
config.json` and fills in a cited row above. Until then, use `sampling_
preset: shared` (the default) for these models.
