### Plain-language summary of the noise check

- **The item-level churn is real, not rerun noise.** A model compared with a rerun of itself changes sides on few questions: 0.3% to 7.2% of its 600 questions under D (qwen3 the most, 43), 0.5% to 6.3% under R. Every upgrade churns far more than that. Over all 10 upgrades, D churn is 1,131 questions against an expected 184.5 from same-model noise (excess +946.5, 15.8% of the questions); without qwen25 -> qwen3 it is 862 against 160 (excess +702, 13.0%). R gives the same picture (excess +778 overall, +704 without qwen25 -> qwen3). The smallest case, granite31 -> granite32, still has 28 changed questions against about 11.5 expected.
- **Caveats on that noise floor.**
  - The two arms of a model share trial 0, the greedy trial, which is identical in both arms (9,600 of 9,600 stress records have the same score). So 1 of the 10 trials is not an independent draw, and the same-model churn slightly understates fully independent rerun noise.
  - For the same reason, the greedy-only rows have a same-model churn of exactly 0 and **cannot serve as a noise floor**. Their "excess" is just the upgrade churn.
  - The expected churn uses the mean of the two models' own churn, as asked. It is a rough yardstick, not a model of how the noise of two different models combines.
- **Why mistral_v01 -> mistral_v02 shows a 'neutral' stress diff but a net of -38 questions under D.**
  - The two numbers measure different things. The stress diff averages **every trial** of every question: mean pass rate 0.7728 vs 0.7723, a diff of -0.0005. The majority count only records **questions that cross the 6-of-10 line**.
  - mistral_v02 is much more all-or-nothing than mistral_v01. It has 364 questions at 10/10 (v01: 238) and 63 at 0/10 (v01: 27), while v01 has 266 questions sitting at 6-9 of 10 (v02: 102).
  - The 88 questions that drop below the line ('got worse') cost 0.095 of stress diff. The 50 that cross upward ('got better') add +0.049.
  - The 'both right' questions, which the count ignores, add +0.050 on balance. This fits v02 pushing many questions that v01 passed 6-9 times up to 10/10 (see the distribution), and it cancels the loss.
  - The 6-of-10 rule also treats a tie at 5/10 as wrong; v01 has 19 such questions, v02 has 8.
  - So "no net change" and "38 more questions lost than gained" are both true. The net count is not an alternative estimate of the score change.
- **The same pattern explains every sign disagreement** (7 of 60 decisions: D 3, R 4). In each one the 'both right' cell (questions moving up toward 10/10) carries the positive stress diff, while the crossing counts lean negative. Under R, mistral_v01 -> v02 has a clearly positive stress diff on bfcl_simple and bfcl_multiple (+0.060 and +0.063) and a still negative majority net (-3 and -1).
- **What this weakens:** the item-level tables' "net" and "got worse" counts depend on the 6-of-10 threshold, and they lean negative when the new model is more all-or-nothing. They should not be read as the direction of the upgrade; the stress diff is the study's measure. The churn claim (many questions change sides under a near-zero net score) stands, and the noise check makes it stronger.
- **Failure types by condition:**
  - Without qwen25 -> qwen3, 'got worse' under D is mostly wrong status on fault_reporting (155 of 203 fault_reporting questions) and wrong or invalid arguments on schema_drift (143 of 164). Broken output accounts for 47 fault_reporting and 17 schema_drift questions.
  - qwen25 -> qwen3 under D is almost all broken output on both conditions (112 of 113 fault_reporting, 122 of 127 schema_drift).
  - Under R, broken output on schema_drift drops to 0 without qwen25 -> qwen3, as expected with the JSON grammar.
