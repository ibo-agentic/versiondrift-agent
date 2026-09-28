# UpgradeCanary

Pilot scaffold for a **local** LLM-agent robustness experiment. It measures how
an agent copes with "upgrade drift": tool schema changes and runtime faults.
Everything runs on your machine — **no paid APIs, no external services, and no
automatic model downloads**. The default `mock` model provider lets the full
pipeline run deterministically before any GGUF file exists.

## What the pipeline does

For each task × condition (`baseline`, `schema_drift`, `runtime_fault`):

1. Pick a perturbation with a seeded RNG (schema drift types: `field_rename`,
   `field_drop`, `type_mutation`, `unexpected_field`, `enum_drift`; runtime
   faults: `timeout`, `tool_exception`, `empty_result`, `stale_result`,
   `partial_result`). Under `schema_drift`, each task's `drift_type` hint is
   honored when the tool supports it (stratified coverage); otherwise the
   seeded RNG chooses among applicable types.
2. Build a prompt showing the (possibly drifted) tool schema.
3. Generate a response (mock stub now; llama.cpp later).
4. Parse the JSON tool call, execute it against the mock tool registry with
   fault injection, allow one retry after retryable faults.
5. Score with pure comparisons (no LLM judge) and write results.

## Metrics

All scoring is deterministic comparison — there is no LLM judge.

Per record:

| Metric | Meaning |
| --- | --- |
| `parse_ok` | Raw output contained a usable JSON tool call |
| `tool_name_ok` | Parsed tool name matches the expected tool |
| `args_exact` | Parsed arguments match the expected arguments exactly |
| `args_intent_match` | Parsed arguments have the same intended meaning as the expected call, compared in the drifted schema's semantic space (renames, enum remaps, type coercions, and dropped optional fields are normalized away) |
| `args_valid_under_drift` | The parsed call passes schema validation against the (possibly drifted) schema the tool now advertises |
| `executor_ok` | The tool executed the call without validation or runtime errors |
| `recovered_after_fault` | A retry after a retryable fault succeeded (null outside runtime_fault) |

The gap between `args_intent_match` and `args_valid_under_drift` is the core
upgrade-drift signal: a stale agent's call can mean the right thing yet be
rejected by the upgraded schema.

**Strict policy:** required arguments must be present **even if the field spec
declares a `default`** — the executor never auto-applies defaults. Missing
required fields always fail validation.

The record `score` depends on the condition:

- `baseline`: parse + tool name + exact args + clean execution
- `schema_drift`: parse + tool name + intent match + clean execution
- `runtime_fault`: recovered after a retryable fault; for non-retryable faults
  (e.g. `stale_result`) a clean execution counts

## Requirements

- Python 3.10+ (developed on 3.14)
- For the mock pilot: only `PyYAML`
- For tests: `pytest`
- For real-model runs: `llama-cpp-python` (see below)

## Setup (Windows)

```bash
py -m venv .venv
.venv\Scripts\activate
pip install pyyaml pytest
```

For real-model runs, additionally:

```bash
# GPU (RTX 4060) — prebuilt CUDA wheel:
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
# or CPU-only:
pip install llama-cpp-python
```

## Run the mock pilot (no model needed)

```bash
python -m upgradecanary.runner --config configs/pilot.yaml
```

This writes a new run directory `results/<run_id>/` containing:

| File | Contents |
| --- | --- |
| `run_manifest.json` | run id, seed, config path, Python/platform versions |
| `raw_outputs.jsonl` | prompt (+ hash) and raw model text per record, incl. retries |
| `parsed_results.jsonl` | parsed call, drift/fault applied, executor outcome, per-metric booleans (no run ids/timestamps — byte-stable across reruns) |
| `summary.json` | per-condition metric means and score deltas vs baseline |

The summary is also printed to stdout. Expected mock outcome: baseline passes
fully; schema_drift drops (stale agent args are rejected by the upgraded
schema, so `args_intent_match` stays high while `args_valid_under_drift` and
`executor_ok` drop); runtime_fault recovers via the retry.

Determinism check — run twice and compare:

```bash
python -m upgradecanary.runner --config configs/pilot.yaml
# re-run, then compare the two parsed_results.jsonl files; they must be identical
```

