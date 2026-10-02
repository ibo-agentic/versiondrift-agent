# PLAN — Upgrade-Verdict Stability Study (pre-registration, DRAFT v0.1)

Working title: *Same Upgrade, Different Verdict: How Evaluation Setup Choices Flip Model-Upgrade Decisions for Tool Agents*

Status: DRAFT. Becomes binding when committed. Any change after commit goes in `DEVIATIONS.md` with date and reason.

---

## 1. Questions

- **RQ1.** How often do reasonable evaluation-setup choices change the verdict (harmful / neutral / beneficial) for the same model upgrade? Which choices matter most?
- **RQ2.** Why do verdicts change — format failures or real semantic mistakes?
- **RQ3.** Does a robust protocol (fixed in this file, before new runs) give more stable verdicts on model families never used to design it?

We do **not** claim any verdict is the "true" one. We measure disagreement between reasonable setups.

---

## 2. Models and upgrade pairs

One quantizer source per family. Q4_K_M unless a factor says otherwise.

| Family | Versions | Adjacent pairs | Split | Note |
|---|---|---|---|---|
| Mistral 7B | v0.1, v0.2, v0.3 | 2 | **Design** | already run |
| Qwen | Qwen2-7B, Qwen2.5-7B, Qwen3-8B | 2 | **Design** | Qwen2.5→3 is size-changing |
| Llama | 3-8B, 3.1-8B | 1 | **Held-out** | verify 3.1 native template by local render |
| Phi mini | 3-mini, 3.5-mini, 4-mini | 2 | **Held-out** | |
| Granite 8B | 3.0, 3.1, 3.2 | 2 | **Held-out** | all have native tool templates |
| Gemma | 2-2b, 3-4b | 1 | **Held-out** | size-changing; Gemma-2-9b only if smoke test fits 8 GB |

Total: 16 models, 10 adjacent pairs (4 design, 6 held-out). Size-changing pairs are tagged and also reported separately.

**Held-out rule:** no held-out family is run, inspected, or used for any decision before this plan is committed. The robust protocol (Section 7) is fixed now, from the Mistral/Qwen audit only.

---

## 3. Task suites and conditions

| Suite | Size | Note |
|---|---|---|
| Synthetic-100 | 100 | Kept as-is. Clean baseline is near ceiling; reported as the "saturated clean suite" case. |
| BFCL-simple-100 | 100 | As before (deterministic selection, fixed seed). |
| BFCL-multiple-100 (new) | 100 | Model must pick the right tool among several. Schema drift applies **only to the gold tool's schema**; distractor tools unchanged. |

Conditions per task: `baseline`, `schema_drift` (field rename, field drop, type mutation, unexpected field; enum drift on synthetic only), and **`fault_reporting` (redesigned)**.

**fault_reporting:** after an injected tool result (timeout, exception, empty, partial), the model must reply in JSON:
`{"status": "ok" | "failed" | "incomplete", "answer": <string or null>}`
Success = correct `status` AND no fabricated answer when status should be `failed`. `stale_result` is dropped (cannot be detected from the output, so it cannot fail).

All 16 models, including Mistral and Qwen, are run fresh under D: the new suite, the new fault condition, and template-based wrapping make old runs non-comparable. Old runs stay as historical audit evidence only.

The old `runtime_fault` condition is not rerun. It is reported in the paper only as historical "retry after tool failure".

Trials: 1 greedy + 2 sampled per task-condition (same as before).

---

## 4. Default protocol (D) — a typical setup

| Setting | D value |
|---|---|
| Chat wrapping | each model's own chat template, read from the GGUF metadata (plain turns only, no tool template) |
| Prompt format | shared JSON-in-prompt: tool docs written in the prompt text (current harness) |
| Max output tokens | 256 |
| Thinking (Qwen3 only) | model default (on) |
| Parsing | strict JSON |
| Constrained decoding | off |
| Precision | Q4_K_M |
| Sampling (sampled trials) | current shared settings |
| Intent rule | current strict rule |
| Gate | point threshold: harmful if diff < −0.05, beneficial if diff > +0.05, else neutral |

Stress diff = mean paired success difference (new − old) over the stress conditions, as in the existing pipeline.

---

## 5. Setup factors (changed one at a time from D)

