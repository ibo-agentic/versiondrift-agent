# Analysis pipeline (PLAN.md sections 8-9)

Reads run records only. Never loads a model, never uses the GPU, never writes into `results/`, `results_smoke/` or `results_v2/` (the code refuses).

## Run the full analysis once all runs are done

From the repo root on `main` (where `results_v2/` lives):

```bash
# 1. rescore-only factors (read D's records, write a NEW folder: rescored/)
python scripts/rescore_f7_lenient_parsing.py     # F7: escape-repair parsing
python scripts/rescore_f8_relaxed_intent.py      # F8: relaxed intent rule (5 causes)
python scripts/rescore_f10_one_trial.py          # F10: greedy trial only
python scripts/rescore_f9_ci_gate.py             # F9: CI gate vs point gate (writes a csv; also computed in step 2)

# 2. everything else
python -m vdanalysis.run_analysis --config configs/analysis_official_folders.yaml --out analysis_out
```

Add `--no-ci` for a quick point-gate-only pass, `--allow-missing` to analyze while runs are still incomplete (missing runs are listed in `run_warnings.json` and the report says it is partial). Without `--allow-missing`, a missing run is an error.

Tests (fake data only): `python -m pytest tests/test_vdanalysis_*.py`. The full `tests/` suite also works, but `test_native_tool_rendering.py` is skipped at collection because it loads `llama.dll`; pass `--run-llama-dll` to include it.

## Which config file maps the official folders

`configs/analysis_official_folders.yaml`. It holds the models, the 10 pairs (design/held-out split, size-changing tags), the protocol -> folder map, the DEVIATIONS.md rules, and the controls. Nothing about folders is hard-coded in Python.

- `overrides`: F3 `granite30` -> `F3_rerun`; F3 `phi4_mini` is the in-place rescored `F3` folder.
- `audit_only_folders`: `F3/granite30` (pre-fix original). The loader refuses it.
- `sampling_changed_models`: the six models for the F6 main number.
- `confounded_models` on `F4_json` and the `R*` protocols: Qwen3 gets the label `grammar+thinking_blocked`.
- `robust`, `controls`, `F5` and `R*` folder names and the control model lists are **assumptions**. Edit them to match what was actually run.

Run layout expected: `<root>/<folder>/<model>/<suite>/<run_id>/parsed_results.jsonl` (+ `run_manifest.json`, optional `raw_outputs.jsonl`). Exactly one run directory per suite folder.

## Method in one paragraph

Records are paired on (task_id, condition, drift type, fault type, trial_index). A decision is one adjacent pair x suite. Its stress diff is the mean paired success difference (new - old) over `schema_drift` + `fault_reporting`. Point gate: harmful if diff < -0.05, beneficial if > +0.05. CI gate: also needs the 95% task-cluster bootstrap CI (10,000 reps, seed 1234, same draws as `upgradecanary/gates.py`) clear of zero. A failure is a *format* failure if nothing parseable came out, else *semantic*.

## Conventions applied (DEVIATIONS.md)

- **F6:** `main` variant = only pairs touching a sampling-changed model; `all` is reported next to it.
- **F4:** generic JSON only. Qwen3 decisions under F4 (and R) carry `confounding = grammar+thinking_blocked`. They are excluded from the `main` F4 flip rate and reported as `confounded_only`. `qwen3_f4_vs_f2.csv` separates the two effects.
- **Size-changing pairs** (Qwen2.5->Qwen3, Gemma-2-2b->Gemma-3-4b) are flagged everywhere and also reported under `pair_subset = size_changing`.
- The Granite-3.0 `"tool"`-key gap is not fixed: F7 lenient parsing is escape repair only.

## Output tables (`analysis_out/`)

| file | meaning |
|---|---|
| `report.md` | hypotheses, flip rates, D decisions, controls, Qwen3 comparison in one page |
| `hypotheses.csv` | H1-H5: value, comparison value, counts, `supported` (True / False / empty = not testable). `variant` shows which pair subset or convention |
| `decisions_D.csv` | one row per pair x suite under D: stress/baseline/drift/fault diffs, CI, both labels, record-level flips (`neg_flips` = old ok -> new fail), `clean_uninformative` (both baselines >= 0.97) |
| `decisions_all_protocols.csv` | same rows for every protocol (F1, F2, ..., R) |
| `factor_flips_long.csv` | every (factor, pair, suite) decision vs D: both labels, `flipped`, `sign_flip`, effect change, and how much of the change came from format vs semantic failures |
| `flip_rates_by_factor.csv` | flip rate per factor x variant (`main` / `all` / `confounded_only`) x pair subset, with sign flips and format-vs-semantic-dominant counts |
| `disagreement.csv` | share of decisions where not all levels of a factor set agree (H4 inputs) |
| `size_changing_decisions.csv` | the size-changing pairs under every protocol |
| `failure_split.csv` | per run x condition: success, format-fail and semantic-fail rates |
| `controls.csv`, `controls_summary.csv` | A/A false-alarm and positive-control detection per model x suite and per control (H5 inputs) |
| `qwen3_f4_vs_f2.csv`, `qwen3_pair_labels.csv` | F2-D (thinking only), F4-D (grammar + blocked thinking), F4-F2 (grammar only), with CIs; Qwen2.5->Qwen3 labels under D/F2/F4 |
| `robust_protocol_checks.csv` | R truncation flag (>2%), clean-ceiling flag, unconstrained-run format-failure rate |
| `run_warnings.json` | record-count or manifest mismatches, missing runs |

H-test definitions: H1 = share of the D decisions that flip under >= 1 level of F1-F10 (>= 20%). H2 = pooled flip rate of {F1,F2,F4,F7} vs {F3,F5,F6,F8}. H3 = median |D stress diff|, flipping vs never-flipping decisions. H4 = disagreement across {F3,F5,F6}, R (CI gate) vs D (point gate), held-out pairs. H5 = A/A false-alarm <= 5% and positive-control detection >= 90% under R. H1-H3 are reported for all pairs and for `size_preserving` / `size_changing`. H4 is reported on all held-out decisions (primary) and on the sampling-changed held-out pairs only.
