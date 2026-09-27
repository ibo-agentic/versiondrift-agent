"""Runtime-fault perturbations injected at the executor level.

Faults simulate a degraded tool backend: timeouts, exceptions, empty or
truncated payloads, and stale cached responses. Retryable faults trigger one
agent retry when ``retry_once`` is set in the config; ``stale_result`` is not
retryable (the call technically succeeds) — detecting staleness needs a real
model and is left for later phases.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

RETRYABLE = ("timeout", "tool_exception", "empty_result", "partial_result")

# Fixed timestamp so fault outputs are byte-identical across runs.
STALE_AS_OF = "2024-11-02T09:00:00+00:00"


@dataclass(frozen=True)
class Fault:
    type: str
    params: dict[str, Any] = field(default_factory=dict)


def choose(enabled: list[str], rng: random.Random) -> Fault | None:
    """Pick one enabled fault type (sorted list keeps choice order-stable)."""
    if not enabled:
        return None
    return Fault(type=rng.choice(sorted(enabled)))


def is_retryable(fault: Fault | None) -> bool:
    return fault is not None and fault.type in RETRYABLE


def apply_fault(tool_name: str, result: Any, fault: Fault | None) -> dict[str, Any]:
    """Wrap a successful handler result or replace it with a fault outcome."""
    if fault is None:
        return {"ok": True, "result": result}
    if fault.type == "timeout":
        return {
            "ok": False,
            "error": {"type": "timeout", "message": f"{tool_name} timed out after 30s"},
            "simulated_latency_ms": 30000,
        }
    if fault.type == "tool_exception":
        return {
            "ok": False,
            "error": {
                "type": "exception",
                "message": f"{tool_name} raised RuntimeError: internal checkpoint corrupted",
            },
        }
    if fault.type == "empty_result":
        return {
            "ok": False,
            "error": {"type": "empty_result", "message": f"{tool_name} returned an empty payload"},
        }
    if fault.type == "partial_result":
        missing = sorted(result.keys())[0] if isinstance(result, dict) and result else None
        return {
            "ok": False,
            "error": {
                "type": "partial_result",
                "message": "response payload truncated by gateway",
                "missing_keys": [missing] if missing else [],
            },
        }
    if fault.type == "stale_result":
        return {
            "ok": True,
            "stale": True,
            "as_of": STALE_AS_OF,
            "note": "served from cache",
            "result": result,
        }
    raise ValueError(f"Unknown fault type: {fault.type}")
