**EXPLORATORY overview (post hoc, not part of the pre-registered analysis).** A reading aid built from `DEVIATIONS.md` (state at tag pre-analysis-v2.3 plus the entries (l) and (m) of 2026-11-14). It records nothing new; where this table and `DEVIATIONS.md` disagree, `DEVIATIONS.md` wins.

# Every entry in DEVIATIONS.md, oldest first

**Types:** *pipeline/engineering* = a fix, a check or an operational choice; *analysis change* = how something is defined, computed or reported; *scope/gate change* = what is run, or a gate or start rule. "Before/after" refers to the first look at **Phase 2 results**, which was the analysis run on 2026-11-14 (first output tables, tag pre-analysis-v2.1). Phase 1 analysis (the first full run on Phase 1 data) was on 2026-10-15; every October entry was written before it except the 2026-10-15 entry itself, which records fixes made right before it.

| # | Date | What it says (plain words) | Type | Before / after Phase 2 results | Can it affect results? |
|---|---|---|---|---|---|
| 0 | 2026-10-05 | **plan-v1**: PLAN.md becomes binding; this file records every later departure from it. (Baseline, not a deviation.) | baseline | before (no Phase 2 yet) | n/a |
| 1 | 2026-10-06 | One F1 run (qwen3 on bfcl_multiple) was run in two halves because a session limit cut long runs. | pipeline/engineering | before | Not intended; later split-equivalence tests (W0) support merging. |
| 2 | 2026-10-06 | Why the F3 native-template models parsed poorly (e.g. Phi-4-mini): causes found, harness left unchanged. | pipeline/engineering (diagnosis only) | before | No change made, so no. |
| 3 | 2026-10-07 | Found a real parser gap for Granite-3.0 in F3 and fixed it; the model was rerun into `F3_rerun`. | pipeline/engineering | before | **Yes**: changes granite30 F3 scores (parse rate up about 1.5 points) and phi4_mini via rescoring. |
| 4 | 2026-10-07 | Follow-up checks of that parser fix without the GPU: the fix changes 28 of 1,800 records and nothing else. | pipeline/engineering (check) | before | Confirms the size of #3's effect. |
| 5 | 2026-10-07 | F6 (the sampling preset factor) gets per-trial overrides and a table of values before any F6 run. | scope/gate change (defines F6) | before | Yes, by design: it defines what F6 tests. |
| 6 | 2026-10-08 | F6 finished: 1 greedy record out of 14,400 differed from D, from known GPU nondeterminism. | pipeline/engineering (check) | before | Negligible (1 record). |
| 7 | 2026-10-08 | F4 is run with generic-JSON constrained decoding only; the full-schema version is dropped (time, cost). | scope/gate change | before | **Yes**: one planned F4 level is not tested. |
| 8 | 2026-10-08 | F6 flip rates are reported on the 6 models whose sampling actually changed (main), all pairs shown too. | analysis change | before | **Yes**: decides which F6 number is the main one. |
| 9 | 2026-10-08 | Qwen3's generic-JSON grammar blocks its thinking, so F4 and R are confounded for qwen3 and flagged as such. | analysis change (confound flag) | before | **Yes**: qwen3 under F4/R is labelled confounded. |
| 10 | 2026-10-08 | Analysis conventions fixed before any verdict: stress conditions = schema_drift + fault_reporting, equal-weight stress diff; F3 main flips = both-native pairs only; and others. | analysis change | before | **Yes**: these define the stress diff and the main flip counts. |
| 11 | 2026-10-09 | F4 finished: a qwen3-only repetition loop shows up at full scale. | pipeline/engineering (finding) | before | Yes for F4/qwen3 (truncated outputs); recorded, not changed. |
| 12 | 2026-10-09 | R_unconstrained (a separate R run without grammar) is taken from F1's existing runs; no new run. | scope/gate change | before | Small: uses existing data for that diagnostic. |
| 13 | 2026-10-09 | R config checked field by field against D (two fields differ, as planned); qwen3 R runs pre-split for time. | pipeline/engineering (check) | before | No. |
| 14 | 2026-10-11 | R finished: the same qwen3-only loop recurs at a lower rate. | pipeline/engineering (finding) | before | Yes for R/qwen3 (recorded, flagged). |
| 15 | 2026-10-11 | The A/A and positive controls are defined (R's config with one change each), before any run. | scope/gate change (defines controls) | before | Yes, by design: they define the controls. |
| 16 | 2026-10-12 | Controls finished: configs differ from R only in the intended field; one more timing anomaly, checked. | pipeline/engineering (check) | before | No. |
| 17 | 2026-10-12 | R_F6, R_F3 and F11 (old chat wrapper) are defined before any run; the native-template model list corrected. | scope/gate change | before | Yes, by design: new nuisance and exploratory runs. |
| 18 | 2026-10-12 | Quick tests of R_F6, R_F3, F11 passed; F11's qwen3 not pre-split. | pipeline/engineering (check) | before | No. |
| 19 | 2026-10-13 | F5 and R_F5 for the 8B models run on Kaggle 2x T4 because Q8 does not fit the laptop GPU. | scope/gate change (hardware) | before | **Yes**: quantization and hardware are confounded in Phase 1 (this is what W1 same-hardware baselines address). |
| 20 | 2026-10-13 | R_F6, R_F3, F11 finished: checks passed, F11's manifest differences explained. | pipeline/engineering (check) | before | No. |
| 21 | 2026-10-13 | F11 vs D: the exact config fields that differ (7 for Qwen, 5 for Mistral). | pipeline/engineering (check) | before | No. |
| 22 | 2026-10-14 | F5 and R_F5 small models finished: configs differ from D and R only in the quant level. | pipeline/engineering (check) | before | No. |
| 23 | 2026-10-15 | Before the first full analysis: two file-organization/config fixes (rescored folders), one diagnostic quirk flagged and left. | pipeline/engineering | before (Phase 1 analysis not yet run) | Low: which files are read, not the scoring. |
| 24 | 2026-11-08 (a) | The W3 determinism check passes if strict scores and prompts are 100% identical (parsed output may differ slightly); revised 2026-11-09 after the R split result was seen. | scope/gate change | before | Only decides whether W3 may run; W3 ran. Written after the R split test (an equivalence check, not a study result). |
| 25 | 2026-11-08 (b) | S1/S2 under the four-class gate use each decision's observed class, not a bootstrap inside the bootstrap. | analysis change (addendum) | before | Yes: how the addendum counts flips under four classes. |
| 26 | 2026-11-08 (c) | The per-decision noise flip probability is the share of task resamples whose two arms get different labels. | analysis change (addendum) | before | Yes: feeds the expected noise share in S1. |
| 27 | 2026-11-08 (d) | F5's noise floor uses the laptop D vs D_AA2 rerun as a proxy for Kaggle noise (stated as a limitation). | analysis change (limitation) | before | Interpretation only: affects how F5 excess is read. |
| 28 | 2026-11-08 (e) | Four-class verdict: harmful and beneficial come from the CI gate; neutral needs a 90% interval inside +/-0.05. | analysis change (addendum) | before | Yes: defines S3. The primary gate is unchanged. |
| 29 | 2026-11-08 (f) | S9 (hierarchical model) specified: statsmodels pinned, fixed effects and random intercepts. | analysis change (addendum) | before | Only S9, which is descriptive. |
| 30 | 2026-11-08 (g) | Kaggle upload and run order fixed (K02, K03, K07, K05, ...); batches unchanged. | pipeline/engineering | before | No: no run, seed or setting changes. |
| 31 | 2026-11-08 (h) | W3 no longer waits for the Kaggle runs; it runs on the idle laptop GPU. | scope/gate change | before | Only timing and order of runs, not scores. |
| 32 | 2026-11-08 (i) | A descriptive row: S3 verdict on synthetic with tasks that share a prompt resampled together. | analysis change (addendum, descriptive) | before | Only that descriptive row. |
| 33 | 2026-11-14 (j) | Code bug: the audit-only ban on F3/granite30 also blocked the new, fixed Phase 2 run; the ban now applies only to the Phase 1 folders. Includes the pytest-config note (test collection ignores the extracted Kaggle copies). | pipeline/engineering | before any result (the analysis crashed before writing output) | **Yes**: without it the F3/granite30 Phase 2 data could not be read; the fix reads the post-fix data. |
| 34 | 2026-11-14 (k) | Bug: P7 was skipped because the code asked for a synthetic W3 run that never existed; P7 now uses the two BFCL suites. | pipeline/engineering | **after** (the first run's results were seen) | Only P7 (descriptive). Other tables checked identical by diff. |
| 35 | 2026-11-14 (l) | W6 human labeling: frame, strata (33/33/33/33/34/34), verdict definition, `unsure` handling and blinding, filling gaps in the plan. | scope/gate change (W6 design) | **after** the main Phase 2 analysis; before the W6 draw and any label | Only W6 (agreement numbers). It was decided after the P-results were seen but before any labels exist. |
| 36 | 2026-11-14 (m) | Bug: the "excluding qwen25->qwen3" S1 table showed full-data point estimates beside an interval that left the pair out; the estimates are now recomputed on the reduced data. | analysis change (bug fix) | **after** (found after the addendum ran) | Only that one table; the rerun differs from the first only in it. |

## Reading the table

- **Entries that changed numbers in the confirmatory results (P1 to P7):** #3 and #4 (the Granite parser fix), #8, #9, #10 (analysis conventions fixed before any verdict), #7 and #19 (what F4 and F5 test and where they run), and #33 (reading the F3/granite30 Phase 2 data). All were decided before Phase 2 results existed, except that #33 was a fix that let the analysis run at all.
- **Entries decided after Phase 2 results were first seen:** #34 (P7 bug), #35 (W6 design, before any label) and #36 (one addendum table). None of them changes P1 to P6, the thresholds, the gates or the controls.
- **Not in this file:** the plan documents themselves (PLAN_PHASE2.md tagged plan-v2 on 2026-10-19, and the analysis addendum tagged plan-v2.1 on 2026-11-08) are plans, not deviations. Their tags are the reference for what was pre-registered.
- **Caveat:** "can it affect results" is my plain-language reading of each entry's text; I did not recompute effects. Entries 1 to 23 are summarised from their opening paragraphs only.
