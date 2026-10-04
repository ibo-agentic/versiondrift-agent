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
    See ``extract_tool_call_with_format`` for the native-tool-call-format
    detection/logging variant (PLAN.md F3 follow-up, 2026-10-04); this
    function is a thin wrapper that discards the format label.
    """
    call, _format_name = extract_tool_call_with_format(raw, strip_think=strip_think, lenient=lenient)
    return call


# PLAN.md F3 follow-up (2026-10-04): native tool-calling output formats,
# verified against each model family's own tokenizer_config.json/chat
# template rather than assumed -- see docs/ENGINEERING_NOTES.md for the
# source quoted per format. Order matters: more specific tag checks run
# before the generic untagged scan, and the paired Phi-4-mini tag is
# checked before the prefix-only Granite tag (they share the same opening
# literal, "<|tool_call|>").
_QWEN_TAG_RE = re.compile(r"<tool_call>")
_MISTRAL_TAG_RE = re.compile(r"\[TOOL_CALLS\]")
_PHI4_PAIRED_TAG_RE = re.compile(r"<\|tool_call\|>.*?<\|/tool_call\|>", re.DOTALL)
_GRANITE_TAG_RE = re.compile(r"<\|tool_call\|>")


def _detect_native_format(raw: str) -> str | None:
    """Which documented native tool-call tag (if any) is present in the raw
    text. Purely a label for logging/diagnostics -- extraction itself scans
    the whole text regardless of tags (see _call_candidates), since the
    tag's surrounding text is simply ignored by the object/array scanner.
    Returns None when no recognized tag is present (plain untagged JSON,
    or an unparseable/unrelated response)."""
    if _QWEN_TAG_RE.search(raw):
        return "qwen_tool_call_tag"
    if _MISTRAL_TAG_RE.search(raw):
        return "mistral_tool_calls_tag"
    if _PHI4_PAIRED_TAG_RE.search(raw):
        return "phi4_tool_call_tag"
    if _GRANITE_TAG_RE.search(raw):
        return "granite_tool_call_tag"
    return None


def extract_tool_call_with_format(
    raw: str,
    *,
    strip_think: bool = False,
    lenient: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    """Like ``extract_tool_call``, but also returns which format was
    detected: one of the four tagged native formats
    (``"qwen_tool_call_tag"``, ``"mistral_tool_calls_tag"``,
    ``"phi4_tool_call_tag"``, ``"granite_tool_call_tag"``), ``"list_wrapped"``
    (a top-level JSON array, untagged), ``"parameters_alias"`` (a bare
    object using ``"parameters"`` instead of ``"arguments"``, Llama 3.1
    style), ``"bare_json"`` (the original ``{"name","arguments"}``/
    ``{"tool_call": {...}}`` shape this project always supported), or
    ``None`` (nothing parseable found, regardless of whether a tag was
    detected -- a detected tag with unparseable content inside it is still
    reported, since that's diagnostically useful, but the call is None).
    """
    text = strip_think_block(raw) if strip_think else raw
    detected_tag = _detect_native_format(text)
    call, shape = _extract_with_shape(text)
    if call is None and lenient:
        call, shape = _extract_with_shape(_repair_invalid_escapes(text))
    if call is None:
        return None, detected_tag
    return call, detected_tag or shape


def _extract_with_shape(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    for candidate, base_shape in _call_candidates(raw):
        call, used_parameters_alias = _normalize(candidate)
        if call is not None:
            shape = "parameters_alias" if used_parameters_alias else base_shape
            return call, shape
    return None, None


def _call_candidates(raw: str):
    """Yield every top-level JSON object OR array found in the text, left
    to right, tagged with a base shape label ("bare_json" for an object,
    "list_wrapped" for an array -- the caller may override this with a
    more specific tag label, or with "parameters_alias", once it knows
    which key/tag actually matched)."""
    decoder = json.JSONDecoder()
    for i, ch in enumerate(raw):
        if ch not in "{[":
            continue
        try:
            obj, _ = decoder.raw_decode(raw[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            yield obj, "bare_json"
        elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
            # A list-wrapped call (Mistral [TOOL_CALLS], Granite <|tool_call|>,
            # or an untagged list) -- only the first element is used; this
            # project's harness never asks for more than one call per turn.
            yield obj[0], "list_wrapped"


def _normalize(obj: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    """Returns (call, used_parameters_alias)."""
    if "tool_call" in obj and isinstance(obj["tool_call"], dict):
        return _normalize(obj["tool_call"])
    name = obj.get("name")
    arguments = obj.get("arguments")
    if isinstance(name, str) and isinstance(arguments, dict):
        return {"name": name, "arguments": arguments}, False
    # Llama 3.1 style: "parameters" instead of "arguments".
    parameters = obj.get("parameters")
    if isinstance(name, str) and isinstance(parameters, dict):
        return {"name": name, "arguments": parameters}, True
    return None, False


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
