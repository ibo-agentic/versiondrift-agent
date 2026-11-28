# EXPLORATORY PLAN: does the "thinking gets cut off" hazard also hit Granite 3.2 with thinking ON?

**Exploratory add-on, NOT pre-registered.** Written 2026-11-28, before any real run of granite32 with thinking ON (the 5-task pilot
in section 7 is run after this plan was written and is not used for any conclusion). Main-study code state: tag pre-analysis-v2.3
(commit 73a9017) plus the opt-in changes listed in section 6. Outputs go to `results_exploratory/granite_thinking/`, never to
`results/`, `results_v2/` or `results_v3/`.

## 1. Question

In the main study, qwen25 -> qwen3 looks strongly harmful under the default protocol D because Qwen3 thinks by default and its
thinking often uses up the 256-token budget before any answer is written (EXPLORATORY_qwen3_dose.md, EXPLORATORY_flip_examples_full.md).
Does the same happen to another thinking-capable model? Granite 3.2 8B Instruct has an optional thinking mode; in the main study it
was never switched on (no granite32 output contains thinking). The existing pair granite31 -> granite32 is neutral on all three suites.

## 2. Model and thinking switch

- **Model:** the same file as the main study: `models/granite/ibm-granite_granite-3.2-8b-instruct-Q4_K_M.gguf` (bartowski build,
  Q4_K_M, 4,942,859,808 bytes, SHA-256 `bd041eb5...df09c2` per docs/deleted_models_2026-11-13.md; restored with scripts/restore_models.py).
- **Thinking switch:** set through the GGUF's own embedded chat template, rendered by our native wrapper (`chat_wrapping: native`),
  with the template variable the template itself reads. The exact variable and the text it adds are recorded in section 7 from the
  GGUF metadata (not assumed). Configured with the new opt-in key `model.chat_template_kwargs` (section 6).
- **Thinking output format:** recorded in section 7 from the template and the pilot outputs.

## 3. Arms

| Arm | Model | Thinking | Token budget (max_tokens) | Trials |
|---|---|---|---|---|
| G-think-256 | granite32 | ON | 256 (the D default) | 10 |
| G-think-1024 | granite32 | ON | 1024 (the Qwen3 F1 dose check) | 10 |
| reference (existing, no new run) | granite31 | off (no thinking mode) | 256 | 10 (D main run) |
| reference (existing, no new run) | granite32 | off (default, never switched on) | 256 | 10 (D main run) |

Everything else is exactly the D main run of granite32: the same 100 tasks per suite (synthetic, bfcl_simple, bfcl_multiple), the
same stress conditions (schema_drift, fault_reporting; the baseline condition is not run because the verdict uses stress conditions
only), the same prompts (shared prompt format, no constrained decoding), the same run seed (1234), trial seeds 1234-1243 and
temperatures (trial 0 greedy at 0.0, trials 1-9 at 0.7, the same top_p/top_k/min_p), n_ctx 4096, the same native chat template.
The only changes are the thinking switch and, in one arm, max_tokens. 10 trials matches the main study; if time does not allow, the
fallback in section 8 is used and the reduced trial count is stated in the report.

## 4. Analysis (same code and gates as the main study)

- **Decision:** granite31 (existing D main run, 10 trials) -> granite32 with thinking ON, per suite, using the study's own
  `vdanalysis.stats.compare()` on the stress conditions: stress diff, point gate +/-0.05 (D's gate), CI gate (task-cluster bootstrap,
  10,000 reps, seed 1234) and the four-class S3 verdict. Compared with the existing thinking-off decision granite31 -> granite32.
- **Scoring rule:** primary = the opt-in `parsing.thinking_policy: strict` (completed thinking removed before scoring, cut-off thinking
  = unparsed). Sensitivity = the main study's rule (no stripping; the first valid JSON anywhere in the output is scored), recomputed from
  the stored raw outputs.
