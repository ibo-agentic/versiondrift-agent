"""Extract a structured tool call from raw model text.

Accepts either a bare call object ({"name": ..., "arguments": {...}}) or an
envelope containing a "tool_call" key. Returns None when nothing parseable is
found — a first-class outcome the evaluator scores as parse_ok = False.

Two optional, OFF-BY-DEFAULT preprocessing steps (added for the 2026-10-02
audit follow-up; default behavior is byte-identical to before, so every
existing result remains reproducible from its config unchanged):

- ``strip_think``: remove a *complete* ``<think>...</think>`` block before
  scanning for JSON. Only a well-formed (both tags present) block is
  stripped; a truncated/unclosed block is left as-is (so a truncation
  failure still shows up as a parse failure, not as a silent fix).
- ``lenient``: if strict extraction finds nothing, retry once after
  repairing invalid JSON backslash-escapes (e.g. ``\\_`` -> ``_``), via
  ``_repair_invalid_escapes``. Strict (``lenient=False``) remains the
  default and the metric used for every score in this project; lenient
  extraction is a diagnostic mode only (see analysis/audit/escape_check.md).
"""

from __future__ import annotations

import json
import re
from typing import Any

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

# Valid characters after a backslash in JSON string literals (RFC 8259).
_VALID_ESCAPES = set('"\\/bfnrtu')


def strip_think_block(raw: str) -> str:
    """Remove a complete <think>...</think> block, if present. Leaves a
    truncated (unclosed) block untouched."""
    return _THINK_BLOCK_RE.sub("", raw)


def _repair_invalid_escapes(text: str) -> str:
    """Drop the backslash from any backslash-escape that JSON does not
    allow (e.g. ``\\_`` -> ``_``). Valid escapes are left untouched, so this
    can only turn an unparseable string into a parseable one -- never the
    reverse."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n and text[i + 1] not in _VALID_ESCAPES:
            out.append(text[i + 1])
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def extract_tool_call(
    raw: str,
    *,
    strip_think: bool = False,
    lenient: bool = False,
) -> dict[str, Any] | None:
    """Return {"name": str, "arguments": dict} or None if unparseable.

    ``strip_think``/``lenient`` default to False, matching the original,
    unconditional behavior used by every result in this project to date.
    """
    text = strip_think_block(raw) if strip_think else raw
    call = _extract(text)
    if call is not None or not lenient:
        return call
    return _extract(_repair_invalid_escapes(text))


def _extract(raw: str) -> dict[str, Any] | None:
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


_FAULT_REPORT_STATUSES = {"ok", "failed", "incomplete"}


def extract_fault_report(
    raw: str,
    *,
    strip_think: bool = False,
    lenient: bool = False,
) -> dict[str, Any] | None:
    """PLAN.md's fault_reporting condition: extract
    ``{"status": "ok"|"failed"|"incomplete", "answer": <string or null>}``
    from raw model text. Returns None if unparseable or if ``status`` is
    not one of the three allowed values (an unparseable/invalid report is a
    first-class outcome, scored as parse_ok=False, exactly like
    ``extract_tool_call``). ``strip_think``/``lenient`` mirror
    ``extract_tool_call``'s options, same defaults (off).
    """
    text = strip_think_block(raw) if strip_think else raw
    report = _extract_fault_report(text)
    if report is not None or not lenient:
        return report
    return _extract_fault_report(_repair_invalid_escapes(text))


def _extract_fault_report(raw: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(raw[i:])
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        status = obj.get("status")
        if status in _FAULT_REPORT_STATUSES and "answer" in obj:
            answer = obj["answer"]
            if answer is None or isinstance(answer, str):
                return {"status": status, "answer": answer}
    return None
