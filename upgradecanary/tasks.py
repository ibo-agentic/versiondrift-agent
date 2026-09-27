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
        )
        for row in rows
    ]
    ids = [t.task_id for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate task_id values in task file.")
    return tasks
