"""Pilot tests: metric semantics, strict validation policy, task coverage."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
import yaml

from upgradecanary import bfcl as bfcl_mod
from upgradecanary import runner
from upgradecanary.bfcl import is_eligible
from upgradecanary.evaluator import evaluate
from upgradecanary.perturbations.runtime_faults import Fault
from upgradecanary.perturbations.schema_drift import (
    apply,
    drifted_schema,
    expressions_equivalent,
    generate_specs_from_schema,
    to_canonical_args,
)
from upgradecanary.tasks import load_tasks
from upgradecanary.tools import BASE_SCHEMAS, execute, validate_call
from upgradecanary.utils import rng_for

ROOT = Path(__file__).resolve().parent.parent

DRIFT_TYPES = [
    "field_rename",
    "field_drop",
    "type_mutation",
    "unexpected_field",
    "enum_drift",
]


def test_intent_match_vs_valid_under_drift():
    """A stale call matches intent but fails drifted-schema validation;
    an adapted call passes both."""
    drift = apply(
        "calculator", ["field_rename"], rng_for(1234, "t", "schema_drift"), "field_rename"
    )
    schema = drifted_schema(BASE_SCHEMAS["calculator"], drift)
    expected = {"name": "calculator", "arguments": {"expression": "1 + 2"}}
    stale = {"name": "calculator", "arguments": {"expression": "1 + 2"}}  # pre-upgrade name
    adapted = {"name": "calculator", "arguments": {"expr": "1 + 2"}}  # post-upgrade name

    m_stale = evaluate(
        "schema_drift", expected, stale, {"ok": False}, drift, None, None, schema, False
    )
    assert m_stale["args_intent_match"] is True
    assert m_stale["args_valid_under_drift"] is False

    m_adapted = evaluate(
        "schema_drift", expected, adapted, {"ok": True}, drift, None, None, schema, False
    )
    assert m_adapted["args_intent_match"] is True
    assert m_adapted["args_valid_under_drift"] is True


def test_missing_required_fails_despite_default():
    """The include_humidity spec declares default=True, but the strict policy
    requires the field to be present; it is never auto-applied."""
    drift = apply(
        "get_weather", ["unexpected_field"], rng_for(1, "t", "c"), "unexpected_field"
    )
    schema = drifted_schema(BASE_SCHEMAS["get_weather"], drift)
    assert schema["args"]["include_humidity"].get("default") is True
    problems = validate_call(
        "get_weather", {"city": "Berlin", "unit": "celsius"}, schema, strict=False
    )
    assert any("include_humidity" in p for p in problems)


def test_task_coverage_counts():
    """100 tasks, unique ids, all conditions per task, balanced tools,
    every drift type represented at least 10 times."""
    rows = [
        json.loads(line)
        for line in (ROOT / "data" / "base_tasks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 100
    assert len({r["task_id"] for r in rows}) == 100

    required_conditions = {"baseline", "schema_drift", "runtime_fault"}
    assert all(required_conditions <= set(r["condition_tags"]) for r in rows)

    tools = Counter(r["tool"] for r in rows)
    assert set(tools) == set(BASE_SCHEMAS)
    assert max(tools.values()) - min(tools.values()) <= 5

    drifts = Counter(r["drift_type"] for r in rows)
    for drift_type in DRIFT_TYPES:
        assert drifts.get(drift_type, 0) >= 10, (
            f"drift type {drift_type} underrepresented: {drifts.get(drift_type, 0)}"
        )


def test_expression_intent_semantics():
    """args_intent_match accepts mathematically equivalent expressions;
    args_exact stays byte-strict."""
    expected = {"name": "calculator", "arguments": {"expression": "7 * 3 + 11"}}
    parsed = {"name": "calculator", "arguments": {"expression": "7*3+11"}}
    schema = drifted_schema(BASE_SCHEMAS["calculator"], None)
    metrics = evaluate("baseline", expected, parsed, {"ok": True}, None, None, None, schema, True)
    assert metrics["args_exact"] is False
    assert metrics["args_intent_match"] is True
    assert expressions_equivalent("7*3+11", "7 * 3 + 11") is True
    assert expressions_equivalent("1+2", "4") is False
    assert expressions_equivalent("two plus two", "4") is None


def test_type_mutation_canonicalized_before_execution():
    """A correctly string-typed value under the drifted schema passes strict
    drifted validation and executes after safe coercion to the canonical type."""
    drift = apply("search_docs", ["type_mutation"], rng_for(1, "t", "c"), "type_mutation")
    schema = drifted_schema(BASE_SCHEMAS["search_docs"], drift)
    call = {"name": "search_docs", "arguments": {"query": "write amplification", "top_k": "3"}}
    assert validate_call(call["name"], call["arguments"], schema, strict=False) == []
    result = execute(call, schema, drift, None, strict=False)
    assert result["ok"] is True
    canonical = to_canonical_args(call["arguments"], drift, BASE_SCHEMAS["search_docs"])
    assert canonical["top_k"] == 3
    assert isinstance(canonical["top_k"], int)


def test_unexpected_field_dropped_before_execution():
    """A correctly included drift-only field passes strict drifted validation
    and is dropped before the canonical mock handler runs."""
    drift = apply(
        "get_weather", ["unexpected_field"], rng_for(1, "t", "c"), "unexpected_field"
    )
    schema = drifted_schema(BASE_SCHEMAS["get_weather"], drift)
    call = {
        "name": "get_weather",
        "arguments": {"city": "Berlin", "unit": "celsius", "include_humidity": True},
    }
    assert validate_call(call["name"], call["arguments"], schema, strict=False) == []
    result = execute(call, schema, drift, None, strict=False)
    assert result["ok"] is True
    canonical = to_canonical_args(call["arguments"], drift, BASE_SCHEMAS["get_weather"])
    assert "include_humidity" not in canonical


def test_score_is_functional_not_exact():
    """args_exact is diagnostic only: byte-mismatched but semantically
    correct, schema-valid, cleanly executed call scores 1."""
    expected = {"name": "calculator", "arguments": {"expression": "7 * 3 + 11"}}
    parsed = {"name": "calculator", "arguments": {"expression": "7*3+11"}}
    schema = drifted_schema(BASE_SCHEMAS["calculator"], None)
    metrics = evaluate(
        "baseline", expected, parsed, {"ok": True}, None, None, None, schema, True
    )
    assert metrics["args_exact"] is False
    assert metrics["args_intent_match"] is True
    assert metrics["args_valid_under_drift"] is True
    assert metrics["executor_ok"] is True
    assert metrics["score"] == 1.0


def _trials_config(tmp_path: Path, out_dir: Path, trials: int) -> Path:
    cfg = {
        "experiment": "trials-test",
        "seed": 1234,
        "data": str(ROOT / "data" / "base_tasks.jsonl"),
        "output_dir": str(out_dir),
        "task_limit": 2,
        "conditions": ["baseline", "schema_drift", "runtime_fault"],
        "model": {"provider": "mock", "temperature": 0.0, "seed": 1234},
        "perturbations": {
            "schema_drift": {
                "enabled": ["field_rename", "field_drop", "type_mutation",
                            "unexpected_field", "enum_drift"]
            },
            "runtime_faults": {
                "enabled": ["timeout", "tool_exception", "empty_result",
                            "stale_result", "partial_result"],
                "retry_once": True,
            },
        },
        "executor": {"strict_baseline_args": True},
    }
    if trials:
        cfg["trials"] = trials
        cfg["trial_temperatures"] = [0.0, 0.7, 0.7][:trials]
        cfg["trial_seeds"] = [1234, 1235, 1236][:trials]
    path = tmp_path / f"config_{out_dir.name}.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path


def _load_parsed(out_dir: Path) -> list[dict]:
    files = list(Path(out_dir).glob("*/parsed_results.jsonl"))
    assert len(files) == 1, f"expected one run dir, found {files}"
    return [json.loads(l) for l in files[0].read_text(encoding="utf-8").splitlines() if l.strip()]


def test_trials_respected_and_recorded(tmp_path):
    out = tmp_path / "out"
    summary = runner.run(str(_trials_config(tmp_path, out, trials=3)))
    rows = _load_parsed(out)
    assert len(rows) == 2 * 3 * 3  # 2 tasks x 3 conditions x 3 trials
    by_pair: dict = {}
    for r in rows:
        by_pair.setdefault((r["task_id"], r["condition"]), set()).add(r["trial_index"])
    assert len(by_pair) == 6
    assert all(v == {0, 1, 2} for v in by_pair.values())
    for r in rows:
        assert r["temperature"] == [0.0, 0.7, 0.7][r["trial_index"]]
        assert r["seed"] == [1234, 1235, 1236][r["trial_index"]]
    assert summary["conditions"]["baseline"]["by_trial"] == {"0": 1.0, "1": 1.0, "2": 1.0}


def test_trial_runs_are_deterministic(tmp_path):
    out_a, out_b = tmp_path / "a", tmp_path / "b"
    runner.run(str(_trials_config(tmp_path, out_a, trials=2)))
    runner.run(str(_trials_config(tmp_path, out_b, trials=2)))
    a, b = _load_parsed(out_a), _load_parsed(out_b)
    assert a == b  # content and ordering identical across reruns
    keys = [(r["task_id"], r["condition"], r["trial_index"]) for r in a]
    assert keys == sorted(keys)


def test_trial_config_validation():
    base = {"trials": 3, "model": {"temperature": 0.0, "seed": 1234},
            "trial_temperatures": [0.0, 0.7], "trial_seeds": [1234, 1235, 1236]}
    with pytest.raises(ValueError):
        runner.build_trials(base)
    ok = runner.build_trials({"trials": 2, "model": {"temperature": 0.0, "seed": 9}})
    assert ok == [{"temperature": 0.0, "seed": 9}] * 2


def _mini_bfcl_record(question, fn_name="calc_area", props=None, required=None):
    props = props or {"base": {"type": "integer"}, "height": {"type": "integer"}}
    required = required if required is not None else ["base", "height"]
    return {
        "id": "simple_python_999",
        "question": [[{"role": "user", "content": question}]],
        "function": [{
            "name": fn_name,
            "description": "demo",
            "parameters": {"type": "dict", "properties": props, "required": required},
        }],
    }


def _mini_bfcl_answer(args=None):
    args = args or {"base": [10], "height": [5]}
    return {"id": "simple_python_999", "ground_truth": [{"calc_area": args}]}


def test_bfcl_eligibility_rules():
    rec = _mini_bfcl_record(
        "Find the area of a triangle with a base of 10 units and height of 5 units."
    )
    ans = _mini_bfcl_answer()
    assert is_eligible(rec, ans) == (True, "ok")
    assert not is_eligible(rec, None)[0]                                    # rule 2
    two_fns = _mini_bfcl_record(
        "Find the area of a triangle with a base of 10 units and height of 5 units."
    )
    two_fns["function"].append(two_fns["function"][0])
    assert not is_eligible(two_fns, ans)[0]                                 # rule 3
    assert not is_eligible(rec, _mini_bfcl_answer({"base": [10], "height": [[5]]}))[0]  # rule 9
    short = _mini_bfcl_record("How big? too short.")
    assert not is_eligible(short, _mini_bfcl_answer())[0]                   # rule 6
    with_url = _mini_bfcl_record(
        "Find the area of a triangle with a base of 10 units see http://x.co and height of 5."
    )
    assert not is_eligible(with_url, ans)[0]                                # rule 7
    ungrounded = _mini_bfcl_record(
        "Find the area of a triangle with a base of 10 units and height of 5 units.",
        props={"base": {"type": "integer"}, "secret": {"type": "integer"}},
        required=["base", "secret"],
    )
    assert not is_eligible(ungrounded, _mini_bfcl_answer({"base": [10], "secret": [99]}))[0]  # rule 8


def test_bfcl_selection_deterministic(tmp_path):
    stats = bfcl_mod.generate(tmp_path)
    assert stats["selected"] == 100
    assert stats["eligible"] >= 100
    first = (tmp_path / "bfcl_tasks.jsonl").read_text(encoding="utf-8")
    bfcl_mod.generate(tmp_path)  # regeneration must be byte-identical
    assert (tmp_path / "bfcl_tasks.jsonl").read_text(encoding="utf-8") == first
    ids = [json.loads(line)["task_id"] for line in first.splitlines()]
    assert len(ids) == len(set(ids)) == 100


def test_bfcl_conversion_and_no_enum_drift(tmp_path):
    bfcl_mod.generate(tmp_path)
    tasks = load_tasks(tmp_path / "bfcl_tasks.jsonl")
    assert len(tasks) == 100
    for task in tasks:
        assert task.suite == "bfcl" and task.source_id
        assert task.tool_schema and task.internal_schema and task.acceptable
        assert validate_call(
            task.expected_call["name"], task.expected_call["arguments"],
            task.internal_schema, strict=False,
        ) == []
        for key, value in task.expected_call["arguments"].items():
            assert value in task.acceptable[key]
        specs = generate_specs_from_schema(task.internal_schema)
        assert specs and all(s["type"] != "enum_drift" for s in specs)
        drift = apply(
            task.tool,
            ["field_rename", "field_drop", "type_mutation", "unexpected_field", "enum_drift"],
            rng_for(1, task.task_id, "schema_drift"),
            schema=task.internal_schema,
        )
        assert drift is None or drift.type != "enum_drift"


def test_simulated_handler_determinism(tmp_path):
    bfcl_mod.generate(tmp_path)
    task = load_tasks(tmp_path / "bfcl_tasks.jsonl")[0]
    schema = drifted_schema(task.internal_schema, None)
    r1 = execute(task.expected_call, schema, None, None, True, canonical_schema=task.internal_schema)
    r2 = execute(task.expected_call, schema, None, None, True, canonical_schema=task.internal_schema)
    assert r1 == r2
    assert r1["ok"] is True and r1["result"]["simulated"] is True
    r3 = execute(task.expected_call, schema, None, Fault("timeout"), False,
                 canonical_schema=task.internal_schema)
    assert r3["ok"] is False  # fault machinery applies to simulated tools too


def test_synthetic_loader_unchanged():
    tasks = load_tasks(ROOT / "data" / "base_tasks.jsonl")
    assert len(tasks) == 100
    assert all(t.suite == "synthetic" for t in tasks)
    assert all(t.internal_schema is None for t in tasks)


def _expr_rename_drift():
    drift = apply(
        "calculator", ["field_rename"], rng_for(7, "t", "schema_drift"), "field_rename"
    )
    assert drift.field == "expression" and drift.params["new_name"] == "expr"
    return drift


def test_renamed_expression_equivalence():
    """expression->expr rename with different spacing: intent matches on
    canonical argument semantics, not the literal drifted key name."""
    drift = _expr_rename_drift()
    schema = drifted_schema(BASE_SCHEMAS["calculator"], drift)
    expected = {"name": "calculator", "arguments": {"expression": "7 * 3 + 11"}}
    adapted = {"name": "calculator", "arguments": {"expr": "7*3+11"}}
    metrics = evaluate(
        "schema_drift", expected, adapted, {"ok": True}, drift, None, None, schema, False
    )
    assert metrics["args_intent_match"] is True
    assert metrics["args_valid_under_drift"] is True


def test_renamed_expression_not_equivalent():
    """Same rename, but the expression evaluates differently: no match."""
    drift = _expr_rename_drift()
    schema = drifted_schema(BASE_SCHEMAS["calculator"], drift)
    expected = {"name": "calculator", "arguments": {"expression": "7 * 3 + 11"}}
    wrong = {"name": "calculator", "arguments": {"expr": "7*3+12"}}
    metrics = evaluate(
        "schema_drift", expected, wrong, {"ok": True}, drift, None, None, schema, False
    )
    assert metrics["args_intent_match"] is False


def test_renamed_expression_requires_matching_key():
    """A call under the rename must still carry the right argument; a wrong
    key fails even if its value is an equivalent expression."""
    drift = _expr_rename_drift()
    schema = drifted_schema(BASE_SCHEMAS["calculator"], drift)
    expected = {"name": "calculator", "arguments": {"expression": "7 * 3 + 11"}}
    bad_key = {"name": "calculator", "arguments": {"result": "7*3+11"}}
    metrics = evaluate(
        "schema_drift", expected, bad_key, {"ok": True}, drift, None, None, schema, False
    )
    assert metrics["args_intent_match"] is False
    # A stale call using the pre-upgrade name still matches intent.
    stale = {"name": "calculator", "arguments": {"expression": "7 * 3 + 11"}}
    stale_metrics = evaluate(
        "schema_drift", expected, stale, {"ok": True}, drift, None, None, schema, False
    )
    assert stale_metrics["args_intent_match"] is True
