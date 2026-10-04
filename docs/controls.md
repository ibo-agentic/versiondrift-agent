# Controls (PLAN.md section 6)

## A/A null pairs

**Pattern**: copy the model's base config, keep the top-level `seed` (drives
drift/fault assignment) unchanged, change `model.seed` and `trial_seeds` to
a different set of values, rename `experiment`. Nothing else differs.
Correct verdict against the base run: always neutral; any harmful/
beneficial verdict is a false alarm (PLAN.md H5: target <= 5% false-alarm
rate under R).

**Instantiated**: `configs/aa_qwen3_nothink_seedB.yaml`
(vs. `configs/real_trials_qwen3_nothink.yaml`), verified structurally
(dry run through the full pipeline with the mock provider, 45/45 records
for a 5-task slice; not run against the real model this session).

**Pending**: PLAN.md asks for >= 6 models (3 design, 3 held-out) x 3
suites. The other 5+ models don't have a PLAN.md "D protocol" base config
yet (native chat_wrapping, the new BFCL-multiple-100/fault_reporting
suite) to make an A/A copy *of* -- that base config has to exist first
(PLAN.md 10's own ordering: "Runs: D on all models first, ... then
controls"). Once it does, apply the exact pattern above to produce its
A/A pair.

## Positive control (a): Q2_K quantization

**Pattern**: copy the model's base config, point `model.path` at a Q2_K
GGUF of the same model, set `model.quant_level: Q2_K` (logged into
`run_manifest.json`'s `run_factors.F5_quant_level` -- purely documentary,
no code reads it). Nothing else differs. Correct verdict: harmful (a Q2_K
quant is a real, deliberate quality regression) -- measures the gate's
detection rate (PLAN.md H5: target >= 90%).

**Not instantiated**: no Q2_K GGUF file exists locally for any of this
project's 5 models. A Q2_K quant of a 7-8B model is a multi-GB download;
per this task's standing instruction ("do not download anything larger
than 1 GB without asking me first"), none was fetched. Say which model(s)
to get a Q2_K file for and I'll add the config once it's downloaded --
the config itself needs no new mechanism, just the two lines above.

## Positive control (b): tool descriptions removed

**Pattern**: copy the model's base config, add `prompt_format:
no_description` (new mechanism, this batch --
`upgradecanary/runner.py:_strip_descriptions`, recursively drops every key
literally named `"description"` from the rendered tool schema(s) before
the prompt is built; names, types, and `required` are untouched). Works
for the synthetic suite's internal schemas, BFCL-simple-100's native docs,
and BFCL-multiple-100's multi-candidate lists alike. Correct verdict:
harmful -- same detection-rate purpose as the Q2_K control, cheaper to run
since it needs no extra download.

**Instantiated**: `configs/positive_control_no_description_qwen3_nothink.yaml`
(vs. the same base config as the A/A example above), verified structurally
the same way.

**Pending**: PLAN.md asks for >= 4 models total across both positive
controls; same "needs a D-protocol base config per model/suite first"
caveat as the A/A pairs above applies to the remaining models.

## Validation performed this batch (no model run)

- `prompt_format: no_description` validated by `validate_run_factors()`
  and exercised by `build_prompt()`/`_strip_descriptions()` directly
  (unit tests, `tests/test_plan_factors.py`): confirmed it strips
  descriptions from the internal-schema shape, a BFCL-native doc
  (including nested per-argument descriptions), and a list of several
  BFCL-multiple candidates, while leaving name/type/required untouched.
- Both new config files were validated (`validate_run_factors`,
  `resolve_run_factors`) and dry-run end-to-end through `runner.run()`
  with the provider swapped to `mock` (a scratch copy, not the committed
  file) for a 5-task slice -- confirms the YAML structure is accepted by
  the whole pipeline. Neither was run against the real Qwen3-8B model.
