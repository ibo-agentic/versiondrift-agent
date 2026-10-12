# Kaggle runner: F5 / R_F5 on 2x T4

Everything needed to run the Q8_0 quantisation factor (F5, and R_F5 for the
held-out 8B models) on Kaggle's free 2x T4, plus a hardware check that tells
you whether T4 results are comparable with the laptop's RTX 4060 results.

Nothing here has been run on a model. The notebook is built, not run.

## Files

| File | Purpose |
|---|---|
| `f5_runner.ipynb` | The notebook you run on Kaggle (thin: install, get repo, launch workers, summary). |
| `kaggle_plan.py` | The run list, model sources and expected SHA-256s. Single source of truth. |
| `kaggle_worker.py` | One process per GPU: claim a model, download + verify, run, zip, delete the model. |
| `kaggle_run_one.py` | One (protocol, model, suite) run; builds the config with the laptop's own `build_config`. |
| `kaggle_session.py` | Notebook helpers: locate repo, restore earlier runs, launch/monitor workers. |
| `kaggle_verify.py` | Checks one exported run zip (used by the Kaggle restore step and by the laptop import). |
| `make_repo_archive.py` | Builds the code archive for the Kaggle dataset from a git commit. |
| `DEVIATIONS_DRAFT.md` | Text for DEVIATIONS.md (not merged into it). |
| `../scripts/import_kaggle_results.py` | Laptop: import downloaded zips into `results_v2/`. |
| `../scripts/compare_kaggle_hwcheck.py` | Laptop: Kaggle hardware check vs the laptop's D greedy records. |

## What runs

