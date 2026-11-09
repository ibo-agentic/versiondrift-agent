# Status report: upgrade-verdict stability study

Snapshot: 2026-11-07, about 06:00 UTC. Everything below comes from files in this repository (code, configs, result files, logs, notes, git log). Where something is not in the files, the text says "not in files". No Phase 2 hypothesis has been analysed yet, so this report contains no Phase 2 results.

## 0. Summary

- The study asks whether reasonable evaluation-setup choices ("factors") change the verdict (harmful / neutral / beneficial) of a model upgrade for small open-weight tool-using models.
- **Phase 1** (pre-registered as `plan-v1`, 2026-10-05; finished and analysed 2026-10-15, tags `runs-complete` and `analysis-complete`): 16 models, 10 upgrade pairs, 3 task suites, so 30 decisions. Result: H1 supported, H2 not supported, H3 not supported, H4 supported, H5 not supported (details in section 2.9).
- **Phase 2** (pre-registered as `plan-v2`, 2026-10-19): the same design with 10 trials instead of 3, a bigger A/A control, same-hardware baselines for F5, and 10-trial positive controls. Laptop part: **355 of 372 runs done, 17 left (about 22 h by the manifest estimate)**. Kaggle part: **0 of 81 runs imported**. Phase 2 analysis has not been run on real data.
- Open problems for Phase 2: the Kaggle runs are the bottleneck for the W3 gate date (2026-11-20), and one W3 prerequisite file (`results_v3/W0_determinism/split_test/R_result.json`) does not exist yet (section 3).
- The Phase 1 result tables (`analysis_out/`), raw runs (`results_v2/`) and Phase 2 runs (`results_v3/`) are git-ignored. They exist only on the laptop and in the OneDrive backups (section 6).

---

## 1. Setup

### 1.1 Models

Source: `docs/model_manifest.md` (SHA-256 of every file is there). All models are GGUF files run through llama.cpp. Main precision is Q4_K_M. Sizes are file sizes.

| Short name | File (under `models/`) | Size GiB | Source repo | Family / split in PLAN.md |
|---|---|---|---|---|
| mistral_v01 | itlwas/mistral-7b-instruct-v0.1-q4_k_m.gguf | 4.07 | itlwas/Mistral-7B-Instruct-v0.1-Q4_K_M-GGUF | Mistral 7B, design |
| mistral_v02 | itlwas/mistral-7b-instruct-v0.2-q4_k_m.gguf | 4.07 | itlwas/...-v0.2-Q4_K_M-GGUF | design |
| mistral_v03 | itlwas/mistral-7b-instruct-v0.3-q4_k_m.gguf | 4.07 | itlwas/...-v0.3-Q4_K_M-GGUF | design |
| qwen2 | qwen/qwen2-7b-instruct-q4_k_m.gguf | 4.36 | Qwen/Qwen2-7B-Instruct-GGUF | Qwen, design |
| qwen25 | qwen/qwen2.5-7b-instruct-q4_k_m-0000{1,2}-of-00002.gguf (split) | 3.72 + 0.64 | Qwen/Qwen2.5-7B-Instruct-GGUF | design |
| qwen3 | qwen/Qwen3-8B-Q4_K_M.gguf | 4.68 | Qwen/Qwen3-8B-GGUF | design |
| llama3 | llama/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf | 4.58 | bartowski/Meta-Llama-3-8B-Instruct-GGUF | Llama, held-out |
| llama31 | llama/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf | 4.58 | bartowski/Meta-Llama-3.1-8B-Instruct-GGUF | held-out |
| phi3_mini | phi/Phi-3-mini-4k-instruct-Q4_K_M.gguf | 2.23 | bartowski/Phi-3-mini-4k-instruct-GGUF | Phi mini, held-out |
| phi35_mini | phi/Phi-3.5-mini-instruct-Q4_K_M.gguf | 2.23 | bartowski/Phi-3.5-mini-instruct-GGUF | held-out |
| phi4_mini | phi/microsoft_Phi-4-mini-instruct-Q4_K_M.gguf | 2.32 | bartowski/microsoft_Phi-4-mini-instruct-GGUF | held-out |
| granite30 | granite/granite-3.0-8b-instruct-Q4_K_M.gguf | 4.60 | bartowski/granite-3.0-8b-instruct-GGUF | Granite 8B, held-out |
| granite31 | granite/granite-3.1-8b-instruct-Q4_K_M.gguf | 4.60 | bartowski/granite-3.1-8b-instruct-GGUF | held-out |
| granite32 | granite/ibm-granite_granite-3.2-8b-instruct-Q4_K_M.gguf | 4.60 | bartowski/ibm-granite_granite-3.2-8b-instruct-GGUF | held-out |
| gemma2_2b | gemma/gemma-2-2b-it-Q4_K_M.gguf | 1.59 | bartowski/gemma-2-2b-it-GGUF | Gemma, held-out |
| gemma3_4b | gemma/google_gemma-3-4b-it-Q4_K_M.gguf | 2.32 | bartowski/google_gemma-3-4b-it-GGUF | held-out |

Parameter counts beyond what the model names say are not in files.

