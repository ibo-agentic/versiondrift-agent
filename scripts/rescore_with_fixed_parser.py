"""2026-10-07 parser follow-up: rescore an existing run's raw_outputs.jsonl
with the CURRENT upgradecanary.parsing parser (post Granite-3.0
function_name_alias fix), without touching the model or re-generating any
text. Only baseline/schema_drift records are affected -- fault_reporting
uses extract_fault_report(), a separate function this fix never touched.

For each matching record, re-parses raw_output, rebuilds the exact schema
(base schema + stored drift) and re-runs the real evaluator.evaluate(), then
compares the new parse_ok/detected_format/score against what's already on
disk. Never writes anything unless --apply is given (and even then, only
parsed_results.jsonl + summary.json -- raw_outputs.jsonl, the ground truth,
is never touched).

Usage:
  python scripts/rescore_with_fixed_parser.py <run_dir> <suite> [--apply]

<run_dir> is the directory directly containing raw_outputs.jsonl and
parsed_results.jsonl (i.e. results_v2/<protocol>/<model>/<suite>/<run_id>/).
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.real_run_models import SUITES  # noqa: E402
from upgradecanary.evaluator import evaluate, summarize  # noqa: E402
from upgradecanary.parsing import extract_tool_call_with_format  # noqa: E402
from upgradecanary.perturbations.runtime_faults import Fault  # noqa: E402
from upgradecanary.perturbations.schema_drift import Drift, drifted_schema  # noqa: E402
from upgradecanary.runner import _safe_execute, task_base_schema  # noqa: E402
from upgradecanary.tasks import load_tasks  # noqa: E402
from upgradecanary.utils import read_jsonl, write_json, write_jsonl  # noqa: E402

_TOOL_CALL_CONDITIONS = {"baseline", "schema_drift"}


def rescore_run(run_dir: Path, suite: str) -> dict:
    tasks_by_id = {t.task_id: t for t in load_tasks(SUITES[suite])}
    raw_rows = read_jsonl(run_dir / "raw_outputs.jsonl")
    parsed_rows = read_jsonl(run_dir / "parsed_results.jsonl")
    assert len(raw_rows) == len(parsed_rows), f"{run_dir}: row count mismatch"

    diffs = []
    new_parsed_rows = []
    for raw_row, parsed_row in zip(raw_rows, parsed_rows):
        condition = parsed_row["condition"]
        if condition not in _TOOL_CALL_CONDITIONS:
            new_parsed_rows.append(parsed_row)
            continue

        task = tasks_by_id[parsed_row["task_id"]]
        drift = Drift(**parsed_row["drift"]) if parsed_row.get("drift") else None
        fault = Fault(**parsed_row["fault"]) if parsed_row.get("fault") else None
        base_schema = task_base_schema(task)
        schema = drifted_schema(base_schema, drift)
        strict = condition == "baseline"

        new_parsed, new_detected_format = extract_tool_call_with_format(raw_row["raw_output"])
        new_exec_result = _safe_execute(new_parsed, schema, drift, fault, strict, canonical_schema=base_schema)
        new_metrics = evaluate(
            condition, task.expected_call, new_parsed, new_exec_result, drift, fault,
            None, schema, strict, acceptable=task.acceptable,
        )

        old_parsed = parsed_row["parsed_call"]
        old_score = parsed_row["metrics"]["score"]
        if new_parsed != old_parsed or new_metrics["score"] != old_score:
            diffs.append({
                "task_id": task.task_id,
                "condition": condition,
                "trial_index": parsed_row["trial_index"],
                "old_parsed_call": old_parsed,
                "new_parsed_call": new_parsed,
                "old_detected_format": parsed_row.get("detected_format"),
                "new_detected_format": new_detected_format,
                "old_score": old_score,
                "new_score": new_metrics["score"],
            })

        new_row = dict(parsed_row)
        new_row["parsed_call"] = new_parsed
        new_row["detected_format"] = new_detected_format
        new_row["exec_result"] = new_exec_result
        new_row["metrics"] = new_metrics
        new_parsed_rows.append(new_row)

    return {
        "run_dir": str(run_dir),
        "num_records": len(parsed_rows),
        "num_diffs": len(diffs),
        "diffs": diffs,
        "new_parsed_rows": new_parsed_rows,
    }


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python scripts/rescore_with_fixed_parser.py <run_dir> <suite> [--apply]")
        return 2
    run_dir = Path(sys.argv[1])
    suite = sys.argv[2]
    apply = "--apply" in sys.argv[3:]

    result = rescore_run(run_dir, suite)
    print(f"{run_dir}: {result['num_records']} records, {result['num_diffs']} diffs")
    for d in result["diffs"]:
        print(f"  DIFF task={d['task_id']} cond={d['condition']} trial={d['trial_index']} "
              f"old_score={d['old_score']} new_score={d['new_score']} "
              f"old_fmt={d['old_detected_format']} new_fmt={d['new_detected_format']}")

    if apply:
        write_jsonl(run_dir / "parsed_results.jsonl", result["new_parsed_rows"])
        new_summary = summarize(result["new_parsed_rows"])
        old_summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        new_summary["run_id"] = old_summary.get("run_id")
        new_summary["model_provider"] = old_summary.get("model_provider")
        new_summary["num_trials"] = old_summary.get("num_trials")
        write_json(run_dir / "summary.json", new_summary)
        print(f"  APPLIED: parsed_results.jsonl + summary.json updated in {run_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
