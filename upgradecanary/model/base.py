"""Model client interface shared by the mock stub and real backends."""

from __future__ import annotations

from typing import Any, Protocol


class ModelClient(Protocol):
    """Anything that turns a prompt into raw text.

    ``context`` carries the structured experiment state (task, condition, drift,
    retry feedback). Real backends ignore it; the mock client uses it to behave
    deterministically. Keeping it in the signature means both backends are
    drop-in interchangeable.
    """

    def generate(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        ...
