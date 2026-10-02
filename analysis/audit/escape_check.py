"""AUDIT follow-up item 1: strict vs lenient (invalid-escape-repaired) scoring.

Read-only; recomputes from existing results/*/{parsed_results,raw_outputs}.jsonl
using analysis/audit/common.py's recompute_record (parity-checked in
_parity_check.py). "Lenient" uses upgradecanary/parsing.py's new lenient=True
mode (added this follow-up, default OFF everywhere else) which retries
extraction after repairing invalid JSON backslash-escapes (e.g. "\\_" -> "_").
Because that repair step can only turn an unparseable string into a parseable
one (never the reverse -- see parsing.py docstring), any record whose score
flips between strict and lenient is, by construction, flipping solely because
of an escape repair.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FINAL_RUNS, load_parsed, load_raw, recompute_record, task_lookup  # noqa: E402

CONDITIONS = ["baseline", "schema_drift", "runtime_fault"]


def main() -> None:
    lines: list[str] = []
    lines.append("# Escape-check: strict vs lenient (invalid-escape-repaired) scoring\n")
    lines.append(
        "Read-only diagnostic. `lenient` retries JSON extraction after repairing "
        "invalid backslash-escapes (e.g. `\\_` -> `_`) via the new "
        "`extract_tool_call(..., lenient=True)` mode in `upgradecanary/parsing.py` "
        "(default `lenient=False` everywhere in production; this file never "
        "changes an existing score). The repair can only make an unparseable "
        "string parseable, never the reverse, so every strict->lenient score "
        "flip (always 0->1) is caused *solely* by an invalid-escape fix.\n"
    )

    # Q1 headline: Mistral v0.2 synthetic runtime_fault executor_failure bucket.
    tasks_syn = task_lookup("synthetic")
    recs = load_parsed("synthetic", "Mistral v0.2")
    raw = load_raw("synthetic", "Mistral v0.2")
    exec_fail_keys = []
    for key, prec in recs.items():
        if prec["condition"] != "runtime_fault":
            continue
        m = prec["metrics"]
        is_exec_fail = (
            m["parse_ok"] and m["tool_name_ok"] and m["args_intent_match"]
            and m["args_valid_under_drift"] and not m["executor_ok"]
        )
        if is_exec_fail:
            exec_fail_keys.append(key)

    escape_fixed = 0
    for key in exec_fail_keys:
        prec = recs[key]
        rrow = raw.get((prec["task_id"], prec["condition"], prec["trial_index"]))
        final_strict, _ = recompute_record(tasks_syn, prec, rrow, use_final_attempt=False, lenient=False)
        final_lenient, _ = recompute_record(tasks_syn, prec, rrow, use_final_attempt=False, lenient=True)
        if final_strict["score"] == 0.0 and final_lenient["score"] == 1.0:
            escape_fixed += 1

    lines.append("## Headline number (Q1)\n")
    lines.append(
        f"Of the **{len(exec_fail_keys)}** `executor_failure`-bucket records in "
        f"Mistral v0.2 synthetic `runtime_fault` (first attempt intent-matched "
        f"and schema-valid, but final `executor_ok=False`), **{escape_fixed}** "
        f"flip to a passing score under lenient (escape-repaired) retry parsing "
        f"-- i.e. **{escape_fixed}/{len(exec_fail_keys)}** fail *only* because of "
        f"an invalid JSON escape in the retry output "
        f"({100*escape_fixed/len(exec_fail_keys) if exec_fail_keys else 0:.1f}%).\n"
    )

    # General table: strict vs lenient score, every model x suite x condition.
    lines.append("## Strict vs lenient score, every model x suite x condition\n")
    lines.append("| suite | model | condition | n | strict mean | lenient mean | records flipped 0->1 |")
    lines.append("|---|---|---|---|---|---|---|")

    total_flips_by_model: dict[tuple, int] = {}
    for suite, model in FINAL_RUNS:
        tasks = task_lookup(suite)
        recs = load_parsed(suite, model)
        raw = load_raw(suite, model)
        for cond in CONDITIONS:
            keys = [k for k, p in recs.items() if p["condition"] == cond]
            n = len(keys)
            strict_scores = []
            lenient_scores = []
            flips = 0
            for key in keys:
                prec = recs[key]
                rrow = raw.get((prec["task_id"], prec["condition"], prec["trial_index"]))
                fs, _ = recompute_record(tasks, prec, rrow, use_final_attempt=False, lenient=False)
                fl, _ = recompute_record(tasks, prec, rrow, use_final_attempt=False, lenient=True)
                strict_scores.append(fs["score"])
                lenient_scores.append(fl["score"])
                if fs["score"] == 0.0 and fl["score"] == 1.0:
                    flips += 1
                elif fs["score"] != fl["score"]:
                    # Should never happen given the repair is monotonic; flag if it does.
                    flips += -1000  # sentinel to make an unexpected direction obvious
            strict_mean = sum(strict_scores) / n if n else 0.0
            lenient_mean = sum(lenient_scores) / n if n else 0.0
            lines.append(
                f"| {suite} | {model} | {cond} | {n} | {strict_mean:.3f} | {lenient_mean:.3f} | {flips} |"
            )
            total_flips_by_model[(suite, model)] = total_flips_by_model.get((suite, model), 0) + max(flips, 0)

    lines.append("\n## Total escape-only flips per model (all conditions pooled)\n")
    lines.append("| suite | model | total records flipped 0->1 by escape repair |")
    lines.append("|---|---|---|")
    for (suite, model), n in total_flips_by_model.items():
        lines.append(f"| {suite} | {model} | {n} |")

    lines.append(
        "\n## Interpretation\n\n"
        "Strict scoring remains the project's official metric; nothing above "
        "changes any published number. This table exists to size the "
        "'spurious backslash escape' failure mode identified in `AUDIT.md` "
        "section E13 (Mistral v0.2 retry outputs like `get\\_weather`). Where "
        "the flip count for a model/condition is non-trivial, it suggests a "
        "fraction of that model's measured 'failures' are a retry-prompt-"
        "induced formatting quirk rather than a semantic or robustness "
        "failure -- the same caution AUDIT.md already raises for Qwen3's "
        "thinking-mode truncation, but via a different mechanism.\n"
    )

    out_path = Path(__file__).parent / "escape_check.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"headline: {escape_fixed}/{len(exec_fail_keys)} Mistral v0.2 synthetic executor_failure records fixed by escape repair")


if __name__ == "__main__":
    main()
