"""BFCL "multiple" category (PLAN.md 10.1 item 3). Hermetic tests -- small
inline BFCL-shaped fixtures, not dependent on the external/gorilla checkout
(which is gitignored and may not be present everywhere this suite runs).
"""

from __future__ import annotations

from upgradecanary.bfcl import convert_multiple, find_correct_function, is_eligible_multiple
from upgradecanary.runner import build_prompt, task_base_schema
from upgradecanary.tasks import load_tasks
from upgradecanary.perturbations.schema_drift import apply as apply_drift, drifted_schema
import random

TRIANGLE_FN = {
    "name": "triangle_properties.get",
    "description": "Retrieve dimensions of a triangle given its three sides.",
    "parameters": {
        "type": "dict",
        "properties": {
            "side1": {"type": "integer", "description": "First side."},
            "side2": {"type": "integer", "description": "Second side."},
            "side3": {"type": "integer", "description": "Third side."},
        },
        "required": ["side1", "side2", "side3"],
    },
}
CIRCLE_FN = {
    "name": "circle_properties.get",
    "description": "Retrieve dimensions of a circle given its radius.",
    "parameters": {
        "type": "dict",
        "properties": {"radius": {"type": "integer", "description": "The radius."}},
        "required": ["radius"],
    },
}

RECORD = {
    "id": "multiple_test_0",
    "question": [[{"role": "user", "content": "What are the properties of a triangle with sides 5, 4 and 3?"}]],
    "function": [TRIANGLE_FN, CIRCLE_FN],
}
ANSWER = {
    "id": "multiple_test_0",
    "ground_truth": [{"triangle_properties.get": {"side1": [5], "side2": [4], "side3": [3]}}],
}


def test_find_correct_function_matches_by_name_not_index():
    fn = find_correct_function([CIRCLE_FN, TRIANGLE_FN], "triangle_properties.get")
    assert fn is TRIANGLE_FN  # correct even though it's NOT functions[0] here


def test_find_correct_function_returns_none_when_missing():
    assert find_correct_function([CIRCLE_FN], "triangle_properties.get") is None


def test_is_eligible_multiple_requires_at_least_two_functions():
    record = dict(RECORD, function=[TRIANGLE_FN])
    ok, reason = is_eligible_multiple(record, ANSWER)
    assert not ok
    assert reason == "not_multiple"


def test_is_eligible_multiple_accepts_a_well_formed_record_with_enough_budget():
    ok, reason = is_eligible_multiple(RECORD, ANSWER, max_prompt_chars=3500)
    assert ok, reason


def test_is_eligible_multiple_rejects_too_long_at_default_budget():
    # The default (1200, matching simple_python) is the documented
    # categorical mismatch for "multiple" -- see ENGINEERING_NOTES.md.
    ok, reason = is_eligible_multiple(RECORD, ANSWER)  # default max_prompt_chars=1200
    assert not ok
    assert reason == "prompt_too_long"


def test_convert_multiple_resolves_correct_tool_and_keeps_all_candidates():
    task = convert_multiple(RECORD, ANSWER)
    assert task["tool"] == "triangle_properties.get"
    assert task["expected_call"] == {
        "name": "triangle_properties.get",
        "arguments": {"side1": 5, "side2": 4, "side3": 3},
    }
    assert len(task["candidate_schemas"]) == 2
    assert {c["name"] for c in task["candidate_schemas"]} == {"triangle_properties.get", "circle_properties.get"}
    assert task["tool_schema"]["name"] == "triangle_properties.get"


def test_convert_multiple_works_when_correct_tool_is_not_first_candidate():
    record = dict(RECORD, function=[CIRCLE_FN, TRIANGLE_FN])  # order swapped
    task = convert_multiple(record, ANSWER)
    assert task["tool"] == "triangle_properties.get"  # still correct, not circle (index 0)


def test_drift_applies_only_to_correct_tool_distractor_renders_verbatim():
    """End-to-end (mock-free, no model): load a converted task, apply a
    drift, and confirm the rendered prompt drifts the correct tool only."""
    record = dict(RECORD)
    task_dict = convert_multiple(record, ANSWER)
    import json
    import tempfile
    import os

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "t.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(task_dict) + "\n")
    task = load_tasks(path)[0]

    base_schema = task_base_schema(task)
    rng = random.Random(1234)
    drift = apply_drift(task.tool, ["unexpected_field"], rng, None, schema=base_schema)
    schema = drifted_schema(base_schema, drift)
    prompt = build_prompt(task, schema, prompt_format="shared")

    assert drift is not None
    assert drift.tool == "triangle_properties.get"
    # The correct tool's rendered doc gained the drift's new field...
    assert "verbose" in prompt
    # ...but circle_properties.get's block must be untouched: find its
    # properties list and confirm "verbose" never appears inside it.
    circle_start = prompt.index('"circle_properties.get"')
    circle_block = prompt[circle_start:]
    assert "verbose" not in circle_block
