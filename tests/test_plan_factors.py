"""PLAN.md 10.1 item 2: F1-F6 (+F11) config switches.

Covers upgradecanary/constrained.py's schema conversions (F3/F4) and
runner.py's resolve_run_factors()/validate_run_factors()/build_prompt()
native-format path. No model is run; these are all pure-logic checks.
"""

from __future__ import annotations

import pytest

from upgradecanary.constrained import (
    GENERIC_JSON_RESPONSE_SCHEMA,
    args_to_json_schema,
    full_schema_response_schema,
    response_schema_for,
    schema_to_openai_tool,
)
from upgradecanary.runner import build_prompt, resolve_run_factors, validate_run_factors
from upgradecanary.tasks import Task

WEATHER_SCHEMA = {
    "name": "get_weather",
    "description": "Get the current weather for a city.",
    "args": {
        "city": {"type": "string", "required": True},
        "unit": {"type": "string", "required": True, "enum": ["celsius", "fahrenheit"]},
        "include_humidity": {"type": "boolean", "required": False, "default": True},
    },
}


def test_args_to_json_schema_basic():
    out = args_to_json_schema(WEATHER_SCHEMA)
    assert out["type"] == "object"
    assert out["properties"]["city"] == {"type": "string"}
    assert out["properties"]["unit"]["enum"] == ["celsius", "fahrenheit"]
    assert out["properties"]["include_humidity"]["default"] is True
    assert set(out["required"]) == {"city", "unit"}


def test_args_to_json_schema_no_required_omits_key():
    schema = {"name": "noop", "args": {"x": {"type": "string", "required": False}}}
    out = args_to_json_schema(schema)
    assert "required" not in out


def test_schema_to_openai_tool_shape():
    tool = schema_to_openai_tool(WEATHER_SCHEMA)
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "get_weather"
    assert tool["function"]["description"] == "Get the current weather for a city."
    assert tool["function"]["parameters"]["properties"]["city"]["type"] == "string"


def test_full_schema_response_schema_constrains_name_and_args():
    out = full_schema_response_schema(WEATHER_SCHEMA)
    assert out["properties"]["name"] == {"const": "get_weather"}
    assert out["properties"]["arguments"]["properties"]["unit"]["enum"] == ["celsius", "fahrenheit"]
    assert out["required"] == ["name", "arguments"]


def test_response_schema_for_off_is_none():
    assert response_schema_for("off", WEATHER_SCHEMA) is None


def test_response_schema_for_generic_json_ignores_schema():
    assert response_schema_for("generic_json", None) == GENERIC_JSON_RESPONSE_SCHEMA
    assert response_schema_for("generic_json", WEATHER_SCHEMA) == GENERIC_JSON_RESPONSE_SCHEMA


def test_response_schema_for_full_schema_needs_a_schema():
    with pytest.raises(ValueError):
        response_schema_for("full_schema", None)
    out = response_schema_for("full_schema", WEATHER_SCHEMA)
    assert out["properties"]["name"] == {"const": "get_weather"}


def test_response_schema_for_rejects_unknown_mode():
    with pytest.raises(ValueError):
        response_schema_for("sometimes", WEATHER_SCHEMA)


def _make_task(**overrides) -> Task:
    base = dict(
        task_id="t1", prompt="What is the weather in Berlin?", tool="get_weather",
        expected_call={"name": "get_weather", "arguments": {"city": "Berlin", "unit": "celsius"}},
    )
    base.update(overrides)
    return Task(**base)


def test_build_prompt_shared_is_unchanged_default():
    task = _make_task()
    prompt = build_prompt(task, WEATHER_SCHEMA)  # prompt_format defaults to "shared"
    assert "Available tool schema" in prompt
    assert "get_weather" in prompt
    assert prompt.endswith("Answer:")


def test_build_prompt_native_is_just_the_bare_question():
    task = _make_task()
    prompt = build_prompt(task, WEATHER_SCHEMA, prompt_format="native")
    assert prompt == task.prompt
    assert "Available tool schema" not in prompt


def test_build_prompt_rejects_unknown_format():
    task = _make_task()
    with pytest.raises(ValueError):
        build_prompt(task, WEATHER_SCHEMA, prompt_format="weird")


def test_resolve_run_factors_defaults():
    cfg = {"model": {}}
    factors = resolve_run_factors(cfg)
    assert factors == {
        "F1_max_tokens": None,
        "F2_thinking": "default",
        "F3_prompt_format": "shared",
        "F4_constrained_decoding": "off",
        "F5_quant_level": "unspecified",
        "F6_sampling_preset": "shared",
        "F11_chat_wrapping": "legacy",
    }


def test_resolve_run_factors_reads_explicit_values():
    cfg = {
        "model": {
            "max_tokens": 1024, "thinking": "off", "quant_level": "Q8_0",
            "sampling_preset": "recommended", "chat_wrapping": "native",
        },
        "prompt_format": "native",
        "constrained_decoding": "full_schema",
    }
    factors = resolve_run_factors(cfg)
    assert factors["F1_max_tokens"] == 1024
    assert factors["F2_thinking"] == "off"
    assert factors["F3_prompt_format"] == "native"
    assert factors["F4_constrained_decoding"] == "full_schema"
    assert factors["F5_quant_level"] == "Q8_0"
    assert factors["F6_sampling_preset"] == "recommended"
    assert factors["F11_chat_wrapping"] == "native"


def test_validate_run_factors_accepts_defaults():
    validate_run_factors({"model": {}})  # must not raise


def test_validate_run_factors_rejects_native_prompt_format_with_legacy_wrapping():
    with pytest.raises(ValueError):
        validate_run_factors({"model": {"chat_wrapping": "legacy"}, "prompt_format": "native"})


def test_validate_run_factors_accepts_native_prompt_format_with_native_wrapping():
    validate_run_factors({"model": {"chat_wrapping": "native"}, "prompt_format": "native"})  # must not raise


def test_validate_run_factors_rejects_bad_enum_values():
    with pytest.raises(ValueError):
        validate_run_factors({"model": {}, "prompt_format": "weird"})
    with pytest.raises(ValueError):
        validate_run_factors({"model": {}, "constrained_decoding": "weird"})
    with pytest.raises(ValueError):
        validate_run_factors({"model": {"sampling_preset": "weird"}})
