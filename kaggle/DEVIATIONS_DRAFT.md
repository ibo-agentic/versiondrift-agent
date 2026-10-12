# DEVIATIONS draft: F5 / R_F5 on Kaggle T4 (text only, not yet merged into DEVIATIONS.md)

## 2026-10-13: F5 (Q8_0) and R_F5 runs for the 8B models were done on Kaggle 2x T4, not on the laptop

**What differs from the other protocols.** Every other run in this study (D, F1-F4, F6, F11, R, controls)
was produced on the laptop (RTX 4060, 8 GB VRAM, Windows). F5 and R_F5 for the 8B models were produced on
Kaggle (Linux, 2x NVIDIA T4, 16 GB each, one process per GPU). The F5 and R_F5 folders therefore differ
from D and R in hardware as well as in quantisation level: this is the one place where the hardware
differs between compared runs.

**Why.** Q8_0 8B models are about 8.5 GB each, which does not fit in the laptop's 8 GB of VRAM with the
KV cache at n_ctx 4096 (full offload is how every other run was done). Partial offload would change speed
but also the execution path, and would be slow enough (11 models x 3 suites, plus 5 models x 3 suites at
R) to be impractical. T4s have 16 GB each, so every Q8_0 8B model is fully offloaded with the same
`n_gpu_layers: -1`, `n_ctx: 4096` settings as on the laptop.

**What was kept identical.** `upgradecanary` code and the laptop's own `scripts/real_run_one.build_config`
(same commit, recorded in each manifest as `kaggle.repo_commit`); seed 1234 and trial seeds
1234/1235/1236; trial temperatures 0.0/0.7/0.7; task files (SHA-256 recorded and checked on import);
perturbations; `max_tokens` 256 (F5) / 1024 (R_F5); constrained decoding off (F5) / generic_json (R_F5);
`llama-cpp-python==0.3.35`, the laptop's version (built from source with CUDA for sm_75).
Only `model.path`, `experiment`, `output_dir` and `model.quant_level: Q8_0` differ in the config.
Each `run_manifest.json` carries a `hardware` field (GPU, driver, CUDA, CPU) and a `kaggle` field
(model source URLs, SHA-256 of every GGUF, task-file hash, commit).

**Safeguard: hardware check.** Before the Q8_0 runs, the D configuration was re-run on Kaggle with the
laptop's own Q4_K_M files (same SHA-256 as `docs/model_manifest.md`) for `llama31` and `mistral_v02`, all
3 suites, written to `results_v2/KAGGLE_HWCHECK/`. The greedy trial (trial_index 0, temperature 0, 300
records per run) is compared record by record with the laptop's D greedy records
(`scripts/compare_kaggle_hwcheck.py`): prompt-hash equality, raw-output equality, parsed-call equality and
score equality. Result: **[TO FILL IN after the hardware check is imported: match rate per model and suite,
and what was concluded]**. If the greedy match is not (near-)complete, F5/R_F5 results are reported as
Kaggle-hardware results and not pooled with laptop runs without that caveat. The sampled trials are
not expected to match (llama.cpp seeding is best-effort; see README).

**Interpretation limit.** Any F5-vs-D (or R_F5-vs-R) difference is the effect of Q8_0 **plus** the
hardware/OS/CUDA-build change. The hardware check bounds the second part for the greedy trial only.

**Mistral Q8_0 source.** The itlwas repos used for the Mistral Q4_K_M files (v0.1, v0.2, v0.3) publish only
Q4_K_M. Q8_0 files for all three versions come from `QuantFactory/Mistral-7B-Instruct-v0.{1,2,3}-GGUF`
(one uploader, one naming scheme, so the three versions stay matched to each other), which is a different
uploader/quantizer from the Q4_K_M files. Source URLs and SHA-256 are in `kaggle/README.md` and every
manifest. qwen2, qwen25, qwen3 use the same org repos as their Q4_K_M files; llama3, llama31 and granite30/31/32
use the same bartowski repos.

**Scope.** F5: mistral_v01, mistral_v02, mistral_v03, qwen2, qwen25, qwen3, llama3, llama31, granite30,
granite31, granite32 (11 models x 3 suites). R_F5: held-out 8B models only (llama3, llama31, granite30,
granite31, granite32). The small models (gemma, phi) are not part of F5.

**Other notes.** Qwen3 F5 runs as a single un-split run per suite on Kaggle; the laptop pre-split Qwen3
runs only to stay inside a tool time limit, and split vs unsplit output was shown identical
(`scripts/prove_split_equivalence.py`). No result from this branch was used to choose any setting.
