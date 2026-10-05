# F2 (Qwen3 thinking off) run report (2026-10-05)

Qwen3 only, all 3 suites, full size (900 records each). No verdicts, no comparison to D yet -- record-keeping only, per instruction.

## Method: the chat template's own `enable_thinking=false` switch

Confirmed directly against Qwen3's actual embedded `tokenizer.chat_template`
(not assumed from documentation) before running anything: the template
contains

```
{%- if add_generation_prompt %}
    {{- '<|im_start|>assistant\n' }}
    {%- if enable_thinking is defined and enable_thinking is false %}
        {{- '<think>\n\n</think>\n\n' }}
    {%- endif %}
{%- endif %}
```

i.e. when `enable_thinking` is passed as the literal boolean `False`, the
template pre-fills an **empty** `<think>\n\n</think>\n\n` block right
after the assistant turn opens, so the model continues straight to the
answer instead of actually reasoning. This project's existing
`model.thinking: "off"` config key (in `upgradecanary/model/
llama_cpp_client.py`) already maps to exactly this: it passes
`enable_thinking=False` into the native Jinja template render call. No
new mechanism was built -- F2 just sets this existing, now-confirmed-correct
switch. Everything else is byte-for-byte the same D config (`n_ctx=4096`,
`max_tokens=256`, `prompt_format=shared`, strict parsing, same sampling,
seed 1234, strict intent rule).

**Quick 5-task/suite verification (before the full runs)**: 135 records
across all 3 suites, zero `<think>` tags anywhere in the raw output,
zero truncation. Thinking is genuinely off, confirmed empirically, not
assumed -- proceeded to the full runs.

**Runs completed: 3/3**
**Total elapsed time: 32.1 minutes**
**Errors: 0**

| Suite | Records | Parse rate | Truncation rate | Greedy baseline acc | Seconds |
|---|---|---|---|---|---|
| synthetic | 900 | 1.000 | 0.000 | 1.000 | 494 |
| bfcl_simple | 900 | 1.000 | 0.000 | 0.970 | 693 |
| bfcl_multiple | 900 | 1.000 | 0.000 | 0.970 | 737 |

## run_manifest.json diff vs. D (all 3 suites)

Compared every field under `run_factors` and `model_backend` directly.
**Exactly one difference, identical across all 3 suites:**

```
run_factors.F2_thinking:    D = 'default'   F2 = 'off'
model_backend.thinking:     D = 'default'   F2 = 'off'
```

No other field differs (`n_ctx`, `max_tokens`, `chat_wrapping`,
`native_chat_template_found`, `native_stop_tokens`,
`native_model_wants_bos`, every sampling default, `prompt_format`,
`constrained_decoding`) -- confirmed identical to D on all 3 suites.

## Backup

Disk space checked before backing up (43.5 GB free, 0.10 GB source --
comfortably safe). Staged in a system temp directory, never inside
`results_v2/` itself (the exact mistake found and fixed during the
D-protocol runs). Copied to `C:\Users\Ibo\OneDrive\upgradecanary_backups\
results_v2_backup_2026-10-05_F2.zip` (4.2 MB).