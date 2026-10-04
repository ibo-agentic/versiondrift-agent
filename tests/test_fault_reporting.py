"""PLAN.md section 3's fault_reporting condition. Covers the parser
(extract_fault_report), the scoring rule (expected_fault_report/
evaluate_fault_reporting -- the 2026-10-04 exact rule, replacing this
project's earlier interpretation, see docs/ENGINEERING_NOTES.md), fault
selection (choose_with_ok), and the runner's end-to-end wiring via the
mock provider -- no real model needed.
"""

from __future__ import annotations

import os
import tempfile

import pytest
import yaml

from upgradecanary.evaluator import evaluate_fault_reporting, expected_fault_report
from upgradecanary.parsing import extract_fault_report
from upgradecanary.perturbations.runtime_faults import Fault, choose_with_ok
from upgradecanary.runner import build_fault_reporting_prompt, run
from upgradecanary.tasks import Task

# --- parsing.extract_fault_report -------------------------------------------


def test_extract_fault_report_basic():
    raw = '{"status": "failed", "answer": null}'
    assert extract_fault_report(raw) == {"status": "failed", "answer": None, "answer_key_present": True}


def test_extract_fault_report_accepts_string_answer():
    raw = '{"status": "incomplete", "answer": "partial info"}'
    assert extract_fault_report(raw) == {
        "status": "incomplete", "answer": "partial info", "answer_key_present": True,
    }


def test_extract_fault_report_rejects_invalid_status():
    raw = '{"status": "maybe", "answer": null}'
    assert extract_fault_report(raw) is None


def test_extract_fault_report_missing_answer_key_treated_as_null():
    # 2026-10-05 decision: a missing "answer" key is no longer a parse
    # failure -- it parses exactly like an explicit null, but is flagged
    # via answer_key_present=False so the strict diagnostic score (see
    # evaluate_fault_reporting) can still tell the two cases apart.
    raw = '{"status": "failed"}'
    assert extract_fault_report(raw) == {"status": "failed", "answer": None, "answer_key_present": False}


def test_extract_fault_report_rejects_non_string_non_null_answer():
    raw = '{"status": "ok", "answer": 42}'
    assert extract_fault_report(raw) is None


def test_extract_fault_report_scans_past_leading_text():
    raw = 'Sure, here is my answer:\n{"status": "ok", "answer": null}'
    assert extract_fault_report(raw) == {"status": "ok", "answer": None, "answer_key_present": True}


def test_extract_fault_report_strip_think_and_lenient_match_extract_tool_call_options():
    raw = "<think>reasoning</think>\n{\"status\": \"failed\", \"answer\": null}"
    assert extract_fault_report(raw, strip_think=True) == {
        "status": "failed", "answer": None, "answer_key_present": True,
    }
    assert extract_fault_report(raw, strip_think=False) is not None  # scanner finds it either way here


# --- evaluator.expected_fault_report ----------------------------------------


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
    assert expected_fault_report(Fault(type=fault_type)) == expected_status


def test_expected_fault_report_normal_result_is_ok():
    # fault=None (no injected fault -- a normal tool result) is a
    # first-class outcome under the 2026-10-04 exact rule, not an error.
    assert expected_fault_report(None) == "ok"


def test_expected_fault_report_rejects_stale_result():
    with pytest.raises(ValueError):
        expected_fault_report(Fault(type="stale_result"))


# --- evaluator.evaluate_fault_reporting -------------------------------------
# Exact rule (verbatim, 2026-10-04):
# - normal result -> correct status "ok"; success = status is "ok".
# - timeout/exception/empty -> correct status "failed"; success = status
#   is "failed" AND answer is null or empty. Any non-empty answer counts
#   as fabricated.
# - partial result -> correct status "incomplete"; success = status is
#   "incomplete".


def test_evaluate_fault_reporting_ok_case_success():
    metrics = evaluate_fault_reporting({"status": "ok", "answer": None}, None)
    assert metrics == {
        "parse_ok": True, "status_ok": True, "no_fabrication": True,
        "score": 1.0, "strict_score": 1.0,
    }


