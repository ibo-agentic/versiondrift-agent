# D-protocol health check (2026-10-05)

Pure diagnostics on `results_v2/D/`'s 48 real runs — **no upgrade verdicts
or pair differences computed here**, per instruction. Full per-run data
read directly from each run's `raw_outputs.jsonl`/`parsed_results.jsonl`/
`run_manifest.json` via `scripts/d_health_check.py`.

## 1. The disk-fill incident: timestamps, scope, and the rerun

**(a) Why `phi3_mini/bfcl_multiple`'s timestamp (22:35:52Z) is out of order,
and the ~26-minute gap before `qwen2`.**

Exact sequence, from `results_v2/real_run_progress.log`:

```
21:23:43Z  phi3_mini/bfcl_simple OK (run 8/48) -> triggers the every-8-runs backup
21:23:43Z  Backing up results_v2/ -> run8.zip ...
21:49:49Z  BACKUP FAILED: RuntimeError: File size too large, try using force_zip64
21:49:49Z  phi3_mini/bfcl_multiple launching ...
21:49:49Z  phi3_mini/bfcl_multiple FAILED (exit 1, status=None)   <- instant failure
21:49:49Z  qwen2/synthetic launching ...
21:57:44Z  qwen2/synthetic OK                                      <- succeeds anyway
   ... qwen2 (3/3), llama31/synthetic all complete normally ...
22:35:14Z  (manual validation backup(12) run while fixing the bug)
22:35:51Z  Orchestrator relaunched -> resumes, retries phi3_mini/bfcl_multiple
22:35:52Z  phi3_mini/bfcl_multiple succeeds this time (run_id timestamp here)
```

