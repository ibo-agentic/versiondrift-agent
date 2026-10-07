"""Model client interface shared by the mock stub and real backends."""

from __future__ import annotations

from typing import Any, Protocol


class ModelClient(Protocol):
    """Anything that turns a prompt into raw text.

    ``context`` carries the structured experiment state (task, condition, drift,
    retry feedback). Real backends ignore it; the mock client uses it to behave
    deterministically. ``temperature``/``seed`` override the client's defaults
    for a single call (repeated trials); llama-cpp-python honors per-call
    seeding (best-effort on GPU). ``tools``/``response_schema`` are optional
    (PLAN.md F3/F4): ``tools`` is an OpenAI-style tool-list, used only under
    ``chat_wrapping: native`` + ``prompt_format: native``; ``response_schema``
    is a JSON Schema dict used to build a constrained-decoding grammar
    (PLAN.md F4 generic_json/full_schema). ``top_p``/``top_k``/``min_p``/
    ``repeat_penalty`` override the client's own sampling defaults for a
    single call, same per-call pattern as ``temperature``/``seed`` (PLAN.md
    F6: lets the greedy trial keep the client's base sampling config even
    when other trials use a model-specific recommended preset). Clients
    that don't support any of these must accept and ignore them, never
    error, so existing call sites that omit them keep working unchanged.
    """

    def generate(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        *,
        temperature: float | None = None,
        seed: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        min_p: float | None = None,
        repeat_penalty: float | None = None,
    ) -> str:
        ...

    def last_truncated(self) -> bool | None:
        """Whether the most recent ``generate`` call hit max_tokens.

        None = unknown / not applicable (e.g. the mock client, or a backend
        that does not report a finish reason). Added for the 2026-10-02
        audit follow-up; callers must treat None as "no information",
        never as False.
        """
        ...