| # | Factor | Levels | New runs? |
|---|---|---|---|
| F1 | Output budget | 256 / 1024 | Yes |
| F2 | Thinking (Qwen3 only) | on / off | Yes (already have nothink, think_long) |
| F3 | Prompt format | shared JSON / best available per model (native tool template if it exists, else shared) | Yes |
| F4 | Constrained decoding | off / generic JSON (`{"name": string, "arguments": object}`) / full tool schema | Yes |
| F5 | Precision | Q4_K_M / Q8_0 | Yes. 8B models on Kaggle (16 GB GPU); small models locally |
| F6 | Sampling | shared / each model's recommended | Yes |
| F7 | Parsing | strict / lenient (escape repair) | No — rescore |
| F8 | Intent rule | strict / relaxed (5 causes) | No — rescore |
| F9 | Gate rule | point threshold / CI gate (Section 8) | No — rescore |
| F10 | Trials | 1 (greedy only) / 3 | No — subsample |
| F11 | Chat wrapping | legacy (old hand-built template string) / native (GGUF's own chat template) | Yes — Mistral and Qwen models only |

**F4 note:** a full-schema grammar built from the drifted schema forces the drifted field names and types, so the model no longer has to adapt to drift by itself. That level changes what `schema_drift` measures. It is kept because real deployments use strict structured output, but it is analyzed separately and is not part of the nuisance set or of R.

F5 may be limited to a subset of pairs if Kaggle time runs short. Any such cut is logged in `DEVIATIONS.md` before analysis.

---

## 6. Controls

- **A/A null pairs:** a model compared against itself (rerun with a different sampling seed). Run for at least 6 models (3 design, 3 held-out) × 3 suites. Correct verdict is always neutral; measures false-alarm rate.
- **Positive controls:** a model compared against a deliberately damaged copy of itself: (a) Q2_K quantization, (b) prompt with tool descriptions removed. At least 4 models. Correct verdict is harmful; measures detection rate.

---

## 7. Robust protocol (R) — fixed now

1. Output budget 1024, with a truncation check. Any run with more than 2% truncated records is flagged and rerun with a larger budget.
2. Generic-JSON constrained decoding for the decision score (structure only, never the specific tool schema). Raw format-failure rate is still measured in a separate unconstrained run and reported as a deployment-risk flag, never mixed into the decision.
3. Failures always reported in two buckets: format vs semantic.
4. Fault tests use `fault_reporting` (can actually fail).
5. CI gate (Section 8).
6. Clean-suite ceiling check: if both versions score ≥ 0.97 on baseline, the clean comparison is marked uninformative.

---

## 8. Metrics and gate

- **CI gate:** task-level cluster bootstrap, 10,000 reps, seed 1234. Harmful if point diff < −0.05 AND upper 95% bound < 0. Beneficial if point diff > +0.05 AND lower 95% bound > 0. Otherwise neutral/inspect.
- **Flip rate:** share of (pair × suite) decisions whose label differs from D's label under a factor level.
- **Disagreement rate:** share of (pair × suite) decisions where not all levels of a factor set give the same label.
- **Also:** sign flips, range of the effect size across levels, A/A false-alarm rate, positive-control detection rate.
- Unit of analysis for decisions: adjacent pair × suite (10 × 3 = 30 decisions).

---

## 9. Hypotheses (with pass/fail rule)

- **H1.** Under D, at least 20% of the 30 decisions change label under at least one factor level (F1–F10).
- **H2.** Format-related factors (F1, F2, F4, F7) have a higher combined flip rate than the other factors (F3, F5, F6, F8).
- **H3.** Decisions that flip have a smaller |stress diff| under D than decisions that never flip (compare medians).
- **H4.** On held-out pairs, R's verdicts disagree less across the nuisance set {F3, F5, F6} than D's verdicts do.
- **H5.** Under R: A/A false-alarm rate ≤ 5%, and positive-control detection rate ≥ 90%.

Each hypothesis is reported as supported / not supported, with numbers, whichever way it comes out.

---

## 10. Order of work

1. **Engineering** (no model runs): config switches for F1–F6; BFCL-multiple loader; `fault_reporting` condition; A/A and positive-control configs; all analysis scripts idempotent; tests pass.
2. **Smoke tests:** every model, 5 tasks, check template render, JSON parse, truncation flag. Confirm each GGUF actually contains `tokenizer.chat_template` (needed for D's wrapping and for F3). Verify Llama-3.1, Phi-4-mini, and Granite native tool templates render with a tool list. Check Gemma-2-9b memory fit. **Over-generation check:** flag any output that contains a role marker or end-of-turn text (e.g. `<|start_header_id|>`, `<|im_start|>`, `<|eot_id|>`, `<end_of_turn>`, `<|end|>`, `<|assistant|>`) — this would mean generation ran past the intended turn despite the stop list.
3. **Commit this PLAN.md** (binding from here).
4. **Runs:** D on all models first, then factors, then controls, then R.
5. **Analysis** exactly as Sections 8–9. Extra analyses allowed but labeled "exploratory".
6. Back up `results/` after every batch of runs.

---

## 11. Compute budget (estimate)

About 16 models × 3 suites × ~5 run-configs ≈ 240 runs, plus controls ≈ 30 runs. At ~5–30 min per run depending on model size: roughly 80–110 GPU hours. Q8 runs for 8B models on Kaggle.
