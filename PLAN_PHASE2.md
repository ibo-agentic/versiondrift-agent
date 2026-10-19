# PLAN_PHASE2.md — Strengthening Runs (LOCKED)

**Status: LOCKED** at tag `plan-v2`, deposited on OSF together with PLAN.md (`plan-v1`).
**Everything here is fixed before any Phase 2 run whose result it describes.**

Decisions confirmed 19 Oct 2026 (after W0 Parts A and B and the Phase 2 code build):
trial scheme, laptop trial reuse, W3 sizes and conditional status, F5 same-hardware fix,
F6 trimming, A/A design, 10-trial positive controls, replicate definition, thresholds,
seeds, W4 option, W5 selection rule and budget, deadline.

---

## 0. Ground rules

- Phase 1 results (tag `analysis-complete`) are **frozen**. H1–H5 stand as reported.
  Nothing here re-tests, replaces, or "fixes" them.
- Phase 2 is a separate, separately pre-registered set of runs. The paper reports both
  phases side by side.
- Same 16 models, same 10 pairs, same GGUF files (SHA-256 in `docs/model_manifest.md`),
  same factor definitions, same strict scoring, same gate rules and thresholds as PLAN.md,
  same CI bootstrap seed (1234). Every exception is listed in §7.
- New results go to `results_v3/`, read-only once written.
- Phase 2 analysis code (`vdanalysis/phase2/`) is written and tested on fixture data
  **before** the lock, and frozen at tag `plan-v2`. It is not run on real Phase 2 records
  before the lock. Its regression check reproduces all Phase 1 tables exactly.
  Bug fixes after the lock go in DEVIATIONS.md with before/after numbers.

---

## 1. Why Phase 2 (one line per reviewer attack)

| Weakness | Answer |
|---|---|
| Only 3 trials (1 greedy + 2 sampled) | W1: 10 trials (1 greedy + 9 sampled) |
| A/A has only 18 decisions, few matched records; one outlier fails H5 | W2: A/A on 48 decisions, all records matched |
| Positive controls measured at 3 trials only | W2b: positive controls at 10 trials |
| F5 (headline factor) ran on Kaggle, D on laptop: quantization and hardware confounded | W1: same-hardware D and R baselines for F5 |
| n=100 per suite (UpgradeBench Table 11) | W3 (conditional): every eligible item |
| No-desc control invisible to stress-only gate | W4: full-score gate as a secondary |
| Only small open models | W5: closed-model pairs |
| 40 human labels, one labeler | W6: 200 labels, two labelers |

---

## 2. Trials and seeds

Facts established by W0:
- Stress prompts (drift, fault) are drawn from the **run seed** (`cfg["seed"]`), hashed with
  task id and condition. All trials of a run share the same prompt.
- Trial seeds affect **sampling only**.
- Within a protocol, the old and new model of a pair see byte-identical prompts (900/900,
  all 30 decisions).
- Laptop re-runs with the same config, seeds and GGUF are byte-identical (W0 Part B, 3 runs,
  900/900 records, every trial).
- At temperature 0 the greedy output does not depend on the trial seed (W0 Part A, 100%
  identical on identical prompts).

Phase 2 seeds:
- **Run seed:** 1234 for every Phase 2 run (main, A/A, positive controls).
- **Main trials:** trial seeds `[1234 … 1243]`, temperatures `[0.0, 0.7 × 9]`
  (1 greedy + 9 sampled). Extra greedy trials would be exact copies, so none are added.
- **A/A second arm:** run seed 1234, trial seeds `[5678 … 5687]`, same temperatures.
- **Synthetic task generator:** not used; synthetic is not extended in W3.
- **Human-label sampling (W6):** seed `20261020`.
- **CI bootstrap:** 1234, unchanged. **BFCL task selection:** 20260930, unchanged.

**Reuse of Phase 1 trials 1–3:**
- **Laptop** (W1 laptop runs, W2b): reused. Only trials 4–10 (trial seeds 1237–1243) are
  run, and merged with the Phase 1 records.
- **Kaggle:** all 10 trials run fresh. All Kaggle comparisons (F5 and R_F5 vs the Kaggle D/R baselines) use Phase 2 Kaggle runs only, so the Kaggle environment does not need to match Phase 1. W0 Part C, if run, is descriptive.
- **Split test (W0):** reused trials 1–3 plus separately run trials 4–10 matched a single 10-trial run in 100% of strict scores (99.33% raw output, 300 records, gemma2_2b synthetic, D). The only differences were in the first trial of the separate run, from KV-cache state. Merged runs are treated as equivalent.

**Estimand note:** a 10-trial score is 1/10 greedy, a 3-trial score is 1/3 greedy, so they
are not exactly the same quantity. The 10-trial score is primary; greedy-only and
sampled-only scores are reported as descriptive views so the phases can be compared like
for like.

---

## 3. Workstreams

### W0. Determinism check — done except Part C
Parts A and B done; split test done. Part C (one Kaggle F5 re-run) is optional and descriptive.

