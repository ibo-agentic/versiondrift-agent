# Phase 2 analysis: what each part does, and why

This is the code that will turn the Phase 2 runs into numbers. It is an **add-on** to the
Phase 1 analysis (`vdanalysis/`). It does not change the Phase 1 code. Everything lives in
`vdanalysis/phase2/`, with two config files in `configs/`.

It is written and tested **before** the Phase 2 runs exist, on small made-up ("fixture") data
with known answers (`tests/fake_phase2.py`). It must not be run on real Phase 2 records until
the plan is locked (PLAN_PHASE2.md section 0). The only run on real data so far is the
regression check below, which uses Phase 1 data only.

## The idea in one paragraph

A "decision" is one upgrade pair on one suite (30 of them). The gate looks at how much the
success rate changed from the old model to the new one and says *harmful*, *neutral* or
*beneficial*. Phase 1 asked: do these labels change when you change a setup detail (a "factor")?
Phase 2 asks the same thing with more trials, a better noise check (A/A), a fairer hardware
comparison for F5, and a second gate that also looks at the easy (baseline) tasks.
This code reads saved records, recomputes the labels, and checks the Phase 2 hypotheses P1-P7.
It never runs a model.

## The parts

| File | What it does | Why |
|---|---|---|
| `config.py` | Reads a config file that says "start from the Phase 1 config, then change these things". Knows where each protocol's records are, how many trials to expect, which models are on Kaggle, which models skip F6, and the thresholds. | Nothing about folders or thresholds is buried in the code, so a change is a visible edit to a config file. |
| `merge.py` | A run can be stored in several folders (Phase 1's trials 0-2 in `results_v2`, the new trials 3-9 in `results_v3`; or the original tasks and the added tasks). This glues them together onto one list of trials, and **refuses** if they do not fit: the same (task, condition, trial) twice, a prompt that is not byte-for-byte the same, a different drift/fault type, a different temperature for the same trial, or a trial seed that does not match its place. Gaps (a missing trial) are warnings. It never assumes a run has 900 records; it works for any number of tasks and trials. | The plan says the laptop is deterministic, so old and new trials can share a run. The checks prove that they really belong to the same run instead of trusting it. |
| `analysis.py` | The decision engine with four Phase 2 rules. **F6 trimming**: for the 10 models whose F6 sampling equals D's, the F6 run *is* the D run. **F10** is just D's greedy trial (no files). **Same-hardware rule**: a factor run is compared with a baseline on the same machine (F5 and R_F5 of the Kaggle models against the Kaggle D / R baselines), and a pair that mixes machines is refused. **Views**: the same analysis on the greedy trial only, the sampled trials only, or a subset of tasks. | Section 5 of the plan: an effect must be measured against a baseline from the same hardware, otherwise "quantization" and "hardware" are mixed up. |
| `controls2.py` | The A/A and positive controls. The **new A/A** (`aa2`) compares arm 1 with arm 2 on *all* records, and stops with an error unless the prompts are identical in both arms and every record is matched. The **secondary full-score gate** scores baseline + stress with the same rule and thresholds as the primary gate and is added as extra columns; the primary columns are never touched. Summaries carry exact (Clopper-Pearson) 95% intervals. | Phase 1's A/A changed the run seed, which redrew the stress prompts, so only a part of the records could be compared. The new design measures sampling noise on everything, and the assertions make it impossible to run it wrongly by accident. |
| `hypotheses2.py` | P1-P7 exactly as in section 4, as plain functions of the decision/flip/control tables. | One place, one definition each. Thresholds come from the config. |
| `descriptive.py` | The descriptive outputs: hardware noise (D laptop vs D Kaggle, per model and per pair), the size of F5's shift next to the A/A noise, flips Phase 1 did not see, human-label agreement (kappa). | Section 4 lists them as descriptive (no threshold). |
| `stats2.py` | Exact Clopper-Pearson intervals and Cohen's kappa (no SciPy needed). | Small counts (e.g. 2 false alarms in 48) need exact intervals. |
| `rescore_v3.py` | Re-scores the *new* D records for F7 (lenient parsing) and F8 (relaxed intent) with the same functions as Phase 1, into `rescored_v3/`. | Scoring-only factors are recomputed from saved records, not re-run. |
| `run_phase2.py` | The command that runs everything and writes CSV tables into `analysis_out_v3/`. | |
| `report.py` | Turns the tables into one readable page, `analysis/phase2/analysis_report.md`. It only formats; it decides nothing. | |
| `regression.py` | The check that this code, fed Phase 1 data in "phase1 mode", gives exactly the Phase 1 tables back. | Proof that the add-on did not change what Phase 1 means. |

## How to run

```bash
# after the plan is locked and the Phase 2 runs are in results_v3/:
python -m vdanalysis.phase2.rescore_v3 --config configs/analysis_phase2.yaml --factor F7
python -m vdanalysis.phase2.rescore_v3 --config configs/analysis_phase2.yaml --factor F8
python -m vdanalysis.phase2.run_phase2 --config configs/analysis_phase2.yaml --out analysis_out_v3 \
       --report analysis/phase2/analysis_report.md [--labels labels.csv]

# regression check (Phase 1 data only; takes a while because of the bootstrap):
python -m vdanalysis.phase2.regression --config configs/analysis_phase1_regression.yaml \
       --reference analysis_out --out analysis_out_v3/regression_phase1
```

Tests: `python -m pytest tests/test_vdanalysis_phase2_*.py` (fixture data only).

The label file for W6 is a CSV with the columns `record_id,labeler,label`. Any labeler name
works; the rule's labels go in under the name `rule` (config `phase2.rule_labeler`).
W5 (closed-model pairs) needs no special code: give the same pipeline a config with those
models and pairs.

## Things to know

* **Matches PLAN_PHASE2.md v4.**
* **Layout assumption.** The plan does not say where `results_v3` stores things. The config assumes it
  mirrors `results_v2`: `<folder>/<model>/<suite>/<run_id>/parsed_results.jsonl` (+ `raw_outputs.jsonl`),
  with these folder names: `D R F1 F2 F3 F4_json F5 F6` (new trials 4-10 for laptop runs; all 10 trials
  for the Kaggle F5 models), `R_PC_Q2K R_PC_NODESC` (W2b), `D_KAGGLE R_KAGGLE` (Kaggle baselines),
  `D_AA2 R_AA2` (second A/A arm), `W3_D W3_R` (added tasks), plus `rescored_v3/F7 F8`. If the runs are
  written elsewhere, only the config changes.
* **Trial numbering.** The new laptop runs store their trials as 0-6. The config says `trial_offset: 3`
  for them, and `merge.py` checks the trial seed (1237...1243) so a wrong offset cannot slip through.
* **Trial counts can differ between runs.** Comparing a 10-trial run with a 3-trial run (R_F5, or Phase 1's
  own control records) uses the trials they share.
* **Kaggle reuse** (plan section 2, decided by W0 Part C): the config currently runs all 10 Kaggle trials
  fresh. If reuse is allowed, replace one line of the `F5` entry (marked in the config).
* **"Replicate" (P2, P6), plan section 5.** A Phase 1 flipped decision replicates if, at 10 trials, it flips
  under at least one of the factors that flipped it in Phase 1, with the same label change (its D label
  equals its Phase 1 D label, its label under that factor equals the Phase 1 label under that factor).
  P6 is the same rule under F5 only, starting from the same-hardware D label. The other three readings
  (every originally flipping factor must replicate; same sign of the change instead of same label change;
  both) are written to `p2_p6_replication_variants.csv` as descriptive output, with the primary one marked.
  They never decide a verdict.
* **P4 and P5 read W2b**: the Q2_K and no-description controls at 10 trials on the laptop (Phase 1 trials
  1-3 reused, trials 4-10 new), compared with the W1 laptop R runs on all 10 trials.
* **Secondary gate on Phase 1's own control records** (3 trials, no new runs) is a descriptive table only
  (`phase1_controls_secondary*.csv`); it feeds no hypothesis.
* **The secondary gate's score** is the equal-weight average of the three conditions (baseline,
  schema_drift, fault_reporting), as in plan W4.
* **F5 noise bound.** Descriptive only. Headline: the 95th percentile (linear interpolation, NumPy's
  default) of |stress difference| over the W2 D A/A decisions, next to each F5 shift; the maximum is
  reported too.
