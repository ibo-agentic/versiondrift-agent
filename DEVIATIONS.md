# Deviations from PLAN.md (v1, binding 2026-10-05)

Every change to the plan after PLAN.md was committed as v1 (git tag
`plan-v1`) is logged here with the date and reason, instead of editing
PLAN.md itself. Newest first.

## 2026-10-06 — F1's qwen3/bfcl_multiple run split into two halves

**Reason**: this one run consistently exceeded the ~2-hour background-
execution ceiling on this session (two consecutive full-length attempts
each ran the full 2 hours without completing). That ceiling is a
constraint of this session's tooling, not a property of the experiment
or the protocol — F1 itself (`max_tokens=1024`, everything else
identical to D) was not changed in any way.

**What was done**: split the 100-task `bfcl_multiple` run into two
50-task halves (`scripts/f1_qwen3_bfcl_multiple_split.py`), ran each
separately (each comfortably under 2 hours: 3742s and 4076s), and
merged their `raw_outputs.jsonl`/`parsed_results.jsonl` into a single
900-record run, recomputing `summary.json` from the merged records via
the real `evaluator.summarize()`. The merged `run_manifest.json` carries
an explicit `"note"` field documenting the split.

**Why this is safe**: every task's randomness is keyed by `rng_for(seed,
task_id, condition)` (see `upgradecanary/utils.py`) — never by the
task's position in the list or by which process/invocation generated
it. Splitting the task file into two subsets and running each under the
same global seed (1234) and the same trial seeds therefore produces,
for each individual task, the exact same generation as if all 100 tasks
had been run together in one invocation. Only the physical grouping
into two subprocess calls differs; nothing about the model, prompts,
conditions, trials, or sampling changes.

**Proof, not just assertion** (`scripts/prove_split_equivalence.py`):
took 10 tasks from the synthetic suite for a fast model (gemma2_2b,
protocol D, to keep the proof itself cheap), ran them once as a single
10-task run and once as two 5-task halves, and compared every record.
**Result: 90/90 records identical** in both `parsed_results.jsonl` and
`raw_outputs.jsonl` (excluding the `run_id` field, which legitimately
differs between the two invocations' timestamps) — confirmed by direct
comparison, not assumed from the seeding argument alone.
