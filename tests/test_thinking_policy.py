"""Opt-in thinking handling (exploratory Granite-thinking add-on, 2026-11-28).

The defaults must leave every existing behavior unchanged; "strict" removes completed thinking and treats cut-off thinking as
unparsed, for Qwen3's <think> tags and Granite 3.2's "Here is my thought process:" / "Here is my response:" sections."""

import os
import tempfile

import pytest
import yaml

from upgradecanary.model.llama_cpp_client import native_render_kwargs
from upgradecanary.parsing import apply_thinking_policy, extract_fault_report, extract_tool_call, extract_tool_call_with_format
from upgradecanary.runner import run

CALL = '{"name": "get_weather", "arguments": {"city": "Berlin", "unit": "c"}}'
DRAFT = '{"name": "get_weather", "arguments": {"city": "Berlin", "unit": "celsius"}}'
QWEN_DONE = f"<think>\nI could send {DRAFT} but the schema says c.\n</think>\n\n{CALL}"
QWEN_CUT = f"<think>\nI could send {DRAFT} but let me check the schema again and"
GRANITE_DONE = f"Here is my thought process:\nMaybe {DRAFT}? No, the enum is c/f.\n\nHere is my response:\n{CALL}"
GRANITE_CUT = f"Here is my thought process:\nMaybe {DRAFT}? The enum lists c and f, so I need to"


def test_default_policy_is_the_identity():
    for raw in (QWEN_DONE, QWEN_CUT, GRANITE_DONE, GRANITE_CUT, CALL, ""):
        assert apply_thinking_policy(raw, None) == raw


def test_strict_keeps_only_the_text_after_completed_thinking():
    assert apply_thinking_policy(QWEN_DONE, "strict").strip() == CALL
    assert apply_thinking_policy(GRANITE_DONE, "strict").strip() == CALL
    assert apply_thinking_policy(CALL, "strict") == CALL                 # no thinking: unchanged


def test_strict_treats_cut_off_thinking_as_nothing_to_parse():
    assert apply_thinking_policy(QWEN_CUT, "strict") == ""
    assert apply_thinking_policy(GRANITE_CUT, "strict") == ""


def test_unknown_policy_is_refused():
    with pytest.raises(ValueError):
        apply_thinking_policy(CALL, "lenient")


@pytest.mark.parametrize("done, cut", [(QWEN_DONE, QWEN_CUT), (GRANITE_DONE, GRANITE_CUT)])
def test_tool_call_parsing_default_unchanged_and_strict_as_planned(done, cut):
    draft_args = {"city": "Berlin", "unit": "celsius"}
    # default: the first JSON in the text wins, even inside the thinking (the main study's behavior, unchanged)
    assert extract_tool_call(done)["arguments"] == draft_args
    assert extract_tool_call(cut)["arguments"] == draft_args
    # strict: completed thinking removed -> the final call; cut-off thinking -> unparsed
    assert extract_tool_call(done, thinking_policy="strict")["arguments"] == {"city": "Berlin", "unit": "c"}
    assert extract_tool_call(cut, thinking_policy="strict") is None
    assert extract_tool_call_with_format(cut, thinking_policy="strict") == (None, None)


def test_fault_report_parsing_default_unchanged_and_strict_as_planned():
    done = 'Here is my thought process:\nmaybe {"status": "incomplete", "answer": null}? no.\nHere is my response:\n{"status": "failed", "answer": null}'
    cut = 'Here is my thought process:\nmaybe {"status": "incomplete", "answer": null}? but a timeout means'
    assert extract_fault_report(done)["status"] == "incomplete"           # default: first JSON (from the thinking)
    assert extract_fault_report(done, thinking_policy="strict")["status"] == "failed"
    assert extract_fault_report(cut)["status"] == "incomplete"
    assert extract_fault_report(cut, thinking_policy="strict") is None


def test_native_render_kwargs():
    assert native_render_kwargs("default") == {}                          # unchanged rendering for every existing config
    assert native_render_kwargs("default", {}) == {}
    assert native_render_kwargs("on") == {"enable_thinking": True}
    assert native_render_kwargs("off") == {"enable_thinking": False}
    assert native_render_kwargs("default", {"thinking": True}) == {"thinking": True}


def _mock_cfg(**parsing):
    with open("configs/pilot.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["output_dir"] = tempfile.mkdtemp()
    cfg["conditions"] = ["baseline"]
    cfg["task_limit"] = 2
    if parsing:
        cfg["parsing"] = parsing
    path = os.path.join(tempfile.mkdtemp(), "cfg.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f)
    return path


def test_runner_accepts_strict_and_refuses_an_unknown_policy():
    a = run(_mock_cfg())
    b = run(_mock_cfg(thinking_policy="strict"))                          # the mock never thinks: identical scores
    assert a["conditions"]["baseline"]["mean_score"] == b["conditions"]["baseline"]["mean_score"]
    with pytest.raises(ValueError, match="thinking_policy"):
        run(_mock_cfg(thinking_policy="bogus"))
