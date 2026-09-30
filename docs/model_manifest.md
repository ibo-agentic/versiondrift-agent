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

## Notes

- The two preliminary root-level Mistral files exist solely to keep earlier
  result folders reproducible.
- `models/.cache/` contains no GGUF files and is not part of this manifest.