| Phase | Config | Quant | Models | Runs |
|---|---|---|---|---|
| `hwcheck` -> `results_v2/KAGGLE_HWCHECK/` | D (unchanged) | Q4_K_M (laptop's exact files) | llama31, mistral_v02 | 2 x 3 suites = 6 |
| `F5` -> `results_v2/F5/` | D | Q8_0 | mistral_v01/v02/v03, qwen2, qwen25, qwen3, llama3, llama31, granite30/31/32 | 11 x 3 = 33 |
| `R_F5` -> `results_v2/R_F5/` | R | Q8_0 | llama3, llama31, granite30/31/32 | 5 x 3 = 15 |

54 runs of 900 records. Seed 1234, trial seeds 1234/1235/1236, temperatures
0.0/0.7/0.7, n_ctx 4096, same task files. Configs come from the laptop's
`scripts/real_run_one.build_config` (unmodified). Only these keys differ from
the laptop config of the same base protocol: `experiment`, `output_dir`,
`model.path`, and (F5/R_F5 only) `model.quant_level: Q8_0`, which the runner
already records as `run_factors.F5_quant_level` (same mechanism as `R_PC_Q2K`).
Checked offline by building all 54 configs and diffing them against the laptop's
`results_v2/_generated_configs/`. `model.thinking: default` is written
explicitly; D's older configs omit the key, and the two are identical in
`LlamaCppClient`.

Each `run_manifest.json` has every laptop field plus:

* `hardware`: GPU name/uuid/index/memory/driver/compute capability, CUDA driver API version, nvcc, CPU, kernel, Kaggle image.
* `kaggle`: model file(s) with source URL, expected and actual SHA-256, task-file SHA-256, repo commit, start time, elapsed time.

## 1. Get the code onto Kaggle (two options, recommend the first)

**Option A (recommended): private Kaggle dataset.**
1. Commit your changes and make sure this branch contains everything `main` has changed in `upgradecanary/`, `data/`, `configs/`, `analysis/audit/`, `scripts/real_run_one.py`, `scripts/real_run_models.py` (the script refuses to build a stale archive).
2. `python kaggle/make_repo_archive.py --out kaggle_repo.zip`. This is `git archive` of the commit: no results, no models, no untracked files. It adds `REPO_COMMIT.txt`.
3. kaggle.com -> Datasets -> New dataset -> upload `kaggle_repo.zip`, visibility **Private**.
4. In the notebook: Add Input -> your dataset. Leave `REPO_SOURCE = "dataset"`.

Why: no secret to manage, byte-exact commit, nothing to leak, no dependency on GitHub.

**Option B: read-only GitHub token as a Kaggle secret.**
1. GitHub -> Settings -> Developer settings -> fine-grained token: this one repository only, permission *Contents: read-only*, short expiry.
2. Kaggle notebook -> Add-ons -> Secrets -> add a secret named `GITHUB_RO_TOKEN` and attach it to the notebook.
3. In the settings cell: `REPO_SOURCE="github"`, `GITHUB_REPO="owner/name"`, `GITHUB_REF="<full 40-char commit hash>"`.

The token is read with `UserSecretsClient` at run time, used only for `git clone`, scrubbed from error text,
and the remote URL is reset right after cloning. It is never in the notebook text. Revoke it when done.
Use B only if you want to change code without re-uploading a dataset. The branch has to be pushed to GitHub first.

## 2. Run

1. New notebook -> File -> Import notebook -> `f5_runner.ipynb`.
2. Settings: Accelerator **GPU T4 x2**, Internet **On**.
3. Add the code dataset as Input.
4. Run all. Order: llama-cpp-python build (10-20 min), hardware check, F5, R_F5.

To gate on the hardware check: set `PHASES = ["hwcheck"]` for a first short session, import and compare on the
laptop (section 5), then run again with `PHASES = ["F5", "R_F5"]`. Otherwise leave all phases: the
hardware-check zips are the first produced, so you can compare them while the session continues.

Disk: Q8_0 files are 8-9 GB each. Each worker downloads one model, runs all of that model's suites, then deletes
it. GGUFs go to `/kaggle/temp`, results to `/kaggle/working`.

### Pinned llama-cpp-python

The laptop used `llama-cpp-python==0.3.35` (every `run_manifest.json`:
`model_backend.llama_cpp_python_version`; `requirements.txt` itself only says `>=0.2.90`).
The notebook installs exactly `0.3.35` with `CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=75"`
and asserts the version and `llama_supports_gpu_offload()`. If that fails the notebook stops with an
error; it does **not** install another version. Every exported run is verified again on import
(`llama_cpp_python_version` must equal `0.3.35`).
Same llama.cpp source as the laptop wheel; the compile target and CUDA toolkit differ (T4/sm_75, Linux).
That difference is what the hardware check measures.

## 3. Saving progress and resuming (12 h sessions)

* A run is the unit of progress. After every run its folder is zipped to `/kaggle/working/export/kaggle__<protocol>__<model>__<suite>.zip`. A worker does not start a run after `SESSION_BUDGET_HOURS` (11.25 h).
* **Download zips as they appear** (Output / file browser panel). Files in `/kaggle/working` are not guaranteed to survive a session that dies without being saved.
* To resume: put the downloaded zips in a private dataset (or attach the earlier notebook version's output) and Add Input. Step 5 of the notebook verifies each zip (CRC, 900/900 records, hashes, factors) and skips runs that are already complete. A failed or partial attempt is moved to `results_v2/_failed_attempts/` before a retry, so a suite never holds two run folders.

Time (an unverified estimate; the hardware check will give real numbers): the laptop took about 15 h for the
same 54-run workload (D 8B models ~30-39 min per model per 3 suites, qwen3 229 min, R held-out ~50-83 min per
model). Expect T4 Q8_0 to be slower per run, so likely **more than one session**. Kaggle's weekly GPU quota
(30 h) counts session time.

## 4. Import on the laptop

```
python scripts/import_kaggle_results.py <folder-or-zips> --dry-run
python scripts/import_kaggle_results.py <folder-or-zips>
```
Per zip: all checks of `kaggle_verify.py`; the task-file hash must equal the local `data/` file; the target
`results_v2/<protocol>/<model>/<suite>/` must not exist (never overwrites); extract to staging, recount
900/900, then move. An import log is appended to `results_v2/_kaggle_import_log.jsonl`.

## 5. Hardware check comparison

```
python scripts/compare_kaggle_hwcheck.py --kaggle-root results_v2/KAGGLE_HWCHECK --laptop-root results_v2/D
```
Compares only the greedy trial (`trial_index == 0`, 300 records per run) one to one on
(task_id, condition): prompt hash equal, raw output equal (the match rate), parsed call equal, score equal.
Prints mismatching examples. It reports counts and rates only and computes no verdicts or version-pair
differences. Not run on real data yet.

## Model sources

Expected SHA-256 = the `lfs.oid` Hugging Face publishes for each file (read from the HF tree API on 2026-10-13).
The worker recomputes the SHA-256 of the downloaded bytes and refuses to run on a mismatch; actual hashes go into
every run's `run_manifest.json`.

| Model | Quant | Used in | Source file (Hugging Face) | SHA-256 |
|---|---|---|---|---|
| llama31 | Q4_K_M | hardware check | [bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf](https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf) | `7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c` |
| mistral_v02 | Q4_K_M | hardware check | [itlwas/Mistral-7B-Instruct-v0.2-Q4_K_M-GGUF/mistral-7b-instruct-v0.2-q4_k_m.gguf](https://huggingface.co/itlwas/Mistral-7B-Instruct-v0.2-Q4_K_M-GGUF/resolve/main/mistral-7b-instruct-v0.2-q4_k_m.gguf) | `aaae8abe274e1521d5aa80bf32cf18b408fc44b9d6869acbdc815440296d275e` |
| mistral_v01 | Q8_0 | F5 | [QuantFactory/Mistral-7B-Instruct-v0.1-GGUF/Mistral-7B-Instruct-v0.1.Q8_0.gguf](https://huggingface.co/QuantFactory/Mistral-7B-Instruct-v0.1-GGUF/resolve/main/Mistral-7B-Instruct-v0.1.Q8_0.gguf) | `eb1d45a507b3f74bf9ae16189be93dcacab1dd4577f134565913b024737a7a6a` |
| mistral_v02 | Q8_0 | F5 | [QuantFactory/Mistral-7B-Instruct-v0.2-GGUF/Mistral-7B-Instruct-v0.2.Q8_0.gguf](https://huggingface.co/QuantFactory/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/Mistral-7B-Instruct-v0.2.Q8_0.gguf) | `7245da8144b0636e0a776cb3b0b706421bb02d2034b1c5e8de19cd37e05a54d9` |
| mistral_v03 | Q8_0 | F5 | [QuantFactory/Mistral-7B-Instruct-v0.3-GGUF/Mistral-7B-Instruct-v0.3.Q8_0.gguf](https://huggingface.co/QuantFactory/Mistral-7B-Instruct-v0.3-GGUF/resolve/main/Mistral-7B-Instruct-v0.3.Q8_0.gguf) | `c19dd08e2787e8337d3b58f035cfc737d4510bde5dad7415dabed80bde9d1b80` |
| qwen2 | Q8_0 | F5 | [Qwen/Qwen2-7B-Instruct-GGUF/qwen2-7b-instruct-q8_0.gguf](https://huggingface.co/Qwen/Qwen2-7B-Instruct-GGUF/resolve/main/qwen2-7b-instruct-q8_0.gguf) | `945823750c8eb6aa685692753ae90cd9551a56618d03051241268f53cdbd8352` |
| qwen25 (part 1/3) | Q8_0 | F5 | [Qwen/Qwen2.5-7B-Instruct-GGUF/qwen2.5-7b-instruct-q8_0-00001-of-00003.gguf](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q8_0-00001-of-00003.gguf) | `26e30cb4559f0d9e9e11f34d351292af6f42199ce3fa742b5e7c5af4bc35b0f0` |
| qwen25 (part 2/3) | Q8_0 | F5 | [Qwen/Qwen2.5-7B-Instruct-GGUF/qwen2.5-7b-instruct-q8_0-00002-of-00003.gguf](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q8_0-00002-of-00003.gguf) | `e93856ce0cb05d5abd698eb439c0fea3acd412d9040f5ab7d2d4d088add5287d` |
| qwen25 (part 3/3) | Q8_0 | F5 | [Qwen/Qwen2.5-7B-Instruct-GGUF/qwen2.5-7b-instruct-q8_0-00003-of-00003.gguf](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q8_0-00003-of-00003.gguf) | `8f29c0e4173d4d92d35c52a7c5807c34a3edfe6bb078ea785d145b7d88c16e44` |
| qwen3 | Q8_0 | F5 | [Qwen/Qwen3-8B-GGUF/Qwen3-8B-Q8_0.gguf](https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q8_0.gguf) | `408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6` |
| llama3 | Q8_0 | F5 + R_F5 | [bartowski/Meta-Llama-3-8B-Instruct-GGUF/Meta-Llama-3-8B-Instruct-Q8_0.gguf](https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF/resolve/main/Meta-Llama-3-8B-Instruct-Q8_0.gguf) | `583c616da14b82930f887f991ab446711da0b029166200b67892d7c9f8f45958` |
| llama31 | Q8_0 | F5 + R_F5 | [bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/Meta-Llama-3.1-8B-Instruct-Q8_0.gguf](https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q8_0.gguf) | `9da71c45c90a821809821244d4971e5e5dfad7eb091f0b8ff0546392393b6283` |
| granite30 | Q8_0 | F5 + R_F5 | [bartowski/granite-3.0-8b-instruct-GGUF/granite-3.0-8b-instruct-Q8_0.gguf](https://huggingface.co/bartowski/granite-3.0-8b-instruct-GGUF/resolve/main/granite-3.0-8b-instruct-Q8_0.gguf) | `b470554539f90a26c0a2d23d7df7398a4f46cff6f5cecfb2778fc110ff6483cd` |
| granite31 | Q8_0 | F5 + R_F5 | [bartowski/granite-3.1-8b-instruct-GGUF/granite-3.1-8b-instruct-Q8_0.gguf](https://huggingface.co/bartowski/granite-3.1-8b-instruct-GGUF/resolve/main/granite-3.1-8b-instruct-Q8_0.gguf) | `70d56efa48c46d941790f17fa0486528e9aab8b82b4e453d2e09e932570a092a` |
| granite32 | Q8_0 | F5 + R_F5 | [bartowski/ibm-granite_granite-3.2-8b-instruct-GGUF/ibm-granite_granite-3.2-8b-instruct-Q8_0.gguf](https://huggingface.co/bartowski/ibm-granite_granite-3.2-8b-instruct-GGUF/resolve/main/ibm-granite_granite-3.2-8b-instruct-Q8_0.gguf) | `e93b442ba2ce753cf1a3904c6ebd1ccfc3f961f5eb8ccc34b9a7e2e4cc1d14a4` |

The Q4_K_M files are the laptop's own (hashes match `docs/model_manifest.md`).

**Mistral Q8_0 is not from the Q4_K_M uploader.** The three itlwas repos used for Q4_K_M ship only Q4_K_M
(verified through the HF API; same situation as the Q2_K control for v0.3). QuantFactory is the one uploader
with v0.1, v0.2 and v0.3 at Q8_0 under one naming scheme, so the three Mistral versions stay matched to each
other. Alternatives found: TheBloke (v0.1, v0.2 only), MaziyarPanahi (all three), bartowski (v0.3 only).
To change it, edit `Q8_SOURCES` in `kaggle_plan.py` (hash + size) and nothing else.

## Not verified here

* That `llama-cpp-python==0.3.35` compiles against Kaggle's current CUDA image (nothing was built or run).
* Real T4 speed, hence the number of sessions needed.
* That Kaggle keeps `/kaggle/working` after a session timeout; hence "download zips as they appear".