## Tests

```bash
python -m pytest -q
```

(run from the repo root). Covers metric semantics, the strict
missing-required policy, and task/drift coverage counts.

## Regenerating the task file

`data/base_tasks.jsonl` holds 100 synthetic tasks: balanced tool coverage
(20/20/15/15/15/15), stratified `drift_type` hints (every drift type ≥ 10
tasks, subject to per-tool applicability), and unique deterministic ids. To
rebuild it deterministically:

```bash
python scripts/generate_tasks.py
```

## Real-model smoke test (optional, manual steps)

This project never downloads models or installs inference backends for you.

1. Install the backend (RTX 4060 — prebuilt CUDA wheel):
   `pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124`
   (CPU-only: plain `pip install llama-cpp-python`.)
2. Download **mistral-7b-instruct-v0.2.Q4_K_M.gguf** (or another 4-bit GGUF that
   fits 8GB, e.g. Qwen2.5-7B-Instruct-Q4_K_M) from Hugging Face and place it
   under `models/` — the filename must match `model.path` in the config
   (`models/mistral-7b-instruct-v0.2.Q4_K_M.gguf`).
3. Run the smoke config (first 10 tasks only, greedy decoding, seed fixed):

   ```bash
   python -m upgradecanary.runner --config configs/real_smoke_v0.2.yaml
   ```

**If CUDA runs out of memory:** lower `n_ctx` in `configs/real_smoke_v0.2.yaml`
(2048 → 1024). A Q4_K_M 7B model uses ~4.2GB, so context is the first knob to
turn; `n_gpu_layers: -1` offloads all layers and is silently ignored by
CPU-only builds.

**Prompt template:** Mistral-7B-Instruct is a chat fine-tune — without its
`[INST]…[/INST]` wrapping it behaves like a base model and tends to answer
with prose instead of the JSON tool call. The smoke config therefore sets
`prompt_template: "<s>[INST]\n{prompt}\n[/INST]"`, applied only inside the
llama_cpp client; the raw prompt (tool schema + JSON-only instruction +
question) is inserted at `{prompt}`, and `stop: ["</s>"]` cuts generation at
the turn end. To disable wrapping, remove or comment out `prompt_template`;
to switch models, adapt the template string and stop sequences (e.g. Llama-3
chat format). The mock provider never applies templates. llama.cpp seeding is
best-effort on GPU; for byte-identical reruns use the mock provider.

## Project layout

```
configs/pilot.yaml          pilot configuration (seed, conditions, perturbations)
configs/real_smoke_v0.2.yaml  real-model smoke config (first 10 tasks, llama_cpp)
data/base_tasks.jsonl       100 deterministic tool-use tasks (regenerate: python scripts/generate_tasks.py)
scripts/generate_tasks.py   deterministic task-file generator
tests/                      pytest suite (python -m pytest -q)
upgradecanary/
  runner.py                 experiment loop + result writing (python -m upgradecanary.runner)
  tasks.py                  Task dataclass + loader (optional drift_type hint)
  tools.py                  mock tool registry, schemas, executor, fault injection
  parsing.py                JSON tool-call extraction from raw model text
  evaluator.py              deterministic metrics + summary aggregation
  utils.py                  seeded RNGs, JSONL io, run ids
  model/                    model clients: mock_llm.py, llama_cpp_client.py, base.py
  perturbations/            schema_drift.py (drift types + drifted-schema math), runtime_faults.py
results/                    run outputs (gitignored)
```

## Extending

- **Add a task**: append one line to `data/base_tasks.jsonl` with `task_id`,
  `prompt`, `tool`, the exact `expected_call`, and optionally a `drift_type`
  hint; or regenerate with `python scripts/generate_tasks.py`.
- **Add a tool**: add a schema to `BASE_SCHEMAS` and a handler in
  `upgradecanary/tools.py`, both keyed by the same name.
- **Add a drift type**: add candidate specs in `_SPECS` in
  `upgradecanary/perturbations/schema_drift.py` and enable the type in
  `configs/pilot.yaml`.

All randomness flows from `seed` in the config via per-record RNGs, so a given
config always produces the same experiment.