- **Note on the main study's parser:** it takes the first valid JSON anywhere in the output, including inside thinking (no D or R config
  strips thinking). For qwen3 under D (6,000 stress records, 10 trials), the strict policy parses **86 records (1.4%)** differently:
  51 with completed thinking (the main rule had taken a JSON written inside the thinking) and 35 with cut-off thinking (the main rule had
  parsed a JSON written before the cut). Of qwen3's 2,439 D outputs that hit the token limit, 88 were still parsed under the main rule.
  qwen3's existing D numbers will therefore also be rescored under the strict rule from stored raw outputs (no rerun), so that both
  models are compared under the same rule.
- **Cut-off share (decision measure for (a) and (c)):** share of stress outputs that hit the token limit (the stored `truncated` flag)
  **or** contain thinking without a completed response marker ("Here is my response:" for Granite, "</think>" for Qwen3), per suite and
  overall.
- **Unparsed share (secondary, reported but not used for any decision):** share of stress outputs the scorer could not parse
  (`parse_ok` false), for any reason, including reasons that have nothing to do with thinking (such as a number given as `answer`).

## 5. What counts as "the same hazard" (fixed now, before any result)

The same hazard as Qwen3 is found only if **all three** hold:

- **(a) Cut-off output:** at the 256 budget, the cut-off share of granite32-thinking (all three suites together; section 4) is
  **above 10%**.
- **(b) The verdict moves toward harmful:** at the 256 budget, compared with the existing thinking-off granite32 decision,
  the mean stress diff over the three suites **drops by at least 0.05** AND the D point-gate label moves **at least one step toward
  harmful** (beneficial -> neutral or neutral -> harmful) in **at least one suite**.
- **(c) It is a budget effect:** at the 1024 budget, the cut-off share **falls to at most half** of its 256 value **and below 10%**.

**Not the same hazard** (each reported as such):
- (a) fails: thinking ON fits the 256 budget (cut-off share at most 10%). The hazard is specific to how much a model thinks.
- (a) holds but (b) fails: outputs are cut off but the upgrade verdict does not move toward harmful (the breakage is too rare or too even).
- (a) and (b) hold but (c) fails: the harm is not removed by a larger budget, so it is not the budget effect seen for Qwen3.

**Change to (a) and (c), 2026-11-28, made after the 30-item greedy pilot and before any real run:** (a) and (c) first used the share of
all unparsed outputs. The pilot showed that unparsed outputs also include failures unrelated to thinking (2 of 30: a number given as
`answer`, which the scorer rejects), so that measure could signal the hazard without any cut-off. (a) and (c) now use the cut-off share
defined in section 4; the share of all unparsed outputs is still reported as a secondary number but is not used for the decision. The
pilot had no cut-off output (0 of 30), so the change was not chosen to produce a particular result; the thresholds (10%, at most half)
and the 3-trial-first sequence in section 8 are unchanged.

## 6. Code changes (opt-in; defaults change nothing)

- `upgradecanary/parsing.py`: `apply_thinking_policy()` and a `thinking_policy` argument (default None = unchanged) on the tool-call
  and fault-report extractors. "strict" handles Qwen3 `<think>...</think>` and Granite's "Here is my thought process:" / "Here is my
  response:" sections.
- `upgradecanary/runner.py`: reads `parsing.thinking_policy` (absent = None = unchanged; unknown values refused).
- `upgradecanary/model/llama_cpp_client.py`: `model.chat_template_kwargs` (absent = {} = unchanged rendering and unchanged run
  manifest) passed to the GGUF's Jinja template; helper `native_render_kwargs()`.
- Tests: `tests/test_thinking_policy.py`. No existing config sets the new keys, so no existing result can change.

## 7. Pilot (run 2026-11-28 after this plan was written; checks only, not used for any conclusion)

**Thinking switch, verified from the GGUF.** The embedded `tokenizer.chat_template` of the main study's file reads a template variable
`thinking`. When it is true and no system message, tools or documents are given (our D setup: shared prompt format, no tools passed), the
template appends to the default system message: *"You can write down your thoughts and reasoning process before responding ... Write your
thoughts after 'Here is my thought process:' and write your response after 'Here is my response:' for each user query."* It is a
system-prompt instruction, not special tokens. In the main study `thinking` was never set, so the template used its plain system message
("You are a helpful AI assistant."). Our existing `model.thinking: on` setting would **not** switch Granite on (it sets Qwen3's
`enable_thinking`, which this template ignores); hence `model.chat_template_kwargs: {thinking: true}`. The run manifests record it.

