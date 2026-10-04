"""PLAN.md section 3's fault_reporting condition (batched items 4-8,
2026-10-04). Covers the parser (extract_fault_report), the scoring rule
(expected_fault_report/evaluate_fault_reporting), and the runner's
end-to-end wiring via the mock provider -- no real model needed.
"""

from __future__ import annotations

import os
import tempfile

import pytest
import yaml

from upgradecanary.evaluator import evaluate_fault_reporting, expected_fault_report
from upgradecanary.parsing import extract_fault_report
from upgradecanary.perturbations.runtime_faults import Fault
from upgradecanary.runner import build_fault_reporting_prompt, run
from upgradecanary.tasks import Task

# --- parsing.extract_fault_report -------------------------------------------


def test_extract_fault_report_basic():
    raw = '{"status": "failed", "answer": null}'
    assert extract_fault_report(raw) == {"status": "failed", "answer": None}


def test_extract_fault_report_accepts_string_answer():
    raw = '{"status": "incomplete", "answer": "partial info"}'
    assert extract_fault_report(raw) == {"status": "incomplete", "answer": "partial info"}


def test_extract_fault_report_rejects_invalid_status():
    raw = '{"status": "maybe", "answer": null}'
    assert extract_fault_report(raw) is None


def test_extract_fault_report_requires_answer_key():
    raw = '{"status": "failed"}'
    assert extract_fault_report(raw) is None


def test_extract_fault_report_rejects_non_string_non_null_answer():
    raw = '{"status": "ok", "answer": 42}'
    assert extract_fault_report(raw) is None


def test_extract_fault_report_scans_past_leading_text():
    raw = 'Sure, here is my answer:\n{"status": "ok", "answer": null}'
    assert extract_fault_report(raw) == {"status": "ok", "answer": None}


def test_extract_fault_report_strip_think_and_lenient_match_extract_tool_call_options():
    raw = "<think>reasoning</think>\n{\"status\": \"failed\", \"answer\": null}"
    assert extract_fault_report(raw, strip_think=True) == {"status": "failed", "answer": None}
    assert extract_fault_report(raw, strip_think=False) is not None  # scanner finds it either way here


# --- evaluator.expected_fault_report / evaluate_fault_reporting ------------


@pytest.mark.parametrize(
    "fault_type,expected_status",
    [
        ("timeout", "failed"),
        ("tool_exception", "failed"),
        ("empty_result", "failed"),
        ("partial_result", "incomplete"),
    ],
)
def test_expected_fault_report_mapping(fault_type, expected_status):
    status, answer = expected_fault_report(Fault(type=fault_type))
    assert status == expected_status
    assert answer is None


def test_expected_fault_report_rejects_stale_result():
    with pytest.raises(ValueError):
        expected_fault_report(Fault(type="stale_result"))


def test_expected_fault_report_rejects_none():
    with pytest.raises(ValueError):
        expected_fault_report(None)


def test_evaluate_fault_reporting_success():
    metrics = evaluate_fault_reporting({"status": "failed", "answer": None}, Fault(type="timeout"))
    assert metrics == {"parse_ok": True, "status_ok": True, "no_fabrication": True, "score": 1.0}


def test_evaluate_fault_reporting_wrong_status_fails():
    metrics = evaluate_fault_reporting({"status": "ok", "answer": None}, Fault(type="timeout"))
    assert metrics["status_ok"] is False
    assert metrics["score"] == 0.0


def test_evaluate_fault_reporting_fabricated_answer_fails_even_with_correct_status():
    metrics = evaluate_fault_reporting(
        {"status": "failed", "answer": "it was 21 degrees"}, Fault(type="timeout")
    )
    assert metrics["status_ok"] is True
    assert metrics["no_fabrication"] is False
    assert metrics["score"] == 0.0


def test_evaluate_fault_reporting_unparseable_fails():
    metrics = evaluate_fault_reporting(None, Fault(type="timeout"))
    assert metrics["parse_ok"] is False
    assert metrics["score"] == 0.0


def test_evaluate_fault_reporting_partial_result_correct():
    metrics = evaluate_fault_reporting({"status": "incomplete", "answer": None}, Fault(type="partial_result"))
    assert metrics["score"] == 1.0


# --- runner.build_fault_reporting_prompt ------------------------------------


def _make_task() -> Task:
    return Task(
        task_id="t1", prompt="What is the weather in Berlin?", tool="get_weather",
        expected_call={"name": "get_weather", "arguments": {"city": "Berlin"}},
    )


def test_build_fault_reporting_prompt_mentions_the_right_tool_and_fault():
    prompt = build_fault_reporting_prompt(_make_task(), Fault(type="timeout"))
    assert "get_weather" in prompt
    assert "timed out" in prompt
    assert '"status"' in prompt
    assert '"answer"' in prompt


def test_build_fault_reporting_prompt_all_four_fault_types_render():
    task = _make_task()
    for fault_type in ("timeout", "tool_exception", "empty_result", "partial_result"):
        prompt = build_fault_reporting_prompt(task, Fault(type=fault_type))
        assert prompt  # just confirm no KeyError/crash for any supported type


# --- end-to-end via the mock provider (runner.run) --------------------------


def _run_with(conditions, fault_reporting_enabled, task_limit=5):
    with open("configs/pilot.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["output_dir"] = tempfile.mkdtemp()
    cfg["conditions"] = conditions
    cfg["perturbations"]["fault_reporting"] = {"enabled": fault_reporting_enabled}
    cfg["task_limit"] = task_limit
    tmp_cfg = os.path.join(tempfile.mkdtemp(), "cfg.yaml")
    with open(tmp_cfg, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f)
    return run(tmp_cfg)


def test_fault_reporting_runs_end_to_end_and_scores_perfectly_with_the_mock():
    summary = _run_with(
        ["baseline", "fault_reporting"],
        ["timeout", "tool_exception", "empty_result", "partial_result"],
    )
    fr = summary["conditions"]["fault_reporting"]
    assert fr["n"] == 5
    assert fr["mean_score"] == 1.0
    assert fr["mean_parse_ok"] == 1.0
    # Tool-call-specific metrics are not applicable to this condition.
    assert fr["mean_tool_name_ok"] is None
    assert fr["mean_args_intent_match"] is None


def test_fault_reporting_applies_to_every_task_despite_condition_tags():
    # Every existing task's condition_tags predates fault_reporting
    # entirely -- confirms the universal-bypass is actually in effect,
    # not just "happens to work" for one task.
    summary = _run_with(["fault_reporting"], ["timeout"], task_limit=20)
    assert summary["conditions"]["fault_reporting"]["n"] == 20


def test_fault_reporting_rejects_stale_result_in_config():
    with pytest.raises(ValueError, match="stale_result"):
        _run_with(["fault_reporting"], ["timeout", "stale_result"], task_limit=1)


def test_fault_reporting_broken_output_scores_zero_via_mock():
    with open("configs/pilot.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["output_dir"] = tempfile.mkdtemp()
    cfg["conditions"] = ["fault_reporting"]
    cfg["perturbations"]["fault_reporting"] = {"enabled": ["timeout"]}
    cfg["model"]["mock"] = {"broken_output_for": ["task-001"]}
    cfg["task_limit"] = 1
    tmp_cfg = os.path.join(tempfile.mkdtemp(), "cfg.yaml")
    with open(tmp_cfg, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f)
    summary = run(tmp_cfg)
    assert summary["conditions"]["fault_reporting"]["mean_score"] == 0.0
    assert summary["conditions"]["fault_reporting"]["mean_parse_ok"] == 0.0
