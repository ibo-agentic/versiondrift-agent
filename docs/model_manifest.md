# Model Manifest — UpgradeCanary

Generated 2026-09-30. All files under `models/`, hashed locally (SHA-256) on
2026-09-30. Nothing was downloaded, modified, or rerun during manifest
creation.

## 1. Preliminary mixed-source Mistral models

Used by the early v0.2/v0.3 comparison; that comparison is **preliminary**
(mixed quantizers) per `docs/experiment_log.md`. Retained so existing result
folders remain reproducible; do not use for new claims.

| Path | Size (bytes) | GiB | SHA-256 | Source repository | Associated configs |
|---|---|---|---|---|---|
| `models/mistral-7b-instruct-v0.2.Q4_K_M.gguf` | 4,368,439,584 | 4.07 | `3e0039fd0273fcbebb49228943b17831aadd55cbcbf56f0af00499be2040ccf9` | TheBloke/Mistral-7B-Instruct-v0.2-GGUF | `configs/real_smoke_v0.2.yaml`, `configs/real_pilot_v0.2.yaml`, `configs/real_trials_v0.2.yaml` |
| `models/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf` | 4,372,812,000 | 4.07 | `1270d22c0fbb3d092fb725d4d96c457b7b687a5f5a715abe1e818da303e562b6` | bartowski/Mistral-7B-Instruct-v0.3-GGUF | `configs/real_pilot_v0.3.yaml`, `configs/real_trials_v0.3.yaml` |

## 2. Matched itlwas Mistral models (canonical Mistral set)

Same quantizer (Q4_K_M, itlwas builds) across versions; basis for all
matched-phase confirmatory claims.

| Path | Size (bytes) | GiB | SHA-256 | Source repository | Associated configs |
|---|---|---|---|---|---|
| `models/itlwas/mistral-7b-instruct-v0.1-q4_k_m.gguf` | 4,368,440,864 | 4.07 | `1af6bf966c4113f0cb5de7af42f38572075c9798bc16e6c72faee051bd7d6d33` | itlwas/Mistral-7B-Instruct-v0.1-Q4_K_M-GGUF | `configs/real_trials_itlwas_v0.1.yaml` |
| `models/itlwas/mistral-7b-instruct-v0.2-q4_k_m.gguf` | 4,368,440,544 | 4.07 | `aaae8abe274e1521d5aa80bf32cf18b408fc44b9d6869acbdc815440296d275e` | itlwas/Mistral-7B-Instruct-v0.2-Q4_K_M-GGUF | `configs/real_trials_itlwas_v0.2.yaml` |
| `models/itlwas/mistral-7b-instruct-v0.3-q4_k_m.gguf` | 4,372,815,808 | 4.07 | `9a643d2815e427e6622c3ef7f284af942bd0c58463a7c94f726fa882f487a404` | itlwas/Mistral-7B-Instruct-v0.3-Q4_K_M-GGUF | `configs/real_trials_itlwas_v0.3.yaml` |

## 3. Qwen models

| Path | Size (bytes) | GiB | SHA-256 | Source repository | Associated configs |
|---|---|---|---|---|---|
| `models/qwen/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf` | 3,993,201,344 | 3.72 | `dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db` | Qwen/Qwen2.5-7B-Instruct-GGUF | `configs/real_smoke_qwen25.yaml`, `configs/real_trials_qwen25.yaml` |
| `models/qwen/qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf` | 689,872,288 | 0.64 | `539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a` | Qwen/Qwen2.5-7B-Instruct-GGUF | companion split part (configs point at part 1 only) |
| `models/qwen/Qwen3-8B-Q4_K_M.gguf` | 5,027,783,488 | 4.68 | `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785` | Qwen/Qwen3-8B-GGUF | `configs/real_smoke_qwen3.yaml`, `configs/real_trials_qwen3.yaml` |

