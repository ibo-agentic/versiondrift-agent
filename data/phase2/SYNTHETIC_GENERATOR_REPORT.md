# W3 synthetic added tasks: why synthetic is not extended (report, 2026-10-19)

**Resolved (PLAN_PHASE2.md v4, edited 2026-10-19): option C. Synthetic is not extended in W3; the synthetic decisions
are additionally reported with a cluster bootstrap over tasks that share a baseline prompt (descriptive only).**

PLAN_PHASE2.md W3 asks for "synthetic: 300 tasks (original 100 + 200 from the generator, seed 20261019)", and the
task asked for "no duplicate prompts" and "no overlap with the original 100". The existing generator
(`scripts/generate_tasks.py`) cannot do that, so no `data/phase2/w3_added_synthetic.jsonl` was written.

## Facts (computed from `data/base_tasks.jsonl` and `build()` in the generator)

* The generator has **no random number generator and no seed**. It is pure construction: task `i` of a tool
  picks its values by `i % len(pool)` from small fixed pools (3 cities, 2 units, 2 queries, 3 time zones,
  2 symbols, 4 conversions) and a prompt template by `i % len(templates)`.
* The **original 100 tasks already contain 46 duplicate prompts** (54 distinct prompts, 36 distinct
  expected calls):

  | tool | tasks | distinct prompts |
  |---|---|---|
  | get_weather | 20 | 12 |
  | search_docs | 20 | 6 |
  | convert_units | 15 | 12 |
  | calculator | 15 | 15 |
  | get_time | 15 | 3 |
  | get_stock_price | 15 | 6 |

* Continuing the unchanged generator (task index 0..2999 per tool) reaches **no prompt that is not already in the
  original 100 for five of the six tools** (weather 12 reachable, 0 new; search_docs 6, 0; convert_units 12, 0;
  get_time 3, 0; get_stock_price 6, 0). Only `calculator` (the expression grows with the index) yields new
  distinct prompts. So 200 new tasks from the unchanged generator are either duplicates of existing prompts,
  or are all calculator tasks.
* Hence "no duplicate prompts" can only hold for the added tasks (against each other and against the originals);
  it cannot hold for the merged set, because the original file itself has duplicates (and must not change).

## Options (not chosen; this is a design decision of the study)

A. **Extend the generator with larger value pools and a seeded draw** (seed 20261019): same six tools, same 2x mix
   (40/40/30/30/30/30), same drift-type stratification, same prompt templates, but many more cities, queries,
   time zones, symbols, conversions and expressions. Needs the new pools to be fixed in the plan (they decide
   what the new tasks look like). No duplicate prompts is then achievable.
B. **Keep the generator unchanged and accept duplicates**: the added tasks repeat existing prompts, so they add
   task *instances* (drawn drift and fault differ by task id) but no new prompts; "no duplicate prompts" is then
   waived for synthetic.
C. **Drop synthetic from W3** (only the BFCL suites get more tasks).

What is done: BFCL added tasks (91 and 9), the manifest points at them, `check_configs` has 0 problems. The
synthetic entries of `configs/phase2/W3.json` stay `data_status: pending`, and the W3 gate in
`scripts/phase2/run_laptop.py` refuses to start W3 while that file is missing.
