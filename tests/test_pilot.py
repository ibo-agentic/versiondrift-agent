"""Pilot tests: metric semantics, strict validation policy, task coverage."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from upgradecanary.evaluator import evaluate
from upgradecanary.perturbations.schema_drift import (
    apply,
    drifted_schema,
    expressions_equivalent,
    to_canonical_args,
)
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
