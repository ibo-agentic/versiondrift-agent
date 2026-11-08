# Analysis addendum to PLAN_PHASE2 (plan-v2.1)

Status: DRAFT. Commit and tag (`plan-v2.1`) before any Phase 2 result file is opened, summarized or analysed.

Date written: 2026-11-07. At this date no Phase 2 result has been analysed. The only Phase 2 outputs that have been looked at are the run status files, the W0 determinism checks, the sanity check of the first three runs, and the Phase 1 regression output. The exploratory Phase 1 report (`analysis/exploratory/EXPLORATORY_phase1_report.md`) motivated this addendum.

## 0. Rules

1. P1–P7 in PLAN_PHASE2.md stay the confirmatory analyses. Nothing here changes their definitions, thresholds or the order in which they are reported.
2. Everything in this addendum is **secondary**. The paper labels it "pre-specified secondary (plan-v2.1)". Anything decided after Phase 2 results are seen is labelled "post hoc exploratory".
3. The code for every analysis below is written and tested in "Phase 1 mode" (on `results_v2/`) before it is run on Phase 2 data. The Phase 2 run happens once. Any later change goes into DEVIATIONS.md with a date and reason.
4. Uncertainty defaults (used in all sections unless stated otherwise): hierarchical bootstrap, resample upgrade pairs, then tasks within each pair-suite, keeping all trials and conditions of a task together. B = 10,000, seed 1234. Report 95% percentile intervals.
5. Multiple comparisons: Holm correction over the 7 generation-side factors (F1, F2, F3, F4, F5, F6, F11) for every per-factor test in S1.

## S1. Noise floor: factor flips vs rerun flips

Motivation: P1 counts flips under factors but has no rerun baseline. A decision near the ±0.05 threshold can flip from sampling noise alone.

Definitions (point gate, as in `vdanalysis/engine.py`):
- **Rerun flip** for decision i under protocol D: label from the D main arm (trial seeds 1234–1243) differs from the label from D_AA2 (trial seeds 5678–5687), both arms using run seed 1234, same prompts, same models.
- **Rerun flip rate** r_D = share of the 30 decisions with a rerun flip. Same for R with R_AA2 (r_R).
- **Factor flip rate** f_F = share of decisions for factor F whose label differs from D (as in P1), restricted to the decisions where F was run.
- **Excess flip rate** for each generation-side factor: e_F = f_F − r_D computed on the same decisions.

Tests and outputs:
1. r_D and r_R with Clopper–Pearson 95% intervals.
2. For each generation-side factor, e_F with a hierarchical bootstrap interval (both f_F and r_D recomputed in each replicate). One-sided test of e_F > 0, Holm-adjusted over the 7 generation factors.
3. Rescoring factors (F7, F8, F9) reuse the same generations, so their rerun baseline is 0; they are reported as is. F10 (greedy trial only) changes the estimator, not the generations; it is reported as is.
4. **"At least one flip" headline (P1 analogue with noise):** for each decision i, estimate a per-decision rerun flip probability p_i by bootstrap (resample tasks; recompute the D vs D_AA2 label comparison). Expected share of decisions with ≥1 noise flip = mean over i of 1 − (1 − p_i)^k_i, where k_i is the number of generation-side factors run for decision i. Report this next to the observed P1 value.
5. Sensitivity: all of S1 repeated excluding the qwen25→qwen3 pair (3 decisions), because under D its Qwen3 outputs are truncated by the 256-token budget.

## S2. Flip types

Each flip (factor or rerun) is classified as:
- **Sign reversal:** harmful ↔ beneficial.
- **Boundary crossing:** any flip that involves neutral.

Report counts of each type per factor and for the rerun baseline (S1), with the qwen25→qwen3 pair shown separately.

## S3. Four-class verdict (secondary gate)

δ = 0.05. Intervals from the task-clustered bootstrap within each decision (B = 10,000, seed 1234).
- **Harmful:** point < −δ and 95% upper bound < 0 (same as the pre-registered CI gate).
- **Beneficial:** mirror image.
- **Neutral (equivalent):** 90% interval entirely inside [−δ, +δ] (TOST at α = 0.05).
- **Inconclusive:** everything else.

Report the share of decisions in each class under D and R, and the S1/S2 analyses repeated with this gate.

## S4. Factor classification (fixed now, before results)

Each factor is classed as a **documented reasonable choice** or a **misconfiguration / compound change**. Headline flip rates in the paper use the reasonable set only. All factors are still reported in full.