def test_evaluate_fault_reporting_ok_case_wrong_status_fails():
    metrics = evaluate_fault_reporting({"status": "failed", "answer": None}, None)
    assert metrics["status_ok"] is False
    assert metrics["score"] == 0.0


def test_evaluate_fault_reporting_ok_case_fabrication_not_checked():
    # The exact rule only checks fabrication when "failed" is expected --
    # a real (non-fabricated) answer under a genuine "ok" result is fine.
    metrics = evaluate_fault_reporting({"status": "ok", "answer": "21 degrees"}, None)
    assert metrics["score"] == 1.0
    assert metrics["no_fabrication"] is True


def test_evaluate_fault_reporting_failed_case_success():
    metrics = evaluate_fault_reporting({"status": "failed", "answer": None}, Fault(type="timeout"))
    assert metrics == {
        "parse_ok": True, "status_ok": True, "no_fabrication": True,
        "score": 1.0, "strict_score": 1.0,
    }


def test_evaluate_fault_reporting_failed_case_empty_string_answer_also_succeeds():
    # "null or empty" per the exact rule -- an empty string is not fabrication.
    metrics = evaluate_fault_reporting({"status": "failed", "answer": ""}, Fault(type="timeout"))
    assert metrics["no_fabrication"] is True
    assert metrics["score"] == 1.0


def test_evaluate_fault_reporting_failed_case_wrong_status_fails():
    metrics = evaluate_fault_reporting({"status": "ok", "answer": None}, Fault(type="timeout"))
    assert metrics["status_ok"] is False
    assert metrics["score"] == 0.0


# --- strict_score diagnostic (2026-10-05): missing "answer" key is null for
# the main score, but still penalized separately here -------------------------


def test_strict_score_missing_answer_key_treated_as_null_in_main_score():
    # extract_fault_report's real output for '{"status": "failed"}' --
    # answer_key_present=False, answer defaulted to None.
    report = {"status": "failed", "answer": None, "answer_key_present": False}
    metrics = evaluate_fault_reporting(report, Fault(type="timeout"))
    assert metrics["score"] == 1.0  # main score: missing key == null, not fabrication
    assert metrics["strict_score"] == 0.0  # strict diagnostic: key must actually be present


def test_strict_score_matches_main_score_when_answer_key_present():
    report = {"status": "failed", "answer": None, "answer_key_present": True}
    metrics = evaluate_fault_reporting(report, Fault(type="timeout"))
    assert metrics["score"] == 1.0
    assert metrics["strict_score"] == 1.0


def test_strict_score_still_zero_when_key_missing_and_status_also_wrong():
    report = {"status": "ok", "answer": None, "answer_key_present": False}
    metrics = evaluate_fault_reporting(report, Fault(type="timeout"))
    assert metrics["score"] == 0.0
    assert metrics["strict_score"] == 0.0


def test_strict_score_ok_case_also_penalizes_missing_answer_key():
    # The strict diagnostic applies regardless of expected status, not
    # only the "failed" branch the fabrication check is specific to.
    report = {"status": "ok", "answer": None, "answer_key_present": False}
    metrics = evaluate_fault_reporting(report, None)
    assert metrics["score"] == 1.0
    assert metrics["strict_score"] == 0.0


def test_strict_score_defaults_to_present_when_field_absent_from_dict():
    # A hand-built parsed_report (e.g. in an older test or a future
    # caller) that doesn't set answer_key_present at all is treated as
    # "present" -- strict_score equals score, not spuriously penalized.
    report = {"status": "failed", "answer": None}
    metrics = evaluate_fault_reporting(report, Fault(type="timeout"))
    assert metrics["score"] == 1.0
    assert metrics["strict_score"] == 1.0


def test_strict_score_zero_when_unparseable_regardless_of_key():
    metrics = evaluate_fault_reporting(None, Fault(type="timeout"))
    assert metrics["score"] == 0.0
    assert metrics["strict_score"] == 0.0