### W1. 10 trials — firm
- **Protocols:** D, R, F1, F2, F3, F4, F5, F6, each with the same model and suite scope as
  its Phase 1 folder.
- **F6 trimming:** for the 10 models whose F6 sampling equals D's (mistral_v01, mistral_v02,
  mistral_v03, phi3_mini, phi35_mini, phi4_mini, granite30, granite31, granite32,
  gemma2_2b), F6 is not re-run; the D records are used, since the laptop is deterministic.
  F6 runs only for qwen2, qwen25, qwen3, llama3, llama31, gemma3_4b. The main F6 result uses
  only sampling-changed pairs, as in Phase 1.
- **Scoring-only factors** (F7, F8, F10) are recomputed on the W1 records.
- **Scope: all 30 decisions, not only the 13 that flipped.** Re-running only the flips is
  biased: decisions picked for looking extreme tend to shrink on re-test, and new flips
  could never appear.
- **Hardware:** each run uses the hardware its Phase 1 folder used, plus the
  **F5 same-hardware fix:**
  - **D on Kaggle** for the 11 models whose F5 ran on Kaggle (granite30, granite31,
    granite32, llama3, llama31, mistral_v01, mistral_v02, mistral_v03, qwen2, qwen25, qwen3).
  - **R on Kaggle** for the 5 models whose R_F5 ran on Kaggle (granite30, granite31,
    granite32, llama3, llama31).
- Kaggle sessions run two jobs in parallel, one per T4.

### W2. Bigger A/A control — firm
- 16 models × 3 suites = **48 decisions**, under **R** and under **D**, laptop.
- **Arm 1** = the W1 laptop run. **Arm 2** = run seed 1234 (same prompts), trial seeds
  5678–5687, 10 fresh trials.
- **Why this differs from Phase 1:** Phase 1's A/A changed the run seed, which redrew the
  stress prompts; the analysis then compared only records whose drift and fault types
  matched (e.g. 19% of records on bfcl_multiple), and those matched records had identical
  prompts. So Phase 1's A/A measured sampling noise on a subset. Phase 2 measures the same
  thing on all records. By construction the greedy trial is identical across arms.
- Report false-alarm rate with an exact (Clopper–Pearson) 95% CI. Note that the 3 suites of
  one model are not independent.

### W2b. Positive controls at 10 trials — firm
- **Q2_K control** and **no-description control**, same model and suite scope as Phase 1's
  R_PC_Q2K and R_PC_NODESC folders, under R, laptop.
- Run seed 1234, trial seeds 1234–1243. Phase 1 trials 1–3 reused; trials 4–10 run.
- Compared against the W1 laptop R runs (same hardware, same prompts).
- Together with W2, this gives both error directions of the gate at 10 trials:
  false alarms (W2) and misses (W2b).

### W3. Every eligible item — conditional
- **Runs only if W1, W2 and W2b are fully complete by 20 Nov 2026.** If not, W3 is skipped
  and reported as not run. The condition depends on the calendar only, never on results.
- D and R only, 10 trials, all 10 pairs, laptop. No Kaggle baselines for W3.
- **synthetic:** not extended. The Phase 1 generator is deterministic with small value pools: the original 100 tasks hold only 54 distinct baseline prompts, and it cannot make new distinct prompts for 5 of its 6 tools. Extending it would change the task distribution.
- **bfcl_simple:** all 191 eligible items (original 100 + 91).
- **bfcl_multiple:** all 109 eligible items (original 100 + 9).
- Eligibility filters are **not** loosened.
- Added tasks run as separate runs and are merged with the W1 records for the original 100.
  Before W3 starts, the split-equivalence check (`scripts/prove_split_equivalence.py`) is
  repeated for R on the laptop.
- Report matched stress-record counts per suite.

### W4. No-description control fix — firm, no GPU
- **Option A:** a pre-registered *secondary* gate that scores the full suite
  (baseline + stress, three conditions weighted equally) with the same rule and thresholds.
  Primary gate unchanged.
- Applied to the W2b positive controls (P5) **and** to W2 A/A, so its false-alarm rate is
  known too. Applying it to Phase 1 control records is descriptive only.

### W5. Closed-model pairs
- **Selection rule (fixed now):** from 2 providers, the latest flagship model and its direct
  predecessor, both still served on the day W5 starts. Exact snapshot IDs and the date are
  recorded before the first W5 call. If a provider has no such pair, that is documented and
  W5 proceeds with what exists.
- Factors: D, R, F4 (if structured output exists), F6 (temperature), scoring-only factors.
  No F3, no F5.
- A/A on each pair.
- **Hard budget cap: $40.** Stop when reached.

### W6. Human labels
- 200 records, stratified by suite × rule verdict (pass/fail), sampling seed above.
- Two labelers, blind to the rule's output and to each other.
- Second labeler: **TBD, recruited before W6 starts** (CS background, not involved in the
  project). If none is found before the GPU deadline, W6 runs with one labeler and
  human–human kappa is reported as not available.
- Report human–human kappa, and each human vs the rule.

---

## 4. Phase 2 hypotheses

