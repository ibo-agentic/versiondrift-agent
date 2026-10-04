"""F3 native tool format: the general "every tool name must appear in the
rendered prompt" check, and the Phi-4-mini fix it was added alongside
(PLAN.md 10.2 smoke-test follow-up, 2026-10-05).

The Phi-4-mini template below is the EXACT, verbatim ``chat_template``
string fetched this session from
``https://huggingface.co/microsoft/Phi-4-mini-instruct/raw/main/tokenizer_config.json``
-- not a paraphrase. It is what caused the real bug: passing ``tools=``
as a top-level kwarg (this project's one mechanism before this fix)
rendered a prompt with no tool information at all, silently, for this
one model -- confirmed in the smoke test (0% tool-call parse rate, zero
detected tool-call attempts of any shape) and root-caused by rendering
this exact template directly (see analysis/plan/smoke_report.md and
docs/ENGINEERING_NOTES.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from upgradecanary.model.llama_cpp_client import missing_tool_names

# Importing llama_cpp.llama_chat_format triggers loading the real llama.dll
# (even though Jinja2ChatFormatter itself needs no model/GPU) -- same
# Windows DLL-search-order issue as everywhere else this project loads
# llama_cpp for real; see analysis/audit/_dll_preload.py's own docstring.
# Best-effort here: harmless on a machine that does not need it, and the
# two tests below skip cleanly (rather than erroring) if llama_cpp still
# cannot be imported at all.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis" / "audit"))
try:
    import _dll_preload

    _dll_preload.preload()
except Exception:
    pass

PHI4_MINI_CHAT_TEMPLATE = (
    "{% for message in messages %}"
    "{% if message['role'] == 'system' and 'tools' in message and message['tools'] is not none %}"
    "{{ '<|' + message['role'] + '|>' + message['content'] + '<|tool|>' + message['tools'] + '<|/tool|>' + '<|end|>' }}"
    "{% else %}"
    "{{ '<|' + message['role'] + '|>' + message['content'] + '<|end|>' }}"
    "{% endif %}"
    "{% endfor %}"
    "{% if add_generation_prompt %}"
    "{{ '<|assistant|>' }}"
    "{% else %}"
    "{{ eos_token }}"
    "{% endif %}"
)

TOOL = {
    "type": "function",
    "function": {"name": "get_weather", "description": "Get the weather.", "parameters": {}},
}


def _formatter():
    Jinja2ChatFormatter = pytest.importorskip("llama_cpp.llama_chat_format").Jinja2ChatFormatter

    return Jinja2ChatFormatter(
        template=PHI4_MINI_CHAT_TEMPLATE,
        eos_token="<|endoftext|>",
        bos_token="",
        add_generation_prompt=True,
    )


# --- missing_tool_names() as a pure function --------------------------------


def test_missing_tool_names_all_present():
    assert missing_tool_names("... get_weather ... get_time ...", [
        {"function": {"name": "get_weather"}}, {"function": {"name": "get_time"}},
    ]) == []


def test_missing_tool_names_reports_each_absent_name():
    assert missing_tool_names("nothing relevant here", [
        {"function": {"name": "get_weather"}}, {"function": {"name": "get_time"}},
    ]) == ["get_weather", "get_time"]


def test_missing_tool_names_partial():
    assert missing_tool_names("mentions get_weather only", [
        {"function": {"name": "get_weather"}}, {"function": {"name": "get_time"}},
    ]) == ["get_time"]


def test_missing_tool_names_ignores_tools_with_no_name():
    assert missing_tool_names("anything", [{"function": {}}]) == []


# --- Phi-4-mini's real template: reproduces the bug, proves the fix ---------


def test_phi4_mini_template_drops_top_level_tools_kwarg():
    """Reproduces the original bug exactly: passing tools= the way every
    other model's template here expects renders NO tool information at
    all for Phi-4-mini's real template -- this is why it went undetected
    until the smoke test's actual parse-rate numbers exposed it."""
    formatter = _formatter()
    rendered = formatter(messages=[{"role": "user", "content": "What is the weather?"}], tools=[TOOL])
    assert missing_tool_names(rendered.prompt, [TOOL]) == ["get_weather"]


def test_phi4_mini_template_renders_tools_via_system_message_fallback():
    """The fix: Phi-4-mini's template only reads a per-message "tools"
    field on a system message, and only as a pre-serialized JSON STRING
    (the template does raw string concatenation, not a render of a
    Python object) -- this is the exact fallback LlamaCppClient.generate()
    now retries with."""
    import json

    formatter = _formatter()
    fallback_messages = [
        {"role": "system", "content": "", "tools": json.dumps([TOOL])},
        {"role": "user", "content": "What is the weather?"},
    ]
    rendered = formatter(messages=fallback_messages, tools=[TOOL])
    assert missing_tool_names(rendered.prompt, [TOOL]) == []
    assert "<|tool|>" in rendered.prompt
    assert "get_weather" in rendered.prompt
