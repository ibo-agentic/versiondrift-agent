# analysis/audit/

Read-only audit tooling and reports for the UpgradeCanary reviewer audit
(2026-10-02). Analysis scripts (`*.py` without a leading underscore) read
existing `results/*/parsed_results.jsonl` / `raw_outputs.jsonl` and write
their own `*.md`/`*.csv` reports in this directory; they never modify
`results/`, `data/`, or `upgradecanary/`.

## Windows DLL-loading workaround (`_dll_preload.py`, `_run_config.py`)

On this machine, plain `import llama_cpp` fails:

```
RuntimeError: Failed to load shared library '...\llama_cpp\lib\llama.dll':
Could not find module '...\llama_cpp\lib\llama.dll' (or one of its dependencies).
```

This happens even with `upgradecanary/model/llama_cpp_client.py`'s own
`_add_bundled_cuda_dll_dirs()` fix in place (which registers the bundled
NVIDIA `cuda_runtime`/`cublas` DLL directories). The root cause is a
Windows DLL-search-order issue specific to this `llama-cpp-python==0.3.35`
install: `llama_cpp`'s own loader (`_ctypes_extensions.load_shared_library`)
adds its `lib/` directory via `os.add_dll_directory` and then calls
`ctypes.CDLL("llama.dll", winmode=ctypes.RTLD_GLOBAL)` directly — but on
this machine that single call cannot resolve `llama.dll`'s sibling
dependencies (`ggml-cuda.dll`, `ggml.dll`, `ggml-base.dll`, `ggml-cpu.dll`,
`mtmd.dll`, all in the same folder).

**Workaround**: load each of those DLLs individually, in dependency order,
with plain `ctypes.CDLL(absolute_path)` calls *before* `import llama_cpp`
ever runs. Once each dependency is already resident in the process,
`llama_cpp`'s own subsequent `CDLL("llama.dll", ...)` call succeeds — this
was verified interactively (each individual load succeeds, and the
model then loads and generates correctly on GPU).

- **`_dll_preload.py`**: `preload()` registers the bundled CUDA/cuBLAS and
  `llama_cpp/lib` directories, then loads
  `ggml-base.dll, ggml-cpu.dll, ggml-cuda.dll, ggml.dll, mtmd.dll, llama.dll`
  in that order. Idempotent (safe to call more than once).
- **`_run_config.py`**: thin CLI wrapper — `python _run_config.py <config>` —
  that calls `preload()` and then invokes the real, unmodified
  `upgradecanary.runner.main(["--config", config])`. This is the only
  entry point used to produce every real-model run in this audit; nothing
  under `upgradecanary/` was changed to work around this issue.

This is a **machine-local workaround**, not a fix to the project itself:
it does not change `upgradecanary/model/llama_cpp_client.py`'s own CUDA-DLL
handling, and a machine where `import llama_cpp` already works does not
need either file. If the project wants this folded into the real client
long-term, the natural place is inside
`LlamaCppClient._add_bundled_cuda_dll_dirs()` (or a sibling function run
before the `from llama_cpp import Llama` import) — not done here, since
this audit was scoped to not touch `upgradecanary/`.

## Other files in this directory

- `common.py` — shared read-only loaders: final-run paths (original 10
  runs + the two Qwen3 thinking-mode-fix reruns), the project's functional
  score formula, and `recompute_record` (a parity-checked re-derivation of
  every metric straight from raw text + the unmodified evaluator/executor,
  used by every diagnostic below).
- `_parity_check.py` — self-test: confirms `recompute_record` reproduces
  all 9,000 stored scores across the 10 original runs with zero mismatches.
- `failure_breakdown.py`, `fault_mechanics.py`, `ceiling_effects.py`,
  `random_baseline_check.py`, `ranking_check.py`, `prefix_vs_postfix.py` —
  AUDIT.md's supporting analyses (sections D, E, I, J, K, H).
- `escape_check.py`/`.md`, `fault_rescore.py`/`.md`,
  `gate_vs_baseline.py`/`.md`, `intent_spotcheck.py`/`.csv`,
  `retry_prompt_check.py` — the first audit follow-up's deliverables
  (see `FOLLOWUP.md`).
- `qwen3_rerun.py`/`.md` — score tables, bootstrap CIs, failure breakdown,
  and gate verdicts for the two Qwen3 thinking-mode-fix reruns vs. the
  original ("pre-fix") run.
- `decisions_corrected.py`/`.md` — every downstream decision/gate/
  calibration analysis recomputed with the corrected Qwen3 runs in place
  of the original.
- `verdict_flips.py`/`.md` — one consolidated table of every gate-label
  flip found across this whole audit (applied fixes and still-diagnostic
  candidate fixes alike).
- `scratch/` — smoke-test config and run logs; not analysis output.