| Factor | Class | Reason and source |
|---|---|---|
| F1 output budget 1024 | reasonable | Output budgets differ widely between tool-calling harnesses: NeMo Evaluator's BFCL example uses `max_new_tokens=512` (https://docs.nvidia.com/nemo/evaluator/latest/evaluation/run-evals/function-calling.html); EvalScope's BFCL-v3 example uses `max_tokens=32000` (https://evalscope.readthedocs.io/en/latest/third_party/bfcl_v3.html). 256 and 1024 both lie inside this range |
| F2 Qwen3 thinking off | reasonable | Official hard switch `enable_thinking=False` in the Qwen3 model card (https://huggingface.co/Qwen/Qwen3-8B). Reported as a case study only (n = 3 decisions) |
| F3 native tool template | reasonable | Qwen docs recommend Hermes-style tool calling for Qwen3 to maximise function-calling performance (https://qwen.readthedocs.io/zh-cn/stable/framework/function_call.html; English version under /en/). Other families: their chat templates' tool sections (model cards) |
| F4 generic-JSON constrained decoding | reasonable | Built into llama.cpp: JSON schema → GBNF grammar in llama-server and llama-cli (https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md) |
| F5 Q8_0 vs Q4_K_M | reasonable | Both standard GGUF presets. Mistral's GGUF guide marks q4_k_m "Recommended" and q8_0 as close to lossless (https://docs.mistral.ai/cookbooks/concept-deep-dive-quantization-methods-gguf); Qwen's llama.cpp guide names Q8_0, Q5_K_M and Q4_K_M as the common choices for 8B models (https://qwen.readthedocs.io/en/latest/quantization/llama.cpp.html) |
| F6 model-recommended sampling | reasonable | Taken from each model card, e.g. Qwen3-8B "Best Practices" sampling settings per mode (https://huggingface.co/Qwen/Qwen3-8B#best-practices). Per-model sources as in `docs/sampling_presets.md` |
| F7 lenient parsing | reasonable | Lenient JSON recovery (strip code fences, take the first `{`…last `}` span) is used in tool-calling evaluation, e.g. arXiv 2609.07370. Source to be checked before camera-ready |
| F8 relaxed intent | reasonable | BFCL's AST checker accepts a list of possible answers per argument instead of one exact value (BFCL, Patil et al., ICML 2025). Source to be checked before camera-ready |
| F9 CI gate | reasonable | Standard statistical gate |
| F10 greedy trial only | reasonable | Single runs at temperature 0 are the default in common BFCL harnesses, e.g. EvalScope's BFCL-v4 example sets `temperature: 0` (https://evalscope.readthedocs.io/en/latest/third_party/bfcl_v4.html) |
| F11 legacy chat wrapping | **misconfiguration / compound** | Changes two things at once (legacy wrapping and no stop strings; DEVIATIONS 2026-10-13). Excluded from headline rates |

## S5. Failure-type mechanism

Failure categories per record: unparsed/malformed, wrong tool name, wrong or invalid arguments, executor failure, fault-reporting wrong status (and fabricated answer).

Outputs:
1. Failure-type shares per model × protocol × suite.
2. For each flip, the change (new − old, factor − D) in each failure type that drives the change in stress diff. Descriptive only; no test.

## S6. Power and minimum detectable effect

Using the method in the Phase 1 exploratory report (normal approximation, task-level paired differences, trials averaged within task):
1. MDE at 80% power, α = 0.05, per suite, with Phase 2 trial counts.
2. Power at a true effect of exactly δ = 0.05.
3. If W3 runs, the same with W3 task counts.
Descriptive only. Stated in the paper as our own method, not part of the original plan.

## S7. McNemar gate (secondary gate)

Item = (task, stress condition). Each item is collapsed to one binary outcome per model: success if the mean strict score over trials ≥ 0.5. Exact two-sided McNemar test on the old vs new model per decision. Label: harmful/beneficial if p < 0.05 and the point stress diff is beyond ∓δ, else neutral. Report agreement with the pre-registered point gate and with S3.

## S8. Reference verdict check (small models)

For decisions where both models have local Q8_0 files (phi3_mini→phi35_mini, phi35_mini→phi4_mini, gemma2_2b→gemma3_4b; 9 decisions), use the F5 (Q8_0) label as a reference. Report how often each other protocol agrees with it. Descriptive only.

## S9. Hierarchical model (sensitivity check)

Per suite: logit P(success) ~ version × protocol + condition + (1 | task) + (1 | pair), on stress-condition records. The version × protocol interaction is read as "how much this protocol changes the upgrade effect". Reported as a sensitivity check next to the bootstrap results; family is not used as a random effect (only 6 families).

## Not part of this addendum

No changes to models, tasks, conditions, trial counts, run seeds, the GPU deadline (2026-12-10) or the W3 gate.
