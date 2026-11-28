**EXPLORATORY add-on, not pre-registered.** Analysis of the granite32 thinking-ON arm by the decision rule fixed in `EXPLORATORY_PLAN_granite_thinking.md` (tag plan-granite-thinking). Existing data plus this arm only; read-only script `scripts/exploratory/granite_thinking_analyze.py`.

# granite32 with thinking ON: arm think256, trials 0, 1, 2

Run: 3 suites x 100 tasks x 2 stress conditions x 3 trials = 1800 outputs (granite32, thinking ON via the chat template's `thinking` variable, 256 tokens, strict thinking policy). Seeds and temperatures as the D main run's trials 0-2.

## Criterion (a): cut-off share, and the secondary unparsed share

| Suite | Outputs | Cut-off (limit hit, or thinking without a response) | of which hit the token limit | Unparsed (secondary) |
|---|---|---|---|---|
| synthetic | 600 | **0.0%** (0) | 0.0% | 6.0% (36) |
| bfcl_simple | 600 | **1.0%** (6) | 1.0% | 3.2% (19) |
| bfcl_multiple | 600 | **0.3%** (2) | 0.3% | 2.3% (14) |
| all | 1800 | **0.4%** (8) | 0.4% | 3.8% (69) |

Thinking visibly on: 1780 of 1800 outputs contain "Here is my thought process:"; 1779 contain "Here is my response:".

**Output length (tokens, re-tokenized with the model's own tokenizer):** median 96, 90th percentile 140, max 256 (budget 256).

## Verdict granite31 -> granite32 (stress conditions, the study's gates)

Compared on the trials both runs share (trials 0-2, n = matched records). 'Thinking-off, existing' is the main study's 10-trial D decision; 'thinking-off, same trials' restricts that run to the same trials as the thinking-ON arm.

| Suite | granite32 | n | Stress diff | 95% CI | Point gate (D) | CI gate | Four-class |
|---|---|---|---|---|---|---|---|
| synthetic | thinking ON (strict rule) | 600 | -0.028 | [-0.060, +0.002] | neutral | neutral | inconclusive |
| synthetic | thinking ON (main study's rule) | 600 | -0.028 | [-0.060, +0.002] | neutral | neutral | inconclusive |
| synthetic | thinking off, same trials | 600 | +0.022 | [+0.000, +0.045] | neutral | neutral | neutral |
| synthetic | thinking off, existing (10 trials) | - | +0.025 | [+0.010, +0.041] | neutral | neutral | neutral |
| bfcl_simple | thinking ON (strict rule) | 600 | -0.035 | [-0.073, +0.002] | neutral | neutral | inconclusive |
| bfcl_simple | thinking ON (main study's rule) | 600 | -0.035 | [-0.073, +0.002] | neutral | neutral | inconclusive |
| bfcl_simple | thinking off, same trials | 600 | +0.013 | [-0.008, +0.037] | neutral | neutral | neutral |
| bfcl_simple | thinking off, existing (10 trials) | - | +0.014 | [-0.004, +0.032] | neutral | neutral | neutral |
| bfcl_multiple | thinking ON (strict rule) | 600 | -0.013 | [-0.057, +0.030] | neutral | neutral | neutral |
| bfcl_multiple | thinking ON (main study's rule) | 600 | -0.013 | [-0.057, +0.030] | neutral | neutral | neutral |
| bfcl_multiple | thinking off, same trials | 600 | +0.028 | [+0.005, +0.055] | neutral | neutral | neutral |
| bfcl_multiple | thinking off, existing (10 trials) | - | +0.029 | [+0.015, +0.045] | neutral | neutral | neutral |

## Decision rule (from the plan)

- **(a) cut-off share above 10% at 256:** 0.4% (8 of 1800) -> **fails**.
- **(b) verdict moves toward harmful** (mean stress diff over the 3 suites drops by at least 0.05 vs the existing thinking-off decision, and the D point label moves at least one step toward harmful in at least one suite): mean change -0.048; suites moving toward harmful: none -> **fails** (descriptive only, from 3 trials, since (a) fails).
- **(c)** needs the 1024 arm; not run, because (a) fails.

**Branch that applies next:** **stop.** (a) fails, so by the plan the answer is *not the same hazard*: with thinking ON, granite32's thinking fits the 256-token budget. The 1024 arm and the extension to 10 trials are not needed; this is reported as a null result for the hazard question.

Secondary unparsed share 3.8% (69 of 1800) is reported, not used for the decision.

## qwen3 under the strict rule (stored D outputs, rescored; no rerun)

The plan (section 4) rescores qwen3's existing D numbers under the strict rule so that both thinking models are compared under the same rule. Both sides of qwen25 -> qwen3 (D main run, 10 trials, stress conditions, results_v2 trials 0-2 + results_v3 trials 3-9) are rescored from the stored raw outputs with the main study's rule and with `thinking_policy="strict"`; the study's gates as above. Checks: 12000 stress records rescored; the main-rule rescore differs from the stored score in 0. The strict rule parses 86 qwen3 records differently (the plan's figure), of which 83 change parse status or score (the rest parse to a different call or report that scores the same); qwen25: 0 parsed differently.

Cut-off = hit the 256-token limit, or `<think>` without `</think>`. Unparsed = the scorer's parse_ok is false.

| Suite | Outputs | Cut-off | Unparsed, main rule | Unparsed, strict rule |
|---|---|---|---|---|
| synthetic | 2000 | 19.5% (390) | 18.2% (365) | 19.4% (389) |
| bfcl_simple | 2000 | 45.9% (918) | 44.4% (887) | 45.9% (918) |
| bfcl_multiple | 2000 | 56.5% (1131) | 55.0% (1099) | 56.4% (1127) |
| all | 6000 | 40.6% (2439) | 39.2% (2351) | 40.6% (2434) |

| Suite | Rule | Stress diff | 95% CI | Point gate (D) | CI gate | Four-class |
|---|---|---|---|---|---|---|
| synthetic | existing D decision (analysis_out_v3_p7) | -0.113 | [-0.165, -0.060] | harmful | harmful | harmful |
| synthetic | main study's rule (rescored) | -0.112 | [-0.165, -0.060] | harmful | harmful | harmful |
| synthetic | strict rule | -0.124 | [-0.178, -0.070] | harmful | harmful | harmful |
| bfcl_simple | existing D decision (analysis_out_v3_p7) | -0.353 | [-0.417, -0.288] | harmful | harmful | harmful |
| bfcl_simple | main study's rule (rescored) | -0.354 | [-0.417, -0.288] | harmful | harmful | harmful |
| bfcl_simple | strict rule | -0.368 | [-0.433, -0.302] | harmful | harmful | harmful |
| bfcl_multiple | existing D decision (analysis_out_v3_p7) | -0.480 | [-0.540, -0.417] | harmful | harmful | harmful |
| bfcl_multiple | main study's rule (rescored) | -0.480 | [-0.540, -0.417] | harmful | harmful | harmful |
| bfcl_multiple | strict rule | -0.491 | [-0.552, -0.428] | harmful | harmful | harmful |

## qwen3 vs granite32, both with thinking ON at 256 tokens

Token counts re-tokenized with each model's own tokenizer (GGUF vocab). qwen3 thinks by default; granite32 with the template's `thinking` variable switched on.

| Model | Trials | Outputs | Cut-off share | Median tokens | 90th percentile | Max |
|---|---|---|---|---|---|---|
| qwen3 (D main run) | 0-9 | 6000 | 40.6% (2439) | 212 | 256 | 256 |
| qwen3 (D main run) | 0-2 | 1800 | 40.0% (720) | 211 | 256 | 256 |
| granite32 thinking ON (think256) | 0-2 | 1800 | 0.4% (8) | 96 | 140 | 256 |

**Context for the 256 budget:** lm-evaluation-harness 0.4.13 uses `max_gen_toks` = 256 by default (HF, vLLM and API backends) when a task does not set its own (checked in the 0.4.13 wheel: `models/huggingface.py`, `models/vllm_causallms.py`, `models/api_models.py`).

