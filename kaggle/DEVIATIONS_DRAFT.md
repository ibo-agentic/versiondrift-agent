## 2026-10-13: F5 (Q8_0) and R_F5 for the 8B models are run on Kaggle 2x T4, not on the laptop

**Origin, not a new deviation in intent.** PLAN.md's F5 row already says "8B models on Kaggle (16 GB GPU);
small models locally", and its compute-budget paragraph says "Q8 runs for 8B models on Kaggle". The reason is hardware: a Q8_0
8B model is about 8.5 GB, which does not fit in the laptop's 8 GB of VRAM (RTX 4060) with the KV cache at
n_ctx 4096, and every other run in this study is fully offloaded (`n_gpu_layers: -1`). The T4s have 16 GB each.
This entry records how it was done and what safeguards apply, because it means F5 and R_F5 differ from D and R in
hardware as well as in quantisation level.

**Machines.** Kaggle (Linux, 2x NVIDIA T4, one worker process per GPU): Mistral v0.1/v0.2/v0.3, Qwen2/2.5/3,
Llama 3/3.1, Granite 3.0/3.1/3.2. Laptop (RTX 4060): Phi-3/3.5/4-mini and Gemma-2-2B/3-4B, run locally at Q8_0
as PLAN.md says. **Every upgrade pair runs entirely on one machine**, so no pair difference mixes hardware.
Cross-machine comparison only happens between a pair's Q4_K_M and Q8_0 results (F5 effect), which is why the
hardware check below is needed.

**What was kept identical.** `upgradecanary` code and the laptop's own `scripts/real_run_one.build_config`
(the commit is recorded in every manifest as `kaggle.repo_commit`); seed 1234 and trial seeds 1234/1235/1236;
trial temperatures 0.0/0.7/0.7; task files (SHA-256 recorded, checked on import); perturbations; `max_tokens`
256 (F5) / 1024 (R_F5); constrained decoding off (F5) / generic_json (R_F5); n_ctx 4096;
`llama-cpp-python==0.3.35` (the laptop's version, built from source with CUDA for sm_75). Only `model.path`,
`experiment`, `output_dir` and `model.quant_level: Q8_0` differ in the config. Each `run_manifest.json` has a
`hardware` field (GPU, driver, CUDA, CPU, image) and a `kaggle` field (model source URLs, SHA-256 of every GGUF,
task-file hash, commit).

**Safeguard: hardware check.** The D configuration was re-run on Kaggle with the laptop's own Q4_K_M files
(same SHA-256 as `docs/model_manifest.md`) for the adjacent pair `llama3` and `llama31`, 3 suites, 6 runs,
written to `results_v2/KAGGLE_HWCHECK/`. Two readings are reported:
(1) record level: greedy trial (trial_index 0, 300 records per run) compared with the laptop's D greedy records
(`scripts/compare_kaggle_hwcheck.py`): prompt, raw output, parsed call and score equality;
(2) pair level: the llama3 -> llama31 pair difference computed from the Kaggle Q4_K_M runs minus the same pair
difference from the laptop D runs. This is the **hardware-check difference**.
Result: **[TO FILL IN after import: per-model/suite greedy match rate and the llama3 -> llama31 hardware-check
difference]**.

**Kaggle session 1 runs only the hardware check. It passes if each run's greedy score and parse rate are within
0.03 of the laptop D run; if not, F5/R_F5 on Kaggle stop until the cause is found.** (Per run = per model x suite,
6 runs; greedy = trial_index 0; computed by `vdanalysis/hwcheck.py`, table `hwcheck_runs`. An incomplete check
is never a pass.) F5 and R_F5 sessions are started only after the check has been imported and has passed.

**How F5 / R_F5 are reported.** F5 and R_F5 8B results are reported next to the hardware-check difference for
the llama3 -> llama31 pair; any F5 flip smaller than that difference is labeled "within hardware noise".
The sampled trials are not expected to match across machines (llama.cpp seeding is best-effort), so they
are not used for the record-level check.

**Mistral Q8_0 source.** The itlwas repos used for the Mistral Q4_K_M files (v0.1, v0.2, v0.3) publish only
Q4_K_M. The Q8_0 files for all three versions come from `QuantFactory/Mistral-7B-Instruct-v0.{1,2,3}-GGUF`
(one uploader and naming scheme, so the three versions stay matched to each other), which is a different
uploader/quantizer from the Q4_K_M files. Qwen2/2.5/3 use the same org repos as their Q4_K_M files;
Llama 3/3.1 and Granite 3.0/3.1/3.2 use the same bartowski repos. Source URLs and SHA-256 are in
`kaggle/README.md` and every manifest.

**Scope on Kaggle.** F5: mistral_v01, mistral_v02, mistral_v03, qwen2, qwen25, qwen3, llama3, llama31, granite30,
granite31, granite32 (11 models x 3 suites = 33 runs). R_F5: held-out 8B models only (llama3, llama31, granite30,
granite31, granite32; 15 runs). Hardware check: 6 runs (session 1). Sessions are time-boxed (no new run after 10.5 h);
each later session resumes from verified zips, so a run is never split across sessions.

**Other notes.** Qwen3 F5 runs as a single un-split run per suite on Kaggle; the laptop pre-split Qwen3 runs
only to stay inside a tool time limit, and split vs unsplit output was shown identical
(`scripts/prove_split_equivalence.py`).
