"""F7/F8/F10 rescore logic on fake raw outputs. Tasks come from the repo's
task file (data/base_tasks.jsonl, read-only); all outputs go to tmp dirs.
"""

import hashlib
import json
from pathlib import Path

import pytest

from tests.fake_study import fake_config_dict
from upgradecanary.evaluator import evaluate
from upgradecanary.parsing import extract_tool_call_with_format
from upgradecanary.runner import _safe_execute, task_base_schema
from upgradecanary.tasks import load_tasks
from upgradecanary.utils import read_jsonl, write_jsonl
from vdanalysis.config import Config
from vdanalysis.loader import Store
from vdanalysis.rescore import rescore_lenient, rescore_relaxed_intent, rescore_tree, subsample_greedy

DATA = Path(__file__).resolve().parent.parent / "data" / "base_tasks.jsonl"


@pytest.fixture(scope="module")
def tasks():
    return {t.task_id: t for t in load_tasks(DATA)}


def strict_row(task, raw, trial):
    """Build a parsed row the way runner.run() does for a baseline record (strict parse)."""
    schema = task_base_schema(task)
    call, fmt = extract_tool_call_with_format(raw)
    ex = _safe_execute(call, schema, None, None, True, canonical_schema=schema)
    m = evaluate("baseline", task.expected_call, call, ex, None, None, None, schema, True, acceptable=task.acceptable)
    return {"task_id": task.task_id, "condition": "baseline", "trial_index": trial, "drift": None, "fault": None,
            "parsed_call": call, "detected_format": fmt, "exec_result": ex, "metrics": m}


def make_f7_inputs(tasks):
    t = tasks["task-021"]  # search_docs, query "vector index compaction"
    good = json.dumps(t.expected_call)
    compact = json.dumps(t.expected_call, separators=(",", ":"))
    escaped = compact.replace(" ", "\\ ", 1)  # "vector\ index compaction": invalid JSON escape
    tool_key = json.dumps({"tool": t.expected_call["name"], "arguments": t.expected_call["arguments"]})
    raws = [good, escaped, tool_key]
    parsed = [strict_row(t, r, i) for i, r in enumerate(raws)]
    raw_rows = [{"task_id": t.task_id, "condition": "baseline", "trial_index": i, "raw_output": r}
                for i, r in enumerate(raws)]
    return parsed, raw_rows


def test_f7_lenient_recovers_invalid_escape_only(tasks):
    parsed, raw_rows = make_f7_inputs(tasks)
    assert [p["metrics"]["score"] for p in parsed] == [1.0, 0.0, 0.0]
    new, diffs = rescore_lenient(parsed, raw_rows, tasks)
    assert [p["metrics"]["score"] for p in new] == [1.0, 1.0, 0.0]
    assert [d["trial_index"] for d in diffs] == [1]


def test_granite_tool_key_stays_unparsed_under_strict_and_lenient(tasks):
    parsed, raw_rows = make_f7_inputs(tasks)
    raw = raw_rows[2]["raw_output"]
    assert extract_tool_call_with_format(raw) == (None, None)
    assert extract_tool_call_with_format(raw, lenient=True) == (None, None)
    new, _ = rescore_lenient(parsed, raw_rows, tasks)
    assert new[2]["parsed_call"] is None and new[2]["metrics"]["parse_ok"] is False


def test_f7_rescores_fault_reporting_rows_with_lenient_extraction(tasks):
    fault = {"type": "timeout", "params": {}}
    raw = '{"status": "fail\\ed", "answer": null}'  # invalid escape inside the status string
    row = {"task_id": "task-021", "condition": "fault_reporting", "trial_index": 0, "drift": None, "fault": fault,
           "parsed_call": None, "exec_result": None,
           "metrics": {"parse_ok": False, "status_ok": False, "no_fabrication": True, "score": 0.0, "strict_score": 0.0}}
    new, diffs = rescore_lenient([row], [{"task_id": "task-021", "condition": "fault_reporting",
                                         "trial_index": 0, "raw_output": raw}], tasks)
    assert new[0]["metrics"]["score"] == 1.0 and len(diffs) == 1


