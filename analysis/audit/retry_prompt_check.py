"""Follow-up to AUDIT.md E13 / escape_check.md: does the retry PROMPT itself
contain the literal sequence "\\_" (which would make this harness-caused),
or does the model introduce it on its own in its retry completion (which
would make this model-caused)?

Read-only. No code or config changes. Reconstructs the exact retry prompt
deterministically from existing logs:
  retry_prompt = prompt + "\nYour previous tool call failed: {feedback}\n"
                        + "Provide a corrected JSON answer:"
  (upgradecanary/runner.py:182-186, unchanged)
then applies the model's prompt_template (read verbatim from the relevant
config, not re-derived) to get the exact wrapped text sent to the model.
`prompt` (unwrapped) and `feedback` (= exec_result["first_attempt"]["error"]["message"])
are both already stored in existing logs; nothing is run or guessed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FINAL_RUNS, load_parsed, load_raw  # noqa: E402

# Verbatim from configs/*.yaml (grepped, not retyped from memory) -- read-only.
TEMPLATES = {
    "Mistral v0.1": "[INST]\n{prompt}\n[/INST]",
    "Mistral v0.2": "[INST]\n{prompt}\n[/INST]",
    "Mistral v0.3": "[INST]\n{prompt}\n[/INST]",
    "Qwen2.5": "<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant",
    "Qwen3": "<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant",
}

NEEDLE = "\\_"  # literal two-character sequence: backslash then underscore


def build_retry_prompt(base_prompt: str, feedback: str) -> str:
    return base_prompt + f"\nYour previous tool call failed: {feedback}\n" + "Provide a corrected JSON answer:"


def retried_records(suite: str, model: str):
    recs = load_parsed(suite, model)
    raw = load_raw(suite, model)
    out = []
    for key, prec in recs.items():
        if prec["condition"] != "runtime_fault":
            continue
        exec_result = prec["exec_result"]
        if not isinstance(exec_result, dict) or "first_attempt" not in exec_result:
            continue  # no retry happened for this record
        rrow = raw.get((prec["task_id"], prec["condition"], prec["trial_index"]))
        if rrow is None or rrow.get("retry_raw_output") is None:
            continue
        feedback = exec_result["first_attempt"].get("error", {}).get("message", "tool call failed")
        base_prompt = rrow["prompt"]
        retry_prompt_unwrapped = build_retry_prompt(base_prompt, feedback)
        wrapped = TEMPLATES[model].format(prompt=retry_prompt_unwrapped)
        out.append((key, prec, rrow, wrapped))
    return out


def main() -> None:
    # --- Part A: 3 concrete examples, Mistral v0.2 synthetic, escape-failure records ---
    print("=" * 100)
    print("PART A: 3 full wrapped retry prompts, Mistral v0.2 synthetic runtime_fault,")
    print("        escape-failure records (71-record bucket from escape_check.md)")
    print("=" * 100)
    shown = 0
    for key, prec, rrow, wrapped in retried_records("synthetic", "Mistral v0.2"):
        retry_out = rrow.get("retry_raw_output", "") or ""
        if "\\_" not in retry_out:
            continue  # this is one of the 71 only if the retry OUTPUT has the artifact
        if shown >= 3:
            break
        shown += 1
        print(f"\n--- record {shown}: task={prec['task_id']} trial={prec['trial_index']} ---")
        print("FULL WRAPPED RETRY PROMPT (exact text sent to the model):")
        print(wrapped)
        print(f"\ncontains literal '\\\\_' in the PROMPT? {NEEDLE in wrapped}")
        print(f"RETRY RAW OUTPUT: {retry_out!r}")

    # --- Part B: all models, both suites: does the retry PROMPT contain \_ ? ---
    print("\n" + "=" * 100)
    print("PART B: all retried runtime_fault records, all models, both suites")
    print("=" * 100)
    print(f"{'suite':9} {'model':12} {'retried_n':9} {'prompt_has_\\\\_':15} {'output_has_\\\\_':15} {'both':6}")
    totals = {"prompt": 0, "output": 0, "both": 0, "retried": 0}
    for suite, model in FINAL_RUNS:
        records = retried_records(suite, model)
        n = len(records)
        prompt_hits = 0
        output_hits = 0
        both_hits = 0
        for key, prec, rrow, wrapped in records:
            p_hit = NEEDLE in wrapped
            o_hit = NEEDLE in (rrow.get("retry_raw_output", "") or "")
            prompt_hits += p_hit
            output_hits += o_hit
            both_hits += p_hit and o_hit
        print(f"{suite:9} {model:12} {n:9} {prompt_hits:15} {output_hits:15} {both_hits:6}")
        totals["retried"] += n
        totals["prompt"] += prompt_hits
        totals["output"] += output_hits
        totals["both"] += both_hits

    print(f"\nTOTALS: retried={totals['retried']} prompt_has_escape={totals['prompt']} "
          f"output_has_escape={totals['output']} both={totals['both']}")

    print("\n--- verdict ---")
    if totals["prompt"] == 0:
        print("HARNESS-CAUSED: NO. The retry prompt (feedback message + base prompt,")
        print("exactly as sent to the model after template wrapping) never contains")
        print("the literal sequence '\\_' in any of the", totals["retried"], "retried records")
        print("across all 10 runs. The artifact is introduced by the MODEL during its")
        print("retry completion, not copied from anything in the prompt it was given.")
        print("=> MODEL-CAUSED.")
    else:
        print(f"The retry prompt itself contains '\\_' in {totals['prompt']} records -- at least")
        print("partially HARNESS-CAUSED (the model may be echoing something already in its input).")


if __name__ == "__main__":
    main()
