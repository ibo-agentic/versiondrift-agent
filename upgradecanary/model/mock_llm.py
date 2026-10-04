"""Deterministic stand-in for a real model.

Lets the whole pipeline (perturb -> prompt -> parse -> execute -> score) run and
be tested before any GGUF file exists locally. Behaviour is controlled from
``configs/pilot.yaml`` under ``model.mock``:

- ``stale_on_drift``: under the schema_drift condition, emit the pre-upgrade
  argument names/values instead of adapting to the drifted schema.
- ``recover_after_fault``: on a retry after a runtime fault, emit a corrected
  call; otherwise repeat the failing output (no recovery).
- ``broken_output_for``: task ids that receive unparseable text (tests parse_ok).
"""

from __future__ import annotations

import json
from typing import Any

from ..evaluator import expected_fault_report
from ..perturbations.schema_drift import to_stale_args

_THOUGHTS = {
    "baseline": "Calling the tool with the expected arguments.",
    "schema_drift": "The tool schema changed in the upgrade; I will use the schema I was built with.",
    "runtime_fault": "The tool call needs to be issued; if it fails I will retry.",
}


class MockModelClient:
    def __init__(self, mock_cfg: dict[str, Any] | None = None) -> None:
        mock_cfg = mock_cfg or {}
        self.stale_on_drift: bool = mock_cfg.get("stale_on_drift", True)
        self.recover_after_fault: bool = mock_cfg.get("recover_after_fault", True)
        self.broken_output_for: list[str] = list(mock_cfg.get("broken_output_for", []))

    def generate(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        *,
        temperature: float | None = None,
        seed: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> str:
        # temperature/seed/tools/response_schema are accepted for interface
        # compatibility with real backends; the mock is fully deterministic
        # and ignores all of them (it already always emits a well-formed,
        # schema-matching call -- there is nothing for a grammar to constrain).
        context = context or {}
        task = context["task"]
        condition = context.get("condition", "baseline")
        is_retry = context.get("is_retry", False)

        if condition == "fault_reporting":
            return self._fault_report(task, context.get("fault"))

        if task.task_id in self.broken_output_for and not is_retry:
            return "I am sorry, but I cannot complete that request right now."

        if is_retry and not self.recover_after_fault:
            return self._first_attempt(task, condition, context.get("drift"))

        call = self._choose_call(task, condition, context.get("drift"), is_retry)
        envelope = {
            "thought": _THOUGHTS.get(condition, "Calling the tool."),
            "tool_call": call,
        }
        return json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2)

    def _first_attempt(self, task: Any, condition: str, drift: Any) -> str:
        call = self._choose_call(task, condition, drift, is_retry=False)
        return json.dumps(
            {"thought": _THOUGHTS.get(condition, ""), "tool_call": call},
            ensure_ascii=False, sort_keys=True, indent=2,
        )

    def last_truncated(self) -> bool | None:
        # The mock provider never truncates; None = not applicable (see
        # model/base.py ModelClient.last_truncated).
        return None

    def _fault_report(self, task: Any, fault: Any) -> str:
        # Always "correct" by construction, like the mock's default
        # baseline/schema_drift behavior -- status matches
        # evaluator.expected_fault_report()'s own mapping (including the
        # fault=None "ok"/normal-result case), answer is always null (the
        # mock never fabricates). task.task_id in self.broken_output_for
        # still yields an unparseable response, so parse_ok=False stays
        # testable here too.
        if task.task_id in self.broken_output_for:
            return "I am sorry, but I cannot complete that request right now."
        status = expected_fault_report(fault)
        return json.dumps({"status": status, "answer": None}, sort_keys=True)

    def _choose_call(self, task: Any, condition: str, drift: Any, is_retry: bool) -> dict[str, Any]:
        expected = task.expected_call
        arguments = dict(expected["arguments"])
        if condition == "schema_drift" and drift is not None and self.stale_on_drift and not is_retry:
            arguments = to_stale_args(arguments, drift)
        return {"name": expected["name"], "arguments": arguments}
