"""Task model and loader.

A task is a fully specified contract: prompt, target tool, and the exact tool
call the agent is expected to produce. The evaluator scores against
``expected_call`` with pure comparisons — no LLM judge anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .utils import read_jsonl


@dataclass(frozen=True)
class Task:
    task_id: str
    prompt: str
    tool: str
    expected_call: dict[str, Any]
    condition_tags: list[str] = field(default_factory=list)
    # Optional stratification hint: prefer this schema-drift type for the
    # schema_drift condition (must be applicable to the tool; falls back to a
    # seeded RNG choice when absent or inapplicable).
    drift_type: str | None = None
    # Task-suite marker. "synthetic" (default) uses the global BASE_SCHEMAS;
    # "bfcl" carries its own schemas below (UpgradeCanary-BFCL-100).
    suite: str = "synthetic"
    tool_schema: dict[str, Any] | None = None      # BFCL-native function doc (the CORRECT tool)
    internal_schema: dict[str, Any] | None = None  # converted canonical schema (the CORRECT tool)
    acceptable: dict[str, Any] | None = None       # acceptable values per arg
    source_id: str | None = None                   # upstream task id
    # BFCL "multiple" category (PLAN.md 10.1 item 3): every candidate tool
    # shown to the model, as BFCL-native function docs, INCLUDING the
    # correct one (tool_schema is always one of these entries, matched by
    # name at prompt-build time). None for every other task (synthetic and
    # BFCL "simple_python") -- those show exactly one tool, as before.
    # Only the correct tool's schema (tool_schema/internal_schema) is ever
    # drift-perturbed or scored against; distractors render verbatim.
    candidate_schemas: list[dict[str, Any]] | None = None


def load_tasks(path: str | Path) -> list[Task]:
    rows = read_jsonl(path)
    tasks = [
        Task(
            task_id=row["task_id"],
            prompt=row["prompt"],
            tool=row["tool"],
            expected_call=row["expected_call"],
            condition_tags=row.get("condition_tags", []),
            drift_type=row.get("drift_type"),
            suite=row.get("suite", "synthetic"),
            tool_schema=row.get("tool_schema"),
            internal_schema=row.get("internal_schema"),
            acceptable=row.get("acceptable"),
            source_id=row.get("source_id"),
            candidate_schemas=row.get("candidate_schemas"),
        )
        for row in rows
    ]
    ids = [t.task_id for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate task_id values in task file.")
    return tasks