| ID | Hypothesis | Threshold |
|---|---|---|
| P1 | At 10 trials, the share of the 30 decisions that flip under ≥1 factor is at least… | **20%** |
| P2 | Of Phase 1's 13 flipped decisions, the number that replicate at 10 trials (§5) is at least… | **7 of 13** |
| P3 | R-gate A/A false-alarm rate (W2, 48 decisions, 10 trials) is at most… | **5%** |
| P4 | Q2_K positive control (W2b) detected under R at 10 trials in at least… | **90%** |
| P5 | On the W2b no-description control, the full-score gate detects more decisions than the stress-only gate | yes / no |
| P6 | F5 (Q4_K_M → Q8_0), same-hardware comparison, replicates (§5) for at least… of the 8 decisions it flipped in Phase 1 | **4 of 8** |

**P7 (descriptive, only if W3 runs):** for D and for R, the share of the 20 BFCL decisions (10 per suite) whose
verdict on the original 100 tasks differs from the verdict on the full task set, per suite.

**Descriptive (no threshold):**
- D-gate A/A false-alarm rate (W2 under D)
- Hardware noise: D-laptop vs D-Kaggle, 11 models
- Size of F5's per-model score shift, same-hardware, vs the A/A noise bound. **Headline
  bound: 95th percentile of |stress diff| over the W2 D A/A decisions**; the maximum is also
  reported.
- Greedy-only and sampled-only views of all main results
- New flips not seen in Phase 1
- Secondary-gate false-alarm rate on A/A
- P2 and P6 under the other replicate readings (all factors; same sign instead of same
  label change)
- Secondary gate on Phase 1 control records
- Synthetic duplicate prompts: all synthetic decisions also reported with a cluster bootstrap where tasks sharing the same baseline prompt form one cluster. Descriptive only; the gate is unchanged.
- W5 results, W6 agreement numbers

---

## 5. Definitions

- **Replicate (P2):** a Phase 1 flipped decision replicates if, at 10 trials, it flips under
  **at least one** of the factors that flipped it in Phase 1, with the **same label change**:
  its D label equals its Phase 1 D label, and its label under that factor equals the Phase 1
  label under that factor.
- **Replicate (P6):** the same rule, under F5 only, with the same-hardware D label as the
  starting label.
- **Same-hardware rule:** every factor effect is computed against a baseline run on the
  same hardware as the factor run. For F5 and R_F5 on Kaggle models, that is the Kaggle
  D / R baseline from W1. This applies to P1, P2 and P6.
- Anything not listed in §4 is **exploratory** and labeled so in the paper.

---

## 6. Order, compute, stopping

| Step | Work | Laptop h | Kaggle single-GPU h |
|---|---|---|---|
| 1 | W0 Part C (optional, descriptive) | 0 | ~0.3 |
| 2 | Phase 2 analysis code + run configs, tested on fixtures | 0 | 0 |
| 3 | Lock plan (`plan-v2`) + OSF deposit | 0 | 0 |
| 4 | W1 | 195.6 | 136.8 (less if Kaggle reuse allowed) |
| 5 | W2 (R) | 70.2 | 0 |
| 6 | W2b | 18.2 | 0 |
| 7 | W2 (D) | 38.4 | 0 |
| 8 | W4 rescoring | 0 | 0 |
| 9 | W3 (only if W1, W2, W2b done by 20 Nov; bfcl only) | 34.5 | 0 |
| any time | W5, W6 | 0 | 0 |

Firm total: **322.4 laptop h**, **136.8 Kaggle single-GPU h** (~68 session h on
2 GPUs). Estimates assume run time scales with trial and task count.

- Priority if compute or time runs short: **W1 > W2 (R) > W2b > W2 (D) > W4 > W5 > W6 > W3**.
- All GPU runs finish by **10 Dec 2026**. Anything unfinished is dropped and reported as
  not done. The deadline is not extended to wait for a result.

---

## 7. Differences from Phase 1

- Trials 3 → 10; trial mix 1 greedy + 2 sampled → 1 greedy + 9 sampled.
- A/A: 18 → 48 decisions; arm 2 keeps the run seed (same prompts) and changes only trial
  seeds, so all records are compared (reason in W2). Also run under D.
- Positive controls at 10 trials.
- Same-hardware baselines for F5 and R_F5 (Phase 1 compared Kaggle F5 against laptop D/R).
- F6 not re-run where its sampling equals D's; D records used instead.
- Tasks (conditional): bfcl_simple 100 → 191, bfcl_multiple 100 → 109; D and R only. Synthetic not extended.
- Secondary full-score gate.
- Closed-model pairs (new).
- Human labels 40 → 200, two labelers.

---

## 8. Checklist before deposit

- [x] Kaggle reuse decided (all fresh)
- [ ] Phase 2 analysis code and run configs match this version, tests passing
- [ ] Committed and tagged `plan-v2`
- [ ] Deposited on OSF with PLAN.md and both commit hashes
- [ ] DEVIATIONS.md has one line pointing to this file

---

## 9. Open items before the lock

None.