The **25-26 minute gap before `qwen2`** (21:23:43 → 21:49:49) is entirely
the runaway backup attempt itself — not model/inference time. A bug in
the backup function (fixed same day; see commit `6cd4be5`'s follow-up)
staged the zip archive *inside* `results_v2/` while also zipping
`results_v2/` as the archive root, so the growing zip file swept itself
up recursively. It grew to 47 GB before `zipfile` raised
`RuntimeError: File size too large, try using force_zip64` — that 26
minutes is the time spent writing those 47 GB before the error surfaced.

**`phi3_mini/bfcl_multiple`'s out-of-order timestamp** is simply this:
its first, in-order attempt (which would have run right after
`phi3_mini/bfcl_simple`, before `qwen2`) died **instantly** (0 elapsed
seconds) the moment it launched, immediately after the backup failure —
consistent with the disk being full at that exact moment (see 1(b)). The
orchestrator's design does not retry a failed run within the same
process; it logs the failure and moves on to the next item in the fixed
model order. So `qwen2` (all 3 suites) and `llama31/synthetic` ran and
completed normally while `phi3_mini/bfcl_multiple` sat pending. It was
only picked up later, when the orchestrator was relaunched after the bug
was fixed — by which point `qwen2`/`llama31` had already finished. Hence
a run_id timestamp that's later than runs listed before it in the model
order: a genuine, explainable consequence of the retry mechanism, not a
data problem.

**(b) Which runs the disk-fill bug touched.**

Checked disk usage directly: the 47 GB leftover file sat on disk (fully
consuming the then-available space — `df -h` showed 609 MB free, i.e.
100% used, at the point I investigated) from **21:49:49Z until it was
manually deleted** during the investigation that followed. Runs that
executed during that window:

| Run | Outcome |
|---|---|
| `phi3_mini/bfcl_multiple` (1st attempt) | **Crashed instantly, zero output written** (no `_status.json`, nothing under its run_id). Cleanly retried after the fix — no partial/corrupt data left behind. |
| `qwen2/synthetic`, `qwen2/bfcl_simple`, `qwen2/bfcl_multiple` | Ran to completion and reported success **despite the full disk**. |
| `llama31/synthetic` | Same — ran to completion despite the full disk. |

Because the first attempt crashed with *zero* output rather than a
partial file, and because "completed successfully" is self-reported, I
did not just trust the summary — I re-read these 5 runs' actual
`raw_outputs.jsonl`/`parsed_results.jsonl`/`run_manifest.json`/
`summary.json` files directly and confirmed: **all 5 have exactly 900
well-formed JSON lines (or valid JSON for the non-jsonl files), zero
malformed lines, zero corruption.** Each run's actual output footprint is
only ~1-2 MB, small enough to apparently still fit in whatever sliver of
space remained even while the OS reported the disk as 100% used. No
other run executed during this window, so no other run is implicated.

**Was any run rerun? Same config and seed?** Only one: `phi3_mini/
bfcl_multiple`. Its config is generated fresh by `build_config()` in
`scripts/real_run_one.py` every time that (model, suite) pair is
invoked, as a pure function of `(model_key, gguf_path, suite, data_path)`
— all fixed, hardcoded inputs (`seed: 1234`, `trial_seeds: [1234, 1235,
1236]`, `trial_temperatures: [0.0, 0.7, 0.7]`, same model path). The
failed first attempt and the successful rerun therefore used an
**identical config and seed** by construction; there was no manual
edit between attempts. (The generated YAML file at `results_v2/
_generated_configs/phi3_mini__bfcl_multiple.yaml` only ever holds the
latest write, so the two attempts' files aren't both preserved to diff
directly — but since the generator is a pure function of unchanged
inputs, they could not have differed.)

## 2. Per-run metrics (all 48 runs)

Computed directly from each run's own `parsed_results.jsonl`/
`raw_outputs.jsonl` — not from `summary.json`'s own aggregates, as an
independent check. "Greedy" = `trial_index == 0` (temperature 0.0) only.
`fr_status_acc` and `fabrication_rate` use all 3 trials (fault_reporting
assigns the same fault per task across trials, so this is 3x the
statistical power on the same assignment). `fabrication_rate` is
computed only over records whose expected status is `"failed"` (the
rule's only fabrication-checked case; see `evaluator.evaluate_fault_reporting`).

| Model | Suite | Parse rate | Truncation | Greedy baseline acc | Greedy drift acc | Fault-report status acc | Fabrication rate (failure cases) |
|---|---|---|---|---|---|---|---|
| gemma2_2b | synthetic | 1.000 | 0.000 | 0.940 | 0.960 | 0.993 | 0.000 |
| gemma2_2b | bfcl_simple | 0.980 | 0.001 | 0.820 | 0.780 | 0.990 | 0.000 |
| gemma2_2b | bfcl_multiple | 0.978 | 0.000 | 0.850 | 0.740 | 1.000 | 0.000 |
| gemma3_4b | synthetic | 1.000 | 0.000 | 0.940 | 0.970 | 0.957 | 0.000 |
| gemma3_4b | bfcl_simple | 1.000 | 0.004 | 0.910 | 0.870 | 0.910 | 0.000 |
| gemma3_4b | bfcl_multiple | 0.997 | 0.001 | 0.960 | 0.820 | 0.967 | 0.000 |
| granite30 | synthetic | 1.000 | 0.001 | 1.000 | 0.820 | 0.927 | 0.000 |
| granite30 | bfcl_simple | 1.000 | 0.004 | 0.940 | 0.900 | 0.873 | 0.000 |
| granite30 | bfcl_multiple | 1.000 | 0.000 | 0.920 | 0.880 | 0.960 | 0.000 |
| granite31 | synthetic | 1.000 | 0.002 | 0.980 | 0.940 | 0.860 | 0.095 |
| granite31 | bfcl_simple | 1.000 | 0.002 | 0.960 | 0.950 | 0.900 | 0.040 |
| granite31 | bfcl_multiple | 1.000 | 0.001 | 0.990 | 0.910 | 0.917 | 0.067 |
| granite32 | synthetic | 1.000 | 0.004 | 0.980 | 0.950 | 0.900 | 0.058 |
| granite32 | bfcl_simple | 1.000 | 0.002 | 0.970 | 0.950 | 0.930 | 0.020 |
| granite32 | bfcl_multiple | 1.000 | 0.000 | 0.990 | 0.920 | 0.960 | 0.026 |
| llama3 | synthetic | 0.927 | 0.000 | 1.000 | 0.900 | 0.957 | 0.000 |
| llama3 | bfcl_simple | 0.945 | 0.001 | 0.890 | 0.850 | 0.883 | 0.000 |
| llama3 | bfcl_multiple | 0.933 | 0.000 | 0.940 | 0.840 | 0.930 | 0.000 |
| llama31 | synthetic | 1.000 | 0.001 | 1.000 | 0.900 | 0.887 | 0.016 |
| llama31 | bfcl_simple | 1.000 | 0.002 | 0.940 | 0.830 | 0.840 | 0.000 |
| llama31 | bfcl_multiple | 1.000 | 0.000 | 0.940 | 0.820 | 0.953 | 0.015 |
| mistral_v01 | synthetic | 1.000 | 0.000 | 1.000 | 1.000 | 0.880 | 0.021 |
| mistral_v01 | bfcl_simple | 0.970 | 0.003 | 0.900 | 0.680 | 0.903 | 0.007 |
| mistral_v01 | bfcl_multiple | 0.985 | 0.000 | 0.900 | 0.690 | 0.917 | 0.062 |
| mistral_v02 | synthetic | 0.973 | 0.000 | 0.960 | 0.830 | 0.950 | 0.000 |
| mistral_v02 | bfcl_simple | 0.947 | 0.006 | 0.740 | 0.580 | 0.907 | 0.000 |
| mistral_v02 | bfcl_multiple | 0.905 | 0.001 | 0.780 | 0.580 | 0.880 | 0.000 |
| mistral_v03 | synthetic | 1.000 | 0.003 | 0.970 | 0.910 | 0.930 | 0.000 |
| mistral_v03 | bfcl_simple | 1.000 | 0.004 | 0.920 | 0.780 | 0.903 | 0.000 |
| mistral_v03 | bfcl_multiple | 0.997 | 0.001 | 0.950 | 0.800 | 0.917 | 0.000 |
| phi35_mini | synthetic | 1.000 | **0.024** | 1.000 | 0.950 | 0.793 | 0.063 |
| phi35_mini | bfcl_simple | 1.000 | **0.056** | 0.960 | 0.940 | 0.727 | 0.100 |
| phi35_mini | bfcl_multiple | 1.000 | **0.062** | 0.960 | 0.910 | 0.727 | 0.195 |
| phi3_mini | synthetic | 1.000 | 0.007 | 0.960 | 0.950 | 0.893 | 0.000 |
| phi3_mini | bfcl_simple | 1.000 | 0.000 | 0.930 | 0.850 | 0.780 | 0.000 |
| phi3_mini | bfcl_multiple | 0.995 | 0.000 | 0.920 | 0.820 | 0.893 | 0.000 |
| phi4_mini | synthetic | 1.000 | 0.000 | 1.000 | 0.940 | 0.850 | 0.127 |
| phi4_mini | bfcl_simple | 1.000 | 0.001 | 0.910 | 0.940 | 0.807 | 0.040 |
| phi4_mini | bfcl_multiple | 1.000 | 0.003 | 0.930 | 0.870 | 0.897 | 0.046 |
| qwen2 | synthetic | 1.000 | 0.000 | 1.000 | 0.780 | **0.653** | **0.275** |
| qwen2 | bfcl_simple | 1.000 | 0.000 | 0.930 | 0.880 | **0.630** | **0.147** |
| qwen2 | bfcl_multiple | 1.000 | 0.000 | 0.980 | 0.860 | **0.697** | **0.215** |
| qwen25 | synthetic | 1.000 | 0.000 | 1.000 | 0.930 | 0.867 | 0.095 |
| qwen25 | bfcl_simple | 1.000 | 0.000 | 0.960 | 0.940 | 0.810 | 0.000 |
| qwen25 | bfcl_multiple | 1.000 | 0.000 | 0.940 | 0.940 | 0.880 | 0.000 |
| qwen3 | synthetic | 0.948 | **0.123** | 0.990 | 0.900 | 0.733 | 0.053 |
| qwen3 | bfcl_simple | 0.688 | **0.378** | 0.770 | 0.570 | 0.493 | 0.287 |
| qwen3 | bfcl_multiple | **0.418** | **0.546** | 0.500 | 0.240 | 0.540 | 0.297 |

## 3. Flags

**Parse rate < 50%:**
- `qwen3/bfcl_multiple`: **0.418**. Consistent with the thinking-budget
  effect already identified in `smoke_report.md` (Problem 2, decision:
  leave D as-is) — `bfcl_multiple` has the longest prompts of the three
  suites, leaving the least of the 256-token budget for Qwen3's
  `<think>` block to finish before the real answer, at full 100-task
  scale this now reaches below 50% parse on the worst suite. Not a new
  problem; this is the same accepted tradeoff, now quantified precisely.

**Truncation > 2%:**
- `qwen3`: 12.3% (synthetic), 37.8% (bfcl_simple), **54.6%** (bfcl_multiple).
- `phi35_mini`: 2.4% (synthetic), 5.6% (bfcl_simple), 6.2% (bfcl_multiple).
  This is new information beyond the smoke test (which only sampled 5
  tasks/suite and saw ~9% on two suites) — at full scale it's lower and
  more suite-differentiated, but still consistently over the 2% line on
  all three suites for this one model. Not flagged or decided on before
  now; worth a decision alongside Qwen3's if the budget question is
  revisited.

**Accuracy of exactly 0 or 1 on a non-saturated (BFCL) suite:** none
found. All BFCL-suite baseline/drift accuracies fall strictly between
0.24 and 0.99 — no ceiling or floor artifacts.

**Native chat template looking wrong:** none found.
`native_chat_template_found: true` for all 16 models (see Section 4),
and every model's `native_stop_tokens`/`native_model_wants_bos` are
family-appropriate (ChatML models: single `<|im_end|>`, no BOS;
Mistral: `</s>`, wants BOS; Llama-3: both `<|end_of_text|>` and
`<|eot_id|>`; Llama-3.1: a single entry because its eos/eot tokens
dedup to the same text in this GGUF — expected per
`build_native_stop_list`'s own documented dedup behavior, not an error;
Granite: `<|end_of_text|>` only, no BOS; Phi-3/3.5-mini: both
`<|endoftext|>`/`<|end|>`; Phi-4-mini: `<|endoftext|>` only, no BOS;
Gemma: `<eos>`/`<end_of_turn>`, wants BOS). **Caveat**: this run (unlike
the smoke tests) did not instrument a per-record "exactly one BOS token
at the actual rendered prompt" check — only the resolved
config-level flags were available here, which match the smoke test's
empirically-verified findings for the same models. A fresh per-record
BOS check was not re-run against these specific 48 runs' raw prompts.

**Beyond the three checklist items — one more pattern worth flagging:**
`qwen2`'s fabrication rate (14.7%-27.5%) and fault-report status
accuracy (63.0%-69.7%) stand out sharply from every other model (next
highest fabrication rate is phi35_mini's 19.5% on one suite only; every
other model is at or near 0%, and every other model's status accuracy is
≥0.78). This matches and confirms, at full 100-task scale, the exact
qwen2 pattern already classified in `smoke_report.md`: it reports
`"status": "ok"` regardless of the actual injected fault and invents a
plausible-looking numeric answer. Not new, but now confirmed as a
consistent, full-scale finding rather than a 5-task sample.

## 4. run_manifest.json config consistency

Checked every one of the 48 `run_manifest.json`'s `run_factors` and
`model_backend` fields. **Exactly one distinct configuration signature
across all 48 runs**: `n_ctx=4096`, `max_tokens=256`, `chat_wrapping=
native`, `constrained_decoding=off`, `thinking=default` (D's own
per-model-default behavior — confirmed this resolves to Qwen3's
documented on-by-default thinking, not an override), and identical
sampling defaults on every run (`top_p=0.95, top_k=40, min_p=0.05,
repeat_penalty=1.0` — "shared" sampling, not overridden anywhere).
`native_chat_template_found: true` for all 16 models. No stray config
drift anywhere in the 48 runs.

## 5. Backup verification and SHA-256 manifest

**Latest OneDrive zip** (`results_v2_backup_2026-10-05_run48.zip`,
copied at `10:03:36Z`, i.e. right after the 48th run completed):
opened and listed directly — **all 48 model/suite run folders are
present**, none missing.

**SHA-256 manifest of every file under `results_v2/D/`**: 240 files (48
runs x 5 files each: `raw_outputs.jsonl`, `parsed_results.jsonl`,
`run_manifest.json`, `summary.json`, `_status.json`), written to
`analysis/plan/D_sha256_manifest.txt` (one `<sha256>  <path>` line per
file, generated by `scripts/d_health_check.py`).
