"""One-off parity check: recompute_record(use_final_attempt=False, lenient=False,
strip_think=False) must exactly reproduce every stored metric. Not part of
the deliverables; just a self-test for the recompute engine in common.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FINAL_RUNS, load_parsed, load_raw, recompute_record, task_lookup  # noqa: E402


def main() -> None:
    for suite, model in FINAL_RUNS:
        tasks = task_lookup(suite)
        recs = load_parsed(suite, model)
        raw = load_raw(suite, model)
        mismatches = 0
        checked = 0
        for key, prec in recs.items():
            rrow = raw.get((prec["task_id"], prec["condition"], prec["trial_index"]))
            if rrow is None:
                continue
            final_m, _ = recompute_record(tasks, prec, rrow)
            checked += 1
            for mk in ("parse_ok", "tool_name_ok", "args_intent_match", "args_valid_under_drift", "executor_ok", "score"):
                if final_m[mk] != prec["metrics"][mk]:
                    mismatches += 1
                    if mismatches <= 3:
                        print(f"MISMATCH {suite} {model} {key} {mk}: recomputed={final_m[mk]} stored={prec['metrics'][mk]}")
                    break
        print(f"{suite:9} {model:12}: checked={checked:4} mismatches={mismatches}")


if __name__ == "__main__":
    main()