**Pilot run:** granite32, thinking ON, first 5 tasks per suite, both stress conditions, 1 trial (greedy, seed 1234), 256 tokens:
30 generations, 2 min 10 s in total on the laptop (three model loads included). Output: `results_exploratory/granite_thinking/pilot/`.

| Check | Result |
|---|---|
| Thinking visibly on | 30 of 30 outputs start with "Here is my thought process:" and contain "Here is my response:" |
| Output length (tokens, re-tokenized with the model's own tokenizer) | min 69, median 94, mean 102, max 171 |
| Hit the 256-token limit | 0 of 30 |
| Parsed (strict thinking policy) | 28 of 30; the same 28 under the main study's rule |
| The 2 unparsed | both fault_reporting replies with a number as `answer` (`"answer": 30`, `"answer": 105`); the study's scorer requires text or null. Not a thinking problem |
| Scores | synthetic 10/10; bfcl_simple 7/10; bfcl_multiple 8/10 (5 tasks x 2 conditions each) |

For comparison, the existing thinking-off granite32 D run has 0.3% to 3.1% unparsed-or-limit outputs per suite.

**Settled 2026-11-28 (before any real run):** criterion (a) now measures cut-off outputs only (section 4 and the dated change in section 5);
the share of all unparsed outputs is reported as a secondary number. In this pilot the cut-off share is 0 of 30 and the unparsed share 2 of 30.

## 8. Time and the cheapest version

Measured pilot speed: about 3.5 s per generation (mean 102 tokens, including prompt processing). Each full arm is 3 suites x 100 tasks x
2 stress conditions x 10 trials = 6,000 generations. Sampled trials (temperature 0.7) may think longer than the greedy pilot did, so a
range is given; the upper bound assumes every output runs to the budget.

| Arm | Laptop (RTX 4060 8 GB) | One Kaggle session (2 x T4, about 1.6x slower per GPU than the laptop, measured on D and D_KAGGLE granite32/qwen3) |
|---|---|---|
| think256, 10 trials | about 6 h (if outputs stay near 100 tokens); up to about 13 h if most reach 256 | about 9.5 GPU-hours = about 5 h with both GPUs; up to about 10 h |
| think1024, 10 trials | about 6 h if outputs stay short (the budget only matters for long thinking); up to about 4x longer if thinking grows | about 5 h with both GPUs if outputs stay short; may need a second session if they grow |
| both arms | about 12 h if outputs stay short | about 10 h with both GPUs: at the edge of one session's limit, safer as two sessions (one arm each) |

(The existing thinking-off granite32 D run took about 0.8 s per generation; Qwen3's D run with thinking took about 12.5 h on the laptop
for 10 trials, which is what the upper bound looks like if Granite also thinks to the limit.)

**Cheapest version that still answers the question:** run think256 first with **3 trials** (trials 0-2: greedy + 2 sampled, the same seeds
as the D main run) on all 300 tasks x 2 conditions = 1,800 generations, about 2 h on the laptop. That measures criterion (a) precisely
(about +/-1.4 points on a 10% share).
- If (a) fails (cut-off share at most 10%), the answer is "not the same hazard" and the 1024 arm is not needed; the verdict comparison (b)
  is then reported descriptively from the 3 trials, and stated as less certain than the main study's 10-trial verdicts.
- If (a) holds, extend think256 to 10 trials (7 more, about 4 h) and run think1024 with 10 trials, as in section 3.
This sequence is fixed now; using it is a deviation from "10 trials per arm" only when (a) fails, and the report will say so.

## 9. What will be reported either way

A short report `EXPLORATORY_granite_thinking.md` with: the thinking switch and output format as verified; per arm and suite the cut-off
share (decision measure), the unparsed share (secondary), the token-limit share, mean output length, pass rates, stress diff, point-gate, CI-gate and four-class labels; the comparison
with the thinking-off decision; the verdict on (a), (b), (c) and the resulting category from section 5, **including a null result**
("not the same hazard") if that is what the data show; both scoring rules; the qwen3 rescoring under the strict rule; any deviation
from this plan (trial count, failed runs) with the reason.
