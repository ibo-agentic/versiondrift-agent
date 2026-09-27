"""Extract a structured tool call from raw model text.

Accepts either a bare call object ({"name": ..., "arguments": {...}}) or an
envelope containing a "tool_call" key. Returns None when nothing parseable is
found — a first-class outcome the evaluator scores as parse_ok = False.
"""

from __future__ import annotations

import json
from typing import Any


def extract_tool_call(raw: str) -> dict[str, Any] | None:
    """Return {"name": str, "arguments": dict} or None if unparseable."""
    for candidate in _json_candidates(raw):
        call = _normalize(candidate)
        if call is not None:
            return call
    return None


def _json_candidates(raw: str):
    """Yield every top-level JSON object found in the text, left to right."""
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(raw[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            yield obj


def _normalize(obj: dict[str, Any]) -> dict[str, Any] | None:
    if "tool_call" in obj and isinstance(obj["tool_call"], dict):
        return _normalize(obj["tool_call"])
    name = obj.get("name")
    arguments = obj.get("arguments")
    if isinstance(name, str) and isinstance(arguments, dict):
        return {"name": name, "arguments": arguments}
    return None