**Upgrade pairs (10):** mistral v01→v02, v02→v03; qwen2→qwen25, qwen25→qwen3; llama3→llama31; phi3_mini→phi35_mini, phi35_mini→phi4_mini; granite30→granite31, granite31→granite32; gemma2_2b→gemma3_4b. Size-changing pairs: qwen25→qwen3 and gemma2_2b→gemma3_4b (PLAN.md section 2; results are also reported separately for size-changing and size-preserving pairs).
Pairs: 4 design (Mistral, Qwen) and 6 held-out.

**Other model files**
- Q2_K positive-control files (4 models: qwen25, llama31, granite32, mistral_v03). The mistral_v03 Q2_K comes from a different uploader (bartowski) because the itlwas repo has no Q2_K. Details in `docs/model_manifest.md` section 6 and `DEVIATIONS.md`, 2026-10-11.
- Q8_0 files for F5: 5 small models stored locally (gemma2_2b, gemma3_4b, phi3_mini, phi35_mini, phi4_mini; manifest section 7). The 8B models' Q8_0 files are downloaded on Kaggle (sources and hashes in `kaggle/README.md`, `kaggle/phase2/p2_sources.py`).

### 1.2 Datasets (three suites, 100 tasks each in Phase 1)

| Suite | Size | Source and construction | Files |
|---|---|---|---|
| synthetic | 100 | Generated by `scripts/generate_tasks.py` (deterministic). 6 tools with 20/20/15/15/15/15 tasks; stratified `drift_type` hints. Note from the Phase 2 work: only 54 distinct baseline prompts among the 100 tasks (`PLAN_PHASE2.md` section 3, W3). | `data/base_tasks.jsonl` |
| bfcl_simple | 100 | Derived from BFCL `BFCL_v4_simple_python.json`. Metadata-only deterministic selection, seed 20260930, stratified by parameter-type signature, 11 eligibility rules (`docs/protocol.md`). 191 items are eligible in total. | `data/bfcl_tasks.jsonl`, `..._provenance.jsonl` |
| bfcl_multiple | 100 | Derived from BFCL `BFCL_v4_multiple.json` (200 records). Eligibility uses a 3500-character rendered-prompt budget (109 of 200 eligible); then the same seeded stratified selection. Schema drift is applied only to the gold tool's schema. PLAN.md section 3 states this biases the suite toward shorter multi-tool tasks. | `data/bfcl_multiple_tasks.jsonl` |

The BFCL suites are "BFCL-derived schema-match" suites with a simulated deterministic executor. They are not comparable with BFCL leaderboard numbers (`README.md`, `docs/protocol.md`). `enum_drift` is excluded for BFCL because `simple_python` has no enums.

Phase 2 (W3, not run) adds the remaining eligible BFCL items: `data/phase2/w3_added_bfcl_simple*.jsonl` (+91) and `w3_added_bfcl_multiple*.jsonl` (+9).

### 1.3 Conditions, metrics, gate

- **Conditions per task:** `baseline`, `schema_drift` (field_rename, field_drop, type_mutation, unexpected_field; enum_drift on synthetic only), `fault_reporting` (redesigned in Phase 1: after a tool result, possibly with an injected timeout, tool_exception, empty_result or partial_result, the model must reply `{"status": "ok"|"failed"|"incomplete", "answer": ...}`; clean cases are included; scoring rule in PLAN.md section 3).
- **Record score (strict, no LLM judge):** `parse_ok ∧ tool_name_ok ∧ args_intent_match ∧ args_valid_under_drift ∧ executor_ok` for tool-call conditions; the fault_reporting rule for that condition. `args_exact` is diagnostic only.
- **Stress diff** = new minus old, equal-weight over the stress conditions (schema_drift, fault_reporting).
- **Gate:** point gate (harmful if diff < −0.05, beneficial if > +0.05, else neutral); CI gate (task-level cluster bootstrap, 10,000 reps, seed 1234; harmful needs point < −0.05 and upper 95% bound < 0, beneficial the mirror).
- **Unit of analysis:** adjacent pair × suite = 30 decisions. Flip rate = share of decisions whose label differs from D's label under a factor level.
- **Factors (changed one at a time from D):** F1 output budget 256→1024; F2 Qwen3 thinking off; F3 native tool template; F4 generic-JSON constrained decoding; F5 Q4_K_M→Q8_0; F6 model-recommended sampling; F7 lenient parsing (rescore); F8 relaxed intent (rescore); F9 CI gate (rescore); F10 greedy trial only (subsample); F11 legacy chat wrapping (Mistral and Qwen only). A fuller table is in `PLAN.md` section 5. R = the "robust protocol" (output budget 1024, generic-JSON constrained decoding, CI gate, etc., `PLAN.md` section 7).

### 1.4 Prompts

- **D (default):** one shared JSON-in-prompt tool description (tool schema dumped as JSON plus "reply with ONLY a single JSON object"), wrapped in each model's own chat template read from the GGUF (`tokenizer.chat_template`), plain turns only (`PLAN.md` section 4; `upgradecanary/runner.py` `build_prompt`).
- **Drift and fault prompts** are drawn from the **run seed** hashed with task id and condition; all trials of a run share the same prompt, and the old and new model of a pair see byte-identical prompts (checked on all 30 pair-suites in D, 900/900 records each; `results_v3/W0_determinism/PROMPT_SEED_REPORT.md`).
- Exact prompt text per record is stored in each run's `raw_outputs.jsonl`.

### 1.5 Decoding settings (D)

