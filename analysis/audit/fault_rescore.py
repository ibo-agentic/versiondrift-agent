"""AUDIT follow-up item 3: fault scoring fix, recomputed from existing logs.

Read-only. For every runtime_fault record (all 10 final runs):
  - first_try_score: all five components scored on the FIRST attempt only
    (ignores any retry entirely).
  - final_score: all five components scored consistently on the FINAL
    attempt (the retry's own parsed call + its own exec result, if a retry
    happened -- not the original mixed first-attempt-metrics/retry-exec_ok
    scoring). This is the "fault scoring fix" requested in the follow-up.
  - recovered   = first_try_score == 0 and final_score == 1
  - broken_by_retry = first_try_score == 1 and final_score == 0

stale_result is reported separately and excluded from the main
"runtime_fault" aggregate, since apply_fault() always returns ok=True for it
(see upgradecanary/perturbations/runtime_faults.py:72-79) -- it cannot fail
by construction and carries no fault-specific signal.

Per AUDIT.md's recommendation, the four genuinely-retried fault types
(timeout, tool_exception, empty_result, partial_result) are additionally
reported under the label "retry_after_tool_failure" pending a real
fault-detection test; "runtime_fault" is kept as the raw label since that is
still the condition name in every config/data file (see FOLLOWUP.md for why
the underlying condition identifier itself was not renamed).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FINAL_RUNS, load_parsed, load_raw, recompute_record, task_lookup  # noqa: E402

STALE = "stale_result"
RETRY_TYPES = ("timeout", "tool_exception", "empty_result", "partial_result")


def main() -> None:
    lines: list[str] = []
    lines.append("# Fault rescore: first-try vs final-attempt-consistent scoring\n")
    lines.append(
        "Read-only, recomputed from existing logs (no reruns). See "
        "`upgradecanary/parsing.py`/`analysis/audit/common.py` "
        "(`recompute_record`, parity-checked against stored scores in "
        "`_parity_check.py`: 0 mismatches across all 9,000 records x 10 runs).\n"
    )
    lines.append(
        "**Terminology note (per AUDIT.md E11):** this file reports the "
        "`timeout`/`tool_exception`/`empty_result`/`partial_result` fault "
        "types under the label **retry_after_tool_failure**, since what is "
        "actually measured is \"does a second generation, prompted with the "
        "first failure's error message, produce a correct call\" -- not "
        "fault *detection* or *handling* in any deeper sense. `stale_result` "
        "is reported separately: `apply_fault` always returns `ok: True` "
        "for it, so it cannot fail by construction and is excluded from the "
        "main aggregate below.\n"
    )

    lines.append("## Per model x suite: first-try vs final-attempt score, recovered / broken_by_retry\n")
    lines.append(
        "| suite | model | n (excl. stale) | first_try mean | final mean "
        "(fixed, consistent) | final mean (original/mixed) | recovered | broken_by_retry |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")

    stale_rows = []
    main_rows = []

    for suite, model in FINAL_RUNS:
        tasks = task_lookup(suite)
        recs = load_parsed(suite, model)
        raw = load_raw(suite, model)
        fault_keys = [k for k, p in recs.items() if p["condition"] == "runtime_fault"]

        for label, type_filter in (("main (excl. stale_result)", RETRY_TYPES), ("stale_result only", (STALE,))):
            keys = [k for k in fault_keys if (recs[k].get("fault") or {}).get("type") in type_filter]
            n = len(keys)
            if n == 0:
                continue
            first_scores, final_fixed_scores, final_mixed_scores = [], [], []
            recovered_n = broken_n = 0
            for key in keys:
                prec = recs[key]
                rrow = raw.get((prec["task_id"], prec["condition"], prec["trial_index"]))
                final_fixed, first = recompute_record(tasks, prec, rrow, use_final_attempt=True)
                final_mixed, _ = recompute_record(tasks, prec, rrow, use_final_attempt=False)
                first_scores.append(first["score"])
                final_fixed_scores.append(final_fixed["score"])
                final_mixed_scores.append(final_mixed["score"])
                if first["score"] == 0.0 and final_fixed["score"] == 1.0:
                    recovered_n += 1
                elif first["score"] == 1.0 and final_fixed["score"] == 0.0:
                    broken_n += 1
            row = (
                suite, model, n,
                sum(first_scores) / n, sum(final_fixed_scores) / n, sum(final_mixed_scores) / n,
                recovered_n, broken_n,
            )
            if type_filter == (STALE,):
                stale_rows.append(row)
            else:
                main_rows.append(row)
                lines.append(
                    f"| {suite} | {model} | {n} | {row[3]:.3f} | {row[4]:.3f} | {row[5]:.3f} | {recovered_n} | {broken_n} |"
                )

    lines.append("\n## stale_result, reported separately (cannot fail by construction)\n")
    lines.append("| suite | model | n | first_try mean | final mean | recovered | broken_by_retry |")
    lines.append("|---|---|---|---|---|---|---|")
    for suite, model, n, first_m, final_m, _mixed, rec, brk in stale_rows:
        lines.append(f"| {suite} | {model} | {n} | {first_m:.3f} | {final_m:.3f} | {rec} | {brk} |")

    lines.append(
        "\n## Reading this table\n\n"
        "- **first_try mean**: score if the retry never happened (fault-forced "
        "first-attempt failure counts as a real failure). This is the closest "
        "thing to \"did the model's own call survive contact with the fault\" "
        "for the four retryable types, and it is near-zero for all of them by "
        "construction (apply_fault always fails the first attempt when the "
        "original call was otherwise correct).\n"
        "- **final mean (fixed, consistent)**: all five components recomputed "
        "on the actual final attempt (the retry's own parsed call + exec, "
        "when a retry happened) -- the corrected scoring this follow-up asked "
        "for.\n"
        "- **final mean (original/mixed)**: the number currently published "
        "(docs/results_summary.md), included for comparison -- computed with "
        "four of five metrics taken from the first attempt and only "
        "`executor_ok` from the retry (see AUDIT.md E10).\n"
        "- A difference between the 'fixed' and 'mixed' columns means the "
        "retry's OWN parsed call differs from the first attempt's in a way "
        "that matters for `tool_name_ok`/`args_intent_match`/"
        "`args_valid_under_drift` (not just `executor_ok`) -- e.g. a retry "
        "that changes its mind about an argument, or one broken by an "
        "escape artifact (see escape_check.md), which the mixed scoring "
        "would not have caught since it only looks at the retry's final "
        "`ok` flag, not its restated arguments.\n"
        "- **stale_result** mean scores track each model's own baseline-"
        "level correctness almost exactly, confirming it carries no "
        "fault-specific signal (AUDIT.md E11) and should not be pooled into "
        "a 'robustness under faults' claim.\n"
    )

    out_path = Path(__file__).parent / "fault_rescore.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