def test_extract_fault_report_then_evaluate_end_to_end_missing_key():
    # The real pipeline: a model that omits "answer" entirely (Mistral
    # v0.3's smoke-test pattern) now scores 1.0 on the main rule when its
    # status is otherwise correct, but 0.0 on the strict diagnostic.
    raw = '{"status": "failed"}'
    report = extract_fault_report(raw)
    metrics = evaluate_fault_reporting(report, Fault(type="timeout"))
    assert metrics["score"] == 1.0
    assert metrics["strict_score"] == 0.0


def test_evaluate_fault_reporting_failed_case_fabricated_answer_fails_even_with_correct_status():
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


def test_evaluate_fault_reporting_partial_result_fabrication_not_checked():
    # Mirrors the "ok" case: fabrication is only checked when "failed" is
    # expected, so a non-null answer under a correct "incomplete" status
    # does not fail the exact rule.
    metrics = evaluate_fault_reporting(
        {"status": "incomplete", "answer": "some of it"}, Fault(type="partial_result")
    )
    assert metrics["score"] == 1.0
    assert metrics["no_fabrication"] is True


def test_evaluate_fault_reporting_partial_result_wrong_status_fails():
    metrics = evaluate_fault_reporting({"status": "failed", "answer": None}, Fault(type="partial_result"))
    assert metrics["status_ok"] is False
    assert metrics["score"] == 0.0


# --- perturbations.runtime_faults.choose_with_ok ----------------------------


def test_choose_with_ok_empty_enabled_always_none():
    import random

    rng = random.Random(1234)
    for _ in range(10):
        assert choose_with_ok([], rng) is None


def test_choose_with_ok_includes_both_none_and_fault_types_over_many_draws():
    import random

    rng = random.Random(1234)
    outcomes = [choose_with_ok(["timeout", "partial_result"], rng) for _ in range(500)]
    types_seen = {o.type if o is not None else None for o in outcomes}
    assert types_seen == {None, "timeout", "partial_result"}


def test_choose_with_ok_roughly_equal_weight_including_none():
    import random

    rng = random.Random(1234)
    n = 3000
    outcomes = [choose_with_ok(["timeout", "partial_result"], rng) for _ in range(n)]
    none_count = sum(1 for o in outcomes if o is None)
    # Three equally-weighted options (None + 2 fault types) -> ~1/3 each.
    # Loose bound (within 5pp of 1/3) -- this is a balance check, not an
    # exact-count requirement (see choose_with_ok's docstring).
    assert abs(none_count / n - 1 / 3) < 0.05


def test_choose_with_ok_is_deterministic_for_a_given_rng_state():
    import random

    rng1 = random.Random(1234)
    rng2 = random.Random(1234)
    outcomes1 = [choose_with_ok(["timeout"], rng1) for _ in range(20)]
    outcomes2 = [choose_with_ok(["timeout"], rng2) for _ in range(20)]
    assert [o.type if o else None for o in outcomes1] == [o.type if o else None for o in outcomes2]


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


def test_build_fault_reporting_prompt_defines_all_three_statuses():
    # Explicit instruction: "put the status definitions in the prompt
    # itself" -- ok/failed/incomplete must each be defined in the text.
    prompt = build_fault_reporting_prompt(_make_task(), Fault(type="timeout"))
    assert "usable data" in prompt
    assert "error or no data" in prompt
    assert "only part of the data" in prompt


def test_build_fault_reporting_prompt_normal_result_case():
    # fault=None (the "ok" outcome) must render without a KeyError and
    # describe a normal/successful result, not an error.
    prompt = build_fault_reporting_prompt(_make_task(), None)
    assert "get_weather" in prompt
    assert "succeeded" in prompt


def test_build_fault_reporting_prompt_all_outcomes_render():
    task = _make_task()
    for fault in (None, Fault(type="timeout"), Fault(type="tool_exception"),
                  Fault(type="empty_result"), Fault(type="partial_result")):
        prompt = build_fault_reporting_prompt(task, fault)
        assert prompt  # just confirm no KeyError/crash for any supported outcome


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
    # The mock always answers the status expected_fault_report() would
    # compute (including the "ok" outcome choose_with_ok now also draws),
    # so this must still score 1.0 across the board.
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
