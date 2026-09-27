"""Schema-drift perturbations, simulating a tool upgrade that changed its API.

A drift is chosen per (task, condition) from a seeded RNG, then:
- ``drifted_schema`` produces the new argument schema the upgraded tool
  advertises (shown in the prompt and used by the executor for validation),
- ``to_stale_args`` renders what a stale agent (built pre-upgrade) would emit,
- ``to_canonical_args`` maps an adapted call back to canonical names/values so
  the mock handlers can execute it (the "compatibility shim" role),
- ``compatible`` decides whether parsed arguments are semantically correct in
  the drifted schema's space (adapted) even if not byte-identical to expected.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Any

# Per-tool drift candidates. Only types listed in the config are eligible,
# and one candidate is picked per record by a seeded RNG.
_SPECS: dict[str, list[dict[str, Any]]] = {
    "get_weather": [
        {"type": "field_rename", "field": "unit", "new_name": "units"},
        {
            "type": "enum_drift",
            "field": "unit",
            "old_to_new": {"celsius": "c", "fahrenheit": "f"},
            "new_enum": ["c", "f"],
        },
        {
            "type": "unexpected_field",
            "field": "include_humidity",
            "spec": {"type": "boolean", "required": True, "default": True},
        },
    ],
    "calculator": [
        {"type": "field_rename", "field": "expression", "new_name": "expr"},
    ],
    "get_time": [
        {"type": "field_rename", "field": "timezone", "new_name": "tz"},
    ],
    "convert_units": [
        {"type": "field_rename", "field": "value", "new_name": "amount"},
        {"type": "type_mutation", "field": "value", "new_type": "string"},
    ],
    "search_docs": [
        {"type": "field_rename", "field": "query", "new_name": "q"},
        {"type": "field_rename", "field": "top_k", "new_name": "limit"},
        {"type": "field_drop", "field": "top_k"},
        {"type": "type_mutation", "field": "top_k", "new_type": "string"},
    ],
    "get_stock_price": [
        {"type": "field_rename", "field": "symbol", "new_name": "ticker"},
    ],
}


@dataclass(frozen=True)
class Drift:
    type: str
    tool: str
    field: str
    params: dict[str, Any] = field(default_factory=dict)


def apply(
    tool_name: str,
    enabled_types: list[str],
    rng: random.Random,
    preferred_type: str | None = None,
) -> Drift | None:
    """Pick one applicable drift for the tool, or None if nothing applies.

    ``preferred_type`` is a per-task stratification hint: when the tool has a
    candidate of that type it is used (the seeded RNG still makes the pick, so
    behavior stays reproducible); otherwise the choice falls back to all
    applicable candidates.
    """
    candidates = [
        spec for spec in _SPECS.get(tool_name, []) if spec["type"] in enabled_types
    ]
    if not candidates:
        return None
    if preferred_type is not None:
        preferred = [c for c in candidates if c["type"] == preferred_type]
        if preferred:
            candidates = preferred
    spec = rng.choice(candidates)
    params = {k: v for k, v in spec.items() if k not in ("type", "field")}
    return Drift(type=spec["type"], tool=tool_name, field=spec["field"], params=params)


def drifted_schema(schema: dict[str, Any], drift: Drift | None) -> dict[str, Any]:
    """Return the post-upgrade schema for the given drift (original untouched)."""
    new_schema = copy.deepcopy(schema)
    if drift is None:
        return new_schema
    args = new_schema["args"]
    if drift.type == "field_rename":
        args[drift.params["new_name"]] = args.pop(drift.field)
    elif drift.type == "field_drop":
        args.pop(drift.field, None)
    elif drift.type == "type_mutation":
        args[drift.field]["type"] = drift.params["new_type"]
    elif drift.type == "unexpected_field":
        args[drift.field] = copy.deepcopy(drift.params["spec"])
    elif drift.type == "enum_drift":
        args[drift.field]["enum"] = list(drift.params["new_enum"])
    return new_schema


def to_stale_args(arguments: dict[str, Any], drift: Drift | None) -> dict[str, Any]:
    """Arguments a stale agent emits: canonical pre-upgrade names/values."""
    stale = dict(arguments)
    if drift is not None and drift.type == "unexpected_field":
        stale.pop(drift.field, None)
    return stale


def to_canonical_args(arguments: dict[str, Any], drift: Drift | None) -> dict[str, Any]:
    """Map an adapted call back to canonical names/values for the mock handlers."""
    canonical = dict(arguments)
    if drift is None:
        return canonical
    if drift.type == "field_rename":
        new_name = drift.params["new_name"]
        if new_name in canonical:
            canonical[drift.field] = canonical.pop(new_name)
    elif drift.type == "enum_drift":
        value = canonical.get(drift.field)
        old_to_new: dict[str, Any] = drift.params["old_to_new"]
        for old, new in old_to_new.items():
            if value == new:
                canonical[drift.field] = old
    return canonical


def to_new_space(arguments: dict[str, Any], drift: Drift | None) -> dict[str, Any]:
    """Normalize arguments into the drifted schema's space for comparison."""
    args = dict(arguments)
    if drift is None:
        return args
    if drift.type == "field_rename":
        new_name = drift.params["new_name"]
        if drift.field in args:
            args[new_name] = args.pop(drift.field)
    elif drift.type == "field_drop":
        args.pop(drift.field, None)
    elif drift.type == "type_mutation":
        if drift.field in args:
            args[drift.field] = str(args[drift.field])
    elif drift.type == "enum_drift":
        value = args.get(drift.field)
        old_to_new: dict[str, Any] = drift.params["old_to_new"]
        if value in old_to_new:
            args[drift.field] = old_to_new[value]
    return args


def compatible(parsed: dict[str, Any], expected: dict[str, Any], drift: Drift | None) -> bool:
    """True if parsed arguments are correct in the drifted schema's space."""
    parsed_new = to_new_space(parsed, drift)
    expected_new = to_new_space(expected, drift)
    if drift is not None and drift.type == "unexpected_field":
        # The new required field may be absent in a pre-upgrade call; judge only
        # the arguments that exist in the canonical expectation.
        return all(parsed_new.get(k) == v for k, v in expected_new.items())
    return parsed_new == expected_new
