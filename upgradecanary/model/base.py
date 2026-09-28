"""Model client interface shared by the mock stub and real backends."""

from __future__ import annotations

from typing import Any, Protocol


class ModelClient(Protocol):
    """Anything that turns a prompt into raw text.

    ``context`` carries the structured experiment state (task, condition, drift,
    retry feedback). Real backends ignore it; the mock client uses it to behave
    deterministically. ``temperature``/``seed`` override the client's defaults
    for a single call (repeated trials); llama-cpp-python honors per-call
    seeding (best-effort on GPU).
    """

    def generate(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        *,
        temperature: float | None = None,
        seed: int | None = None,
    ) -> str:
        ...