No source is marked "verify": every filename matches the naming convention
of the repository listed (per the project's known-sources table). If any file
is replaced, re-hash and update this manifest before running experiments with
it.

## 4. Canonical matched set

The models behind current confirmatory claims and the frozen protocol
(`docs/protocol.md`):

1. itlwas Mistral v0.1 — `models/itlwas/mistral-7b-instruct-v0.1-q4_k_m.gguf`
2. itlwas Mistral v0.2 — `models/itlwas/mistral-7b-instruct-v0.2-q4_k_m.gguf`
3. itlwas Mistral v0.3 — `models/itlwas/mistral-7b-instruct-v0.3-q4_k_m.gguf`
4. Qwen2.5-7B-Instruct (split GGUF; part 1 referenced) — `models/qwen/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf`
5. Qwen3-8B — `models/qwen/Qwen3-8B-Q4_K_M.gguf`

Canonical run settings: llama.cpp via llama-cpp-python (CUDA), n_ctx 2048,
n_gpu_layers -1, temperature/seed per config, ChatML template for Qwen,
`[INST]` template without explicit `<s>` for Mistral, stop sequences per
`docs/protocol.md`.

## 5. PLAN.md 10.2 smoke-test models (2026-10-04/05)

The 11 Q4_K_M models from PLAN.md's 16-model table not covered by sections
1-3 above. Downloaded via `scripts/download_smoke_models.py` (resumable:
`curl -C -`, since both `huggingface_hub`'s default "Xet" transfer backend
and its classic ETag-keyed resume both failed outright on this machine's
connection -- see that script's own docstring). Every SHA-256 below is
each file's own HF "lfs.oid" field (fetched live from the HF tree API,
not computed-then-trusted-blindly) AND independently re-verified against
a local SHA-256 of the actual downloaded bytes by that same script --
both matched for all 11 files. No config YAML exists yet for any of
these; they are driven directly by `scripts/smoke_one_model.py` for the
smoke test (see `analysis/plan/smoke_report.md`), not by a `configs/*.yaml`
entry point.

| Path | Size (bytes) | GiB | SHA-256 | Source repository |
|---|---|---|---|---|
| `models/qwen/qwen2-7b-instruct-q4_k_m.gguf` | 4,683,071,264 | 4.36 | `ed93dfc426f926451fa3ec7f996a787a31cfd97e55d7769568fbffc2d69861c2` | Qwen/Qwen2-7B-Instruct-GGUF |
| `models/llama/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf` | 4,920,734,272 | 4.58 | `8ba9baf3a7345f705a11878397500fb25174034f0fd784e83aa4a96aaa47735f` | bartowski/Meta-Llama-3-8B-Instruct-GGUF |
| `models/llama/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` | 4,920,739,232 | 4.58 | `7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c` | bartowski/Meta-Llama-3.1-8B-Instruct-GGUF |
| `models/phi/Phi-3-mini-4k-instruct-Q4_K_M.gguf` | 2,393,231,360 | 2.23 | `28a89b4ddb5766355f24e362ae4078b4c35b9ca9568df5fc9e6d9aeee4dee834` | bartowski/Phi-3-mini-4k-instruct-GGUF |
| `models/phi/Phi-3.5-mini-instruct-Q4_K_M.gguf` | 2,393,232,672 | 2.23 | `e4165e3a71af97f1b4820da61079826d8752a2088e313af0c7d346796c38eff5` | bartowski/Phi-3.5-mini-instruct-GGUF |
| `models/phi/microsoft_Phi-4-mini-instruct-Q4_K_M.gguf` | 2,491,874,688 | 2.32 | `01999f17c39cc3074afae5e9c539bc82d45f2dd7faa3917c66cbef76fce8c0c2` | bartowski/microsoft_Phi-4-mini-instruct-GGUF |
| `models/granite/granite-3.0-8b-instruct-Q4_K_M.gguf` | 4,942,856,416 | 4.60 | `360c8e306b9a40c59080e60cb51305867457dfa7e66b99fdffdf5afaab8ba34b` | bartowski/granite-3.0-8b-instruct-GGUF |
| `models/granite/granite-3.1-8b-instruct-Q4_K_M.gguf` | 4,942,858,720 | 4.60 | `b72cfca8e30f23af77f922ce18d6fe1a5d4925907dddf7249c0cabc2739d48c8` | bartowski/granite-3.1-8b-instruct-GGUF |
| `models/granite/ibm-granite_granite-3.2-8b-instruct-Q4_K_M.gguf` | 4,942,859,808 | 4.60 | `bd041eb5bc5e75e4f9a863372000046fd6490374f4dec07f399ca152b1df09c2` | bartowski/ibm-granite_granite-3.2-8b-instruct-GGUF |
| `models/gemma/gemma-2-2b-it-Q4_K_M.gguf` | 1,708,582,752 | 1.59 | `e0aee85060f168f0f2d8473d7ea41ce2f3230c1bc1374847505ea599288a7787` | bartowski/gemma-2-2b-it-GGUF |
| `models/gemma/google_gemma-3-4b-it-Q4_K_M.gguf` | 2,489,758,112 | 2.32 | `4996030242583a40aa151ff93f49ed787ac8c25e4120c3ae4588b2e2a7d1ae94` | bartowski/google_gemma-3-4b-it-GGUF |

Together with sections 1-3, this is all 16 of PLAN.md section 2's models
at Q4_K_M. Note the uploader is not uniform within every family here
(unlike sections 1-3's one-quantizer-per-family convention): Llama/Phi/
Granite/Gemma all use bartowski (consistent per family), but Qwen2-7B
uses the official Qwen org repo like Qwen2.5/Qwen3 already did. This
matches `analysis/plan/feasibility.md`'s own choices, not a new decision
made here.

## Notes

- The two preliminary root-level Mistral files exist solely to keep earlier
  result folders reproducible.
- `models/.cache/` contains no GGUF files and is not part of this manifest.