def test_f8_relaxed_intent_changes_only_intent_and_score_derived_from_it(tasks):
    t = tasks["task-041"]  # convert_units 5 km -> mi
    call = {"name": "convert_units", "arguments": {"value": 5, "from_unit": "kilometers", "to_unit": "mi"}}
    base = {"parse_ok": True, "tool_name_ok": True, "args_exact": False, "args_intent_match": False,
            "args_valid_under_drift": True, "executor_ok": True, "recovered_after_fault": None, "score": 0.0}
    rows = [
        {"task_id": t.task_id, "condition": "baseline", "trial_index": 0, "drift": None, "fault": None,
         "parsed_call": call, "metrics": dict(base)},
        # wrong tool name: relaxed intent must not rescue it
        {"task_id": t.task_id, "condition": "baseline", "trial_index": 1, "drift": None, "fault": None,
         "parsed_call": call, "metrics": dict(base, tool_name_ok=False)},
        # already correct: untouched
        {"task_id": t.task_id, "condition": "baseline", "trial_index": 2, "drift": None, "fault": None,
         "parsed_call": t.expected_call, "metrics": dict(base, args_intent_match=True, score=1.0)},
    ]
    new, diffs = rescore_relaxed_intent(rows, tasks)
    assert [r["metrics"]["score"] for r in new] == [1.0, 0.0, 1.0]
    assert new[1]["metrics"]["args_intent_match"] is True  # intent relaxed, score still gated by name
    assert [d["trial_index"] for d in diffs] == [0]
    assert rows[0]["metrics"]["score"] == 0.0  # input not mutated


def test_f10_keeps_greedy_trial_only():
    rows = [{"task_id": "a", "condition": "baseline", "trial_index": i, "metrics": {}} for i in range(3)]
    kept, _ = subsample_greedy(rows)
    assert [r["trial_index"] for r in kept] == [0]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_tree_driver_writes_new_folder_loadable_by_analysis_and_leaves_source_alone(tmp_path, tasks):
    src_root = tmp_path / "src_results"
    run = src_root / "D" / "h_new" / "s1" / "run1"
    run.mkdir(parents=True)
    parsed, raw_rows = make_f7_inputs(tasks)
    write_jsonl(run / "parsed_results.jsonl", parsed)
    write_jsonl(run / "raw_outputs.jsonl", raw_rows)
    (run / "run_manifest.json").write_text(json.dumps({"run_id": "run1", "run_factors": {}}), encoding="utf-8")
    before = {p.name: _sha(p) for p in run.iterdir()}

    cfg_dict = fake_config_dict(src_root, rescored_root=tmp_path / "rescored")
    cfg_dict["protocols"].update({"F7": {"folder": "F7", "root": "rescored", "expected_records": 3},
                                  "F10": {"folder": "F10", "root": "rescored", "expected_records": 1}})
    cfg = Config(cfg_dict)
    log = rescore_tree(cfg, "F7", "D", tmp_path / "rescored", models=["h_new"], suites=["s1"],
                       tasks_loader=lambda s: tasks)
    assert log[0]["records"] == 3 and log[0]["diffs"] == 1
    rescore_tree(cfg, "F10", "D", tmp_path / "rescored", models=["h_new"], suites=["s1"], tasks_loader=lambda s: tasks)

    assert {p.name: _sha(p) for p in run.iterdir()} == before  # source untouched
    store = Store(cfg)
    f7 = store.get("F7", "h_new", "s1")
    assert sorted(v[0] for v in f7.keys.values()) == [0.0, 1.0, 1.0]
    assert f7.manifest["rescore"]["factor"] == "F7" and not f7.warnings
    f10 = store.get("F10", "h_new", "s1")
    assert len(f10) == 1 and not f10.warnings
    assert read_jsonl(next((tmp_path / "rescored" / "F7").rglob("rescore_diffs.jsonl")))[0]["new_score"] == 1.0


@pytest.mark.parametrize("bad", ["results", "results_smoke", "results_v2"])
def test_rescore_refuses_to_write_into_protected_folders(tmp_path, tasks, bad):
    cfg = Config(fake_config_dict(tmp_path))
    with pytest.raises(ValueError, match="protected"):
        rescore_tree(cfg, "F10", "D", tmp_path / bad / "out", models=["h_new"], suites=["s1"],
                     tasks_loader=lambda s: tasks)