From `PLAN.md` section 4, `docs/sampling_presets.md` and a Phase 2 `run_manifest.json`:
`n_ctx` 4096, `n_gpu_layers` −1, `max_tokens` 256, strict JSON parsing, no constrained decoding, Qwen3 thinking left at the model default (on), stop tokens derived from each model's template. Sampled trials use top_p 0.95, top_k 40, min_p 0.05, repeat_penalty 1.0. Backend: `llama-cpp-python` 0.3.35 (CUDA).

### 1.6 Trials and seeds

- **Phase 1:** run seed 1234; 3 trials per task-condition: trial seeds 1234, 1235, 1236 with temperatures 0.0, 0.7, 0.7. 900 records per run (100 tasks × 3 conditions × 3 trials).
- **Phase 2:** run seed 1234 for every run. Main trial seeds 1234…1243 (1 greedy + 9 sampled at 0.7). On the laptop, Phase 1 trials 1–3 are reused and only trials 4–10 (seeds 1237–1243) are run (3000 merged records per run). On Kaggle all 10 trials are run fresh. The A/A second arm uses run seed 1234 and trial seeds 5678–5687. F6 uses each model's preset temperatures.
- Other seeds: BFCL selection 20260930, CI bootstrap 1234, W3 synthetic generator 20261019 (unused), human-label sampling 20261020 (W6, not done).

### 1.7 Hardware

- Laptop with an RTX 4060 (8 GB VRAM) running Windows. Phase 1 laptop runs and all Phase 2 laptop runs.
- Kaggle 2 × Tesla T4 for the Q8_0 runs of the 8B models (F5, R_F5) in Phase 1 (33 + 15 runs per `PROMPT_SEED_REPORT.md` section 5). Phase 2 plans Kaggle runs for F5, same-hardware D and R baselines.
- CPU model, RAM: not in files.

---

## 2. Experiments in time order

Dates are commit or log dates. Result file paths are given for each; the raw run folders and `analysis_out/` are git-ignored (see section 6).

### 2.1 2026-09-27/28: mock pilot and first real pilot (exploratory)
- Mock pilot: deterministic mock provider, 100 tasks (commit `1875c15`). Results: not in files.
- Real pilot Mistral v0.2 vs v0.3, mixed quantizers (TheBloke vs bartowski files), n=100 per condition. `docs/experiment_log.md` 2026-09-28 entries: the first comparison (baseline 100→88, schema_drift 66→55, runtime_fault 78→100) was an artifact of two harness bugs (calculator-whitespace intent matching; type coercion/drift-only-field handling). After fixes and a score redefinition to "functional success", baseline is 1.00/1.00, schema_drift 0.84/0.82 (CI [−0.120, +0.080]), runtime_fault 0.78/1.00 (+0.220, CI [+0.140, +0.300]). A third bug (arithmetic check keyed on the argument name "expression") invalidated earlier schema_drift conclusions. Run folders: `results/upgradecanary-real-pilot-v0.*`.

### 2.2 2026-09-29: matched Mistral v0.1/v0.2/v0.3 study
- 100 synthetic tasks × 3 conditions × 3 trials, itlwas Q4_K_M set, n_ctx 2048. Scores (v0.1/v0.2/v0.3): baseline 1.00/1.00/0.97; schema_drift 0.99/0.90/0.93; runtime_fault 1.00/0.76/0.97 (`docs/protocol.md`).
- v0.1→v0.2: stress diff −0.168, 95% CI [−0.218, −0.122]; v0.2→v0.3: +0.123, CI [+0.062, +0.180]; v0.1→v0.3: −0.045 (`docs/results_summary.md` section 2).
- Same day: release-gate simulation (30-task "canary"), leave-one-upgrade-out validation. Files: `tables/*.csv`, `docs/experiment_log.md`.

### 2.3 2026-09-30: Qwen2.5→Qwen3 and gate analyses
- Qwen2.5 vs Qwen3 on synthetic: pooled stress −0.042 (CI [−0.078, −0.007]), gate-neutral, with category swaps (field_drop 0.40→1.00, unexpected_field 1.00→0.13).
- Cross-family gate transfer, threshold sensitivity (t = 0.01…0.10, k = 10…50), canary calibration. Frozen protocol written (`docs/protocol.md`, 2026-09-30). Files: `docs/experiment_log.md`, `scripts/analyze_*.py`, `scripts/validate_*.py`.

### 2.4 2026-09-30 to 10-01: BFCL-100 phase
- Full BFCL-100 runs (Mistral ×3, Qwen2.5, Qwen3). **Invalidated on 2026-10-01** because schema_drift prompts showed the original schema while scoring used the drifted one (section 4). Corrected runs (authoritative), from `docs/results_summary.md`:

| Suite | Model | baseline | schema_drift | runtime_fault | stress |
|---|---|---|---|---|---|
| bfcl_simple (old "BFCL") | Mistral v0.1 | 0.890 | 0.690 | 0.883 | 0.787 |
| | Mistral v0.2 | 0.807 | 0.623 | 0.720 | 0.672 |
| | Mistral v0.3 | 0.943 | 0.777 | 0.940 | 0.858 |
| | Qwen2.5 | 0.950 | 0.923 | 0.950 | 0.937 |
| | Qwen3 | 0.850 | 0.693 | 0.720 | 0.707 |

  (The same file has the synthetic-suite rows.) Decisions: v0.1→v0.2 −0.115 (harmful), v0.2→v0.3 +0.187 (beneficial), v0.1→v0.3 +0.072 (beneficial), Qwen2.5→Qwen3 −0.230 (harmful). Files: `docs/results_summary.md`, `tables/upgrade_decisions.csv`, `docs/experiment_report.md`.

### 2.5 2026-10-02: reviewer audit and follow-ups
- `AUDIT.md` (read-only audit; 24 questions, some verdicts "BUG" or "CONFOUND RISK") and `analysis/audit/*` follow-ups: Qwen3 thinking-mode reruns (nothink, think_long), escape-repair parsing check, fault rescoring, intent spot-check (40 records, one labeler: 32/40 agreement, Cohen's kappa 0.60; all 8 disagreements were rule=False, human=True).
- Qwen3 BFCL result after the thinking fix (`analysis/audit/verdict_flips.md`): Qwen2.5→Qwen3 changes from harmful (−0.230) to neutral (+0.015 nothink, −0.002 think_long). Qwen3-nothink scores on BFCL: baseline 0.967, schema_drift 0.937, runtime_fault 0.967 (`analysis/audit/qwen3_rerun.md`). 5 of the 24 audit rows are label flips.

### 2.6 2026-10-03 to 10-05: engineering, smoke tests, PLAN v1
- F1–F6 switches, BFCL-multiple suite, fault_reporting condition, A/A and control mechanism, native chat wrapping (commits `4d65949` … `395d374`).
- Smoke tests: 16 models, D/F3/F4, 1,800 generations (`analysis/plan/smoke_report.md`). Found three fixes: fault_reporting scoring rule (Fix 1), F3 native tool parsing per model family (Fix 2), F6 sampling presets re-verified (Fix 3), plus Phi-4-mini F3 (tools never reached the prompt) and F3/D prompt parity.
- **PLAN v1** committed 2026-10-05 (tag `plan-v1`, commit `746c67a`).

### 2.7 2026-10-05 to 10-15: Phase 1 runs (all under `results_v2/`)
Counts and hours are from commit messages and `DEVIATIONS.md`.

| Date done | Protocol | What | Runs | Hours |
|---|---|---|---|---|
| 10-05 | D | default, 16 models × 3 suites | 48 | 11.5 (laptop, `PROMPT_SEED_REPORT.md`) |
| 10-05 | F2 | Qwen3 thinking off | 3 | 0.5 |
| 10-06 | F1 | output budget 1024 | 48 | 13.4 |
| 10-07 | F3 (+F3_rerun) | native tool template (rerun for Granite-3.0 parser) | 24 (+3) | 8.0 |
| 10-08 | F6 | recommended sampling | 48 | 11.4 |
| 10-09 | F4_json | generic-JSON constrained decoding | 48 | 20.2 |
| 10-11 | R | robust protocol | 48 | 21.1 |
| 10-12 | controls | A/A (R_AA, 18), no-description (R_PC_NODESC, 12), Q2_K (R_PC_Q2K, 12) | 42 | not in one file |
| 10-13 | F11, R_F6, R_F3 | chat wrapping legacy; R with F6 and F3 | 42 | 13.9 |
| 10-13/14 | F5, R_F5 | Q8_0: 8B models on Kaggle 2×T4 (33 + 15 runs), 5 small models on laptop (30 runs, 9.8 h) | 78 | see `PROMPT_SEED_REPORT.md` §5 |

Scoring-only factors (F7, F8, F9, F10) are rescored from existing D records (`scripts/rescore_*.py`, `rescored/`).

### 2.8 2026-10-14/15: Kaggle hardware check
- Laptop D greedy vs Kaggle T4 on 6 runs (`analysis_out/hwcheck_summary.csv`): all within tolerance, max |hardware diff| in stress score 0.0183, 1 pair-suite label changed (llama3→llama31 bfcl_simple: neutral on laptop, harmful on Kaggle; `analysis_out/hwcheck_pair.csv`).

### 2.9 2026-10-15: Phase 1 analysis (tag `analysis-complete`, commit `995d8b2`)
Files: `analysis_out/*.csv`, `analysis_out/report.md`. 30 decisions.

**Hypotheses** (`analysis_out/hypotheses.csv`):

| H | Statement (short) | Value | Result |
|---|---|---|---|
| H1 | ≥20% of 30 decisions flip under ≥1 factor (F1–F10) | 13/30 = 43.3% | supported |
| H2 | Format factors (F1, F2, F4, F7) flip more than others (F3, F5, F6, F8) | 11.1% (10/90) vs 14.8% (12/81) | **not supported** (supported only within size-changing pairs: 33.3% vs 4.8%) |
| H3 | Flipping decisions have smaller median \|stress diff\| under D | 0.0383 (flipped, n=13) vs 0.0367 (never flipped, n=17) | **not supported** |
| H4 | R disagrees less than D across {F3, F5, F6}, held-out pairs | pooled/primary 6/36 = 16.7% vs 14/36 = 38.9% | supported |
| H5 | Under R: A/A false alarms ≤5% and positive-control detection ≥90% | false alarms 1/18 = 5.6%; detection pooled 13/24 = 54.2% | **not supported** |

**Controls** (`analysis_out/controls_summary.csv`, `analysis_out/controls.csv`): A/A under R: 1 harmful label in 18 decisions (llama31 bfcl_multiple, stress diff −0.111). Q2_K positive control detected 10/12 (83.3%). No-description control detected 3/12 (25.0%).

**Flip rate by factor** (main variant, all pairs; `analysis_out/flip_rates_by_factor.csv`):

| Factor | Flips / decisions | Rate |
|---|---|---|
| F1 | 3 / 30 | 10.0% |
| F2 | 3 / 3 | 100% |
| F3 | 2 / 9 (all-variant 9 / 21) | 22.2% (42.9%) |
| F4 | 3 / 27 | 11.1% |
| F5 | 8 / 30 | 26.7% |
| F6 | 1 / 12 | 8.3% |
| F7 | 1 / 30 | 3.3% |
| F8 | 1 / 30 | 3.3% |
| F9 | 0 / 30 | 0% |
| F10 | 1 / 30 | 3.3% |
| F11 | 5 / 12 | 41.7% |

**Decisions under D** (stress diff; the point-gate and CI-gate labels are identical for all 30 decisions, the flip analysis uses the point gate for D; `analysis_out/decisions_D.csv`):

| Pair | synthetic | bfcl_simple | bfcl_multiple |
|---|---|---|---|
| mistral v01→v02 | −0.038 neutral | −0.058 harmful | −0.083 harmful |
| mistral v02→v03 | +0.028 neutral | +0.117 beneficial | +0.142 beneficial |
| qwen2→qwen25 | +0.183 beneficial | +0.120 beneficial | +0.138 beneficial |
| qwen25→qwen3 | −0.083 harmful | −0.340 harmful | −0.500 harmful |
| llama3→llama31 | −0.008 neutral | −0.042 neutral | +0.012 neutral |
| phi3_mini→phi35_mini | −0.053 harmful | +0.013 neutral | −0.037 neutral |
| phi35_mini→phi4_mini | +0.020 neutral | +0.033 neutral | +0.065 beneficial |
| granite30→granite31 | +0.022 neutral | +0.037 neutral | +0.003 neutral |
| granite31→granite32 | +0.022 neutral | +0.013 neutral | +0.028 neutral |
| gemma2_2b→gemma3_4b | −0.015 neutral | +0.028 neutral | +0.048 neutral |

### 2.10 2026-10-19 (and after): Phase 2

**Setup work (commits on 2026-10-19):** analysis code `vdanalysis/phase2/`, run tooling `scripts/phase2/`, manifests `configs/phase2/*.json`, Kaggle notebook `kaggle/phase2/`, W3 task files. Regression check: the Phase 2 code in "phase 1 mode" reproduces all Phase 1 tables with 0 differences (`analysis/phase2/regression_phase1_result.md`: decisions_D 30 rows, decisions_all_protocols 360, factor_flips_long 276, flip_rates_by_factor 68, controls 42, controls_summary 3, hypotheses 19). **PLAN_PHASE2 locked at tag `plan-v2`** (commit `9ddd85e`).

**W0 determinism checks** (`results_v3/W0_determinism/`):
- Part A: Phase 1 R vs R_AA, all records (the two arms used different run seeds, so many prompts differ). Greedy trial: 63.4% raw outputs identical, 90.0% strict scores identical (n=5400); sampled trials: 45.5% raw identical, 86.1% scores identical (n=10800) (`partA_raa.json`). Split by whether the prompt was identical (`partA_breakdown.json`): greedy with identical prompt 100% raw identical (n=3006), greedy with different prompt 17.4% (n=2394); sampled with identical prompt 70.3% raw identical (n=6012), sampled with different prompt 14.3% (n=4788).
- Part B: 3 laptop re-runs of Phase 1 runs (gemma2_2b/synthetic, phi3_mini/bfcl_simple, gemma3_4b/bfcl_multiple): 900/900 records identical in raw output, parsed call and score, every trial (`partB_result.json`).
- Split test (gemma2_2b/synthetic, first 10 tasks, 300 records): one 10-trial run vs 3 trials + separately run 7 trials: strict score identical for 100% of records, raw output for 99.33% (2 of 300 records differ, both first sampled trial of the separate run, whitespace or number-text differences) (`split_test/split_test_report.md`).
- Part C (optional Kaggle re-run): not done (notebook prepared in `kaggle/w0/`).

**Sanity check of the first 3 runs** (`results_v3/sanity_check_first3.md`): D/gemma2_2b on all 3 suites, 2100 records each, merge with Phase 1 passes, parse and truncation rates of new trials match Phase 1 (e.g. bfcl_simple tool-call parse rate 97.71% new vs 98.00% Phase 1; truncation 0.19% vs 0.11%).

**Laptop queue progress** (computed from `results_v3/*/*/*/_status.json`, 2026-11-07; hours are the sum of `elapsed_seconds`, which includes time lost when the PC slept or was paused):

| Folder | Workstream | Runs done / planned | Run hours so far |
|---|---|---|---|
| D | W1 | 48 / 48 | 25.7 |
| R | W1 | 48 / 48 | 39.5 |
| F1 | W1 | 48 / 48 | 33.2 |
| F2 | W1 | 3 / 3 | 1.2 |
| F3 | W1 | 24 / 24 | 20.7 |
| F4_json | W1 | 48 / 48 | 38.5 |
| F5 (small models) | W1 | 15 / 15 | 12.4 |
| F6 | W1 | 18 / 18 | 15.4 |
| R_AA2 | W2 (R) | 48 / 48 | 76.7 |
| R_PC_Q2K | W2b | 12 / 12 | 13.5 |
| R_PC_NODESC | W2b | 12 / 12 | 14.3 |
| D_AA2 | W2 (D) | 31 / 48 (queue says 355 done in total, i.e. 17 left) | 18.3 |
| **Total** | | **355 / 372** | **309.4** |

W1 laptop was finished on 2026-10-31; W2 R on 2026-11-05; W2b before 2026-11-06 13:19 UTC. No result from these runs has been analysed yet; P1–P7 are not computed.

---

## 3. Running now, half-finished, and what blocks it

1. **Laptop queue (running).** `python -m scripts.phase2.run_laptop`, detached. Remaining: the last 17 `D_AA2` runs (W2 D), in the order: granite31 (2), granite30 (3), phi4_mini (3), mistral_v02 (3), phi35_mini (3), then the three long `D_AA2/qwen3` runs (manifest estimates 3.56, 4.50 and 4.68 h; the earlier `R_AA2/qwen3` runs took 1.5–1.9× their estimates). Manifest estimate for what is left: about 22 h. No FAILED lines in `results_v3/phase2_laptop_progress.log`.
2. **Kaggle W1 (not started in files).** `configs/phase2/W1_kaggle.json`: 81 runs, 136.8 single-GPU hours, 10 batches (K01–K10, two lanes per T4 pair, lanes up to about 9 h). K01 upload bundle exists in `kaggle_upload/` (git-ignored). `results_v3` contains no Kaggle folders (no `D_KAGGLE`, `R_KAGGLE`, or Kaggle-model `F5` runs), so 0 of 10 batches are imported. Whether K01 has been uploaded is not in files.
3. **W3 gate (will not open yet).** `scripts/phase2/run_laptop.py` `w3_gate` needs by 2026-11-20: W1_laptop, W1_kaggle, W2_R, W2_D, W2b complete; `results_v3/W0_determinism/split_test/R_result.json` with `all_identical` true; added-task files present. Blocking items today: W1_kaggle (0/81), W2_D (31/48 done), and the R split-equivalence file does not exist (only `D_result.json` is there). A W3 run list exists (64 runs, 34.5 h, bfcl only).
4. **Not started / not in files:** W4 rescoring and Phase 2 analysis on real data (`rescored_v3/`, `analysis_out_v3/` has only the regression output), W5 closed-model pairs (budget cap $40, no run files), W6 human labels (no label file; second labeler "TBD" in the plan).
5. **GPU deadline** 2026-12-10 (plan): runs not finished by then are dropped and reported as not done.

---

## 4. Bugs, reruns, thrown-away results, big code changes

### 4.1 Bugs and invalidated results (from `docs/experiment_log.md`, `DEVIATIONS.md`, `AUDIT.md`, git log)

| Date | What | Effect |
|---|---|---|
| 09-28 | Intent matching compared calculator expressions as literal strings; type coercion and drift-only fields not handled before execution | First v0.2 vs v0.3 pilot comparison discarded; score redefined to functional success |
| 09-28 | Arithmetic equivalence keyed on the argument name "expression" | Earlier schema_drift conclusions invalid |
| 10-01 | **BFCL drift-prompt bug**: prompts showed the original schema while scoring used the drifted one (100% of BFCL schema_drift records) | All earlier BFCL schema_drift results invalidated; scores moved by +0.43 to +0.71 (AUDIT.md); one label flipped (Mistral v0.1→v0.3 BFCL, neutral→beneficial); runs redone |
| 10-02 | Qwen3 thinking truncation under max_tokens 256 (AUDIT.md: 67–69% of Qwen3's failures were format failures, mostly unclosed `<think>`) | Qwen2.5→Qwen3 BFCL verdict flips from harmful to neutral with thinking off; motivated F1/F2/F4 |
| 10-02 | Old runtime_fault design could not test fault handling for most records (AUDIT.md E11) | Replaced by `fault_reporting` in PLAN v1; old condition "not rerun" |
| 10-04/05 | fault_reporting scoring rule replaced (Fix 1); F3 native parsing per model family (Fix 2); Phi-4-mini F3 tools never reached the prompt; F3 prompt missing task framing; missing `"answer"` key rule | Fixed before the Phase 1 runs |
| 10-05 | Backup function bug: zip staged inside `results_v2/` grew to 47 GB, run `phi3_mini/bfcl_multiple` failed instantly and was rerun | `analysis/plan/D_health_check.md` |
| 10-06 | F1 `qwen3/bfcl_multiple` run split into two halves | `DEVIATIONS.md`, `scripts/f1_split.log`, equivalence proof in `scripts/prove_split_equivalence.py` |
| 10-07 | Granite-3.0 F3 parser gap | Fixed; 3 runs redone into `F3_rerun/` |
| 10-08 | F4 full-schema constrained decoding cut; Qwen3 generic-JSON grammar also blocks thinking | `DEVIATIONS.md` |
| 10-08/09, 10-11 | Qwen3-only repetition loops under F4 and R | Reported at full scale; kept as results |
| 10-08 | F6: 1 greedy mismatch, pre-existing GPU nondeterminism | Reported |
| 10-13 | F11 differs from D in a second way: the legacy setup has no stop strings (0 of 16,200 outputs contain a stop string) | Not rerun; documented |
| 10-15 | Two analysis fixes before the one full run: `rescored/` contained Kaggle exploratory rescores (crash for 10/16 models) and three analysis-config entries lacked `models:` keys | Fixed; analysis run once |
| 10-15 | `n_unmatched` column in several output tables is inflated by ≥300 | **Not fixed**; stress diffs and labels are not affected |
| 10-19 (W0) | Phase 1 A/A design flaw: changing the run seed redrew stress prompts, so only about 19% of records on bfcl_multiple could be compared (`PLAN_PHASE2.md` W2; `PROMPT_SEED_REPORT.md`) | Phase 2 A/A keeps the run seed and changes only trial seeds |

### 4.2 Phase 2 operations
- The log has 407 "launching" lines and 355 "OK" lines (laptop queue). The difference is runs that were stopped (pauses by the user, PC shutdown/sleep) and then redone from zero; there are no FAILED lines. Several long runs were restarted more than once (launch lines in the log: `F3/qwen3/bfcl_multiple` 5, `R_AA2/qwen3/bfcl_multiple` 2). A few runs took 2–3× their manifest estimate, partly from restarts and sleep, so run hours above are inflated. The manifest hours estimate for `R_AA2/qwen25/synthetic` (12.8 h) is much larger than its actual 2.13 h.
- Backups: 26 backup lines in the progress log; the latest zip was written to the OneDrive backup folder.
- Plan edits before the lock (git log 2026-10-19): W3 synthetic extension dropped (generator cannot make new distinct prompts), cluster bootstrap added, Kaggle trials changed to "all fresh", checklist and open-items edits.

### 4.3 Big code changes over time (`git log`, 143 commits)
- 09-27 to 10-02: harness (`upgradecanary/`): tools, drift and fault perturbations, evaluator, llama.cpp client, BFCL suites, repeated trials, scoring and intent fixes, gate and canary analyses.
- 10-03 to 10-05: factor switches (F1–F6, F11), native chat wrapping, fault_reporting, BFCL-multiple, smoke tests, PLAN v1.
- 10-05 to 10-14: run orchestrators per protocol (`scripts/real_run_*`), controls, F11/R_F*, Kaggle runner and importer.
- 10-08 to 10-15: analysis pipeline `vdanalysis/`, rescoring scripts, one full analysis run.
- 10-19: Phase 2 analysis (`vdanalysis/phase2/`), run tooling (`scripts/phase2/`), manifests, W3 task files, plan lock.
- Tests: full suite run on 2026-11-07 for this report: **414 passed** (7 min 20 s, `python -m pytest -q`).

---

## 5. Weak spots I can see

**Design and statistics**
1. Only 30 decisions, and they are not independent: 3 suites per pair, shared families (Mistral ×3 models, Granite ×3, Phi ×3), and pairs share a model (e.g. phi35_mini appears in two pairs). The Phase 1 flip-rate and hypothesis tables (`flip_rates_by_factor.csv`, `hypotheses.csv`) carry no confidence intervals.
2. n=100 tasks per suite. The synthetic suite is close to ceiling on clean tasks (AUDIT.md: 96% ceiling on baseline) and has only 54 distinct baseline prompts among 100 tasks, so its effective sample is smaller than 100.
3. BFCL suites are schema-match only with a simulated executor; not comparable with BFCL leaderboard numbers. BFCL-multiple selection favors shorter multi-tool tasks (PLAN.md).
4. The gate thresholds (±0.05) are fixed by the plan, but `docs/results_summary.md` notes they were post hoc relative to the earlier exploratory phase. Many decisions sit near the threshold (e.g. phi3_mini→phi35_mini synthetic −0.053, mistral v01→v02 bfcl_simple −0.058), so labels there are fragile.
5. Phase 1 H5 fails on both parts (false alarms 5.6% against ≤5%; detection 54%, driven by the no-description control at 25%). The no-description control is largely invisible to a stress-only gate; Phase 2 adds a secondary full-score gate for this reason.
6. Phase 1 A/A control had few matched records (design flaw above) and only 18 decisions. Phase 2's A/A is bigger (48 decisions, plus D), but the three suites of one model are not independent.

**Scope**
7. Only open-weight models of 2B–8B at Q4_K_M (with Q8_0 and Q2_K variants for some), one inference stack (llama.cpp via llama-cpp-python), one laptop GPU plus Kaggle T4s. No closed models (W5 not run), no larger models.
8. Six model families; "held-out" status of Llama, Phi, Granite, Gemma depends on the plan being committed before they were run (PLAN.md section 2). The robust protocol R was designed from Mistral and Qwen only.
9. Human validation is thin: 40 labels from one labeler (kappa 0.60 against the rule). W6 (200 labels, two labelers) not done.

**Possible bugs and known quirks**
10. F5 was confounded with hardware in Phase 1 (Kaggle T4 vs laptop D); the Kaggle hardware check covers 6 runs, 1 of which changed a label. Phase 2's same-hardware runs are the fix and are not yet available (Kaggle 0/81).
11. F11 is not a one-field change (no stop strings); the `n_unmatched` column is wrong in several tables (not fixed); Qwen3 repetition loops under F4 and R.
12. GPU nondeterminism appears in places: 1 greedy mismatch in F6; the split test shows 2 differing raw outputs out of 300 (scores identical).
13. Phase 2 laptop timing: some runs ran far over their estimates (for example Qwen3 `R_AA2`, `R_PC_Q2K`), so the remaining-time estimate may be low. Restarts from zero cost compute but do not affect data.

**Missing comparisons / risks to the plan**
14. W3 (every eligible item) is conditional on the Kaggle runs finishing by 2026-11-20; at the current state (0/81 Kaggle runs imported) it is at risk. The plan says it will then be reported as not run.
15. The R split-equivalence check for W3 is missing (`R_result.json`).
16. PLAN_PHASE2.md section 8 checklist boxes were not ticked in the file after the lock (tag and OSF deposit are done per the git log and `osf_deposit/`; the boxes are only unticked text).

---

## 6. Repo map and how to re-run the main experiment

### 6.1 Where things are
| Path | What |
|---|---|
| `PLAN.md`, `PLAN_PHASE2.md` | Pre-registered plans (tags `plan-v1`, `plan-v2`) |
| `DEVIATIONS.md` | Every change after the plans, with dates |
| `docs/` | `protocol.md` (frozen early protocol), `experiment_log.md`, `experiment_report.md`, `results_summary.md`, `model_manifest.md`, `sampling_presets.md`, `controls.md`, `ENGINEERING_NOTES.md` |
| `upgradecanary/` | The harness: runner, tools, parsing, evaluator, perturbations, llama.cpp client |
| `configs/` | Early run configs (`real_*`, `bfcl_*`), `analysis_official_folders.yaml`, `analysis_phase1_regression.yaml`, `analysis_phase2.yaml`, `configs/phase2/*.json` (Phase 2 manifests) |
| `data/` | Task files (`base_tasks.jsonl`, `bfcl_*_tasks.jsonl`, provenance) and `data/phase2/` |
| `scripts/` | Phase 1 orchestrators (`real_run_*_orchestrator.py`, `real_run_one.py`), rescoring scripts, early analysis scripts, Kaggle import; `scripts/phase2/` Phase 2 tooling |
| `vdanalysis/`, `vdanalysis/phase2/` | Phase 1 analysis pipeline and the Phase 2 extension |
| `analysis/` | `audit/` (audit follow-ups), `plan/` (per-protocol reports, smoke test, health check), `phase2/` (README, regression result) |
| `kaggle/`, `kaggle/phase2/`, `kaggle_upload/` | Kaggle runner and notebooks (`kaggle_upload/` ignored) |
| `tests/` | 414 tests (pass) |
| `results/`, `results_smoke/`, `results_v2/`, `results_v3/` | Early runs, smoke tests, Phase 1 runs, Phase 2 runs (all git-ignored; backed up to OneDrive) |
| `analysis_out/`, `analysis_out_v3/`, `rescored/` | Phase 1 tables (ignored), Phase 2 regression output, rescored records |
| `osf_deposit/` | Copies of the plans and hashes prepared for OSF (ignored) |
| `tables/`, `figures/` | Early-phase tables and figures |

### 6.2 Re-running
Requirements: Python 3.12, `requirements.txt`, `llama-cpp-python` 0.3.35 with CUDA, the GGUF files from `docs/model_manifest.md` in `models/`.

```bash
# Phase 1 (one orchestrator per protocol; each is resumable, writes to results_v2/)
python scripts/real_run_orchestrator.py          # D, 48 runs
python scripts/real_run_f1_orchestrator.py       # F1; likewise real_run_f2/f3/f4_json/f5_small/f6/r/controls orchestrators and real_run_batch_rf6_rf3_f11_orchestrator.py
# rescoring-only factors
python scripts/rescore_f7_lenient_parsing.py
python scripts/rescore_f8_relaxed_intent.py
python scripts/rescore_f10_one_trial.py
python scripts/rescore_f9_ci_gate.py
# Phase 1 analysis
python -m vdanalysis.run_analysis --config configs/analysis_official_folders.yaml --out analysis_out

# Phase 2
python -m scripts.phase2.check_configs --phase1-root results_v2
python -m scripts.phase2.run_laptop --dry-run    # queue, hours, what is done
python -m scripts.phase2.run_laptop              # resumable; writes to results_v3/
python -m scripts.phase2.import_kaggle <folder> --apply   # after Kaggle batches
python -m vdanalysis.phase2.rescore_v3 --config configs/analysis_phase2.yaml --factor F7   # and F8
python -m vdanalysis.phase2.run_phase2 --config configs/analysis_phase2.yaml --out analysis_out_v3 --report analysis/phase2/analysis_report.md
python -m pytest -q                              # tests
```

Single early run: `python -m upgradecanary.runner --config configs/<name>.yaml`. Regression check of the Phase 2 code against Phase 1: `python -m vdanalysis.phase2.regression --config configs/analysis_phase1_regression.yaml --reference analysis_out --out analysis_out_v3/regression_phase1`.

Not checked for this report: the exact command-line arguments of the Phase 1 orchestrators (script names were listed from the `scripts/` folder; only `real_run_orchestrator.py`'s header was read), and whether the Phase 1 pipeline still reproduces `analysis_out/` today (the Phase 2 regression check did, with 0 differences, on 2026-10-19).
