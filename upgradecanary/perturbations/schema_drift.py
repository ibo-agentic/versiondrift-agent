"""Schema-drift perturbations, simulating a tool upgrade that changed its API.

A drift is chosen per (task, condition) from a seeded RNG, then:
- ``drifted_schema`` produces the new argument schema the upgraded tool
  advertises (shown in the prompt and used for validation),
- ``to_stale_args`` renders what a stale agent (built pre-upgrade) would emit,
- ``to_canonical_args`` maps an adapted call back to canonical form for the
  mock handlers: inverse rename/enum mapping, safe coercion of drifted string
  values to canonical types ("3" -> 3), and dropping drift-only fields the
  original handler does not accept,
- ``compatible`` decides whether parsed arguments are semantically correct in
  the drifted schema's space. Intent matching uses per-argument semantic
  equality: calculator expressions count as equal when mathematically
  equivalent (AST-based, never eval()); ``args_exact`` elsewhere remains
  byte-strict.
"""

from __future__ import annotations

import ast
import copy
import operator
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


# --- arithmetic equivalence for calculator expressions ----------------------
# Intent matching treats mathematically equivalent expressions as equal
# (e.g. "7*3+11" vs "7 * 3 + 11"). Pure AST walking — never eval().

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval_arithmetic(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval_arithmetic(node.left), _eval_arithmetic(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_arithmetic(node.operand))
    raise ValueError(f"unsupported expression element: {ast.dump(node)}")


def arithmetic_value(expression: str) -> Any:
    """Value of a basic arithmetic expression, evaluated via AST."""
    return _eval_arithmetic(ast.parse(expression, mode="eval").body)


def expressions_equivalent(a: str, b: str) -> bool | None:
    """True/False when both are basic arithmetic with equal value; None when
    either side is not evaluable arithmetic (callers fall back to equality)."""
    try:
        return arithmetic_value(a) == arithmetic_value(b)
    except Exception:
        return None


def _value_matches(key: str, parsed: Any, expected: Any) -> bool:
    """Per-argument semantic equality used by intent matching."""
    if key == "expression" and isinstance(parsed, str) and isinstance(expected, str):
        eq = expressions_equivalent(parsed, expected)
        if eq is not None:
            return eq
    return parsed == expected


def _args_match(parsed: dict[str, Any], expected: dict[str, Any]) -> bool:
    if set(parsed) != set(expected):
        return False
    return all(_value_matches(k, parsed[k], expected[k]) for k in expected)


@dataclass(frozen=True)
class Drift:
    type: str
    tool: str
    field: str
    params: dict[str, Any] = field(default_factory=dict)


def generate_specs_from_schema(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive drift candidates from any canonical schema by fixed rules.

    Used for tools without hand-written specs (e.g. BFCL-derived tasks). Only
    drift types that need no semantic knowledge of the tool are generated —
    never enum_drift, which requires real enums the schema may not have.
    """
    args = schema.get("args", {})
    specs: list[dict[str, Any]] = []
    required = sorted(k for k, s in args.items() if s.get("required"))
    optional = sorted(k for k, s in args.items() if not s.get("required"))
    integers = sorted(k for k, s in args.items() if s.get("type") == "integer")
    if required:
        specs.append({"type": "field_rename", "field": required[0], "new_name": f"{required[0]}_v2"})
    elif args:
        first = sorted(args)[0]
        specs.append({"type": "field_rename", "field": first, "new_name": f"{first}_v2"})
    if optional:
        specs.append({"type": "field_drop", "field": optional[0]})
    if integers:
        specs.append({"type": "type_mutation", "field": integers[0], "new_type": "string"})
    specs.append(
        {
            "type": "unexpected_field",
            "field": "verbose",
            "spec": {"type": "boolean", "required": True, "default": True},
        }
    )
    return specs


def apply(
    tool_name: str,
    enabled_types: list[str],
    rng: random.Random,
    preferred_type: str | None = None,
    schema: dict[str, Any] | None = None,
) -> Drift | None:
    """Pick one applicable drift for the tool, or None if nothing applies.

    ``preferred_type`` is a per-task stratification hint: when the tool has a
    candidate of that type it is used (the seeded RNG still makes the pick, so
    behavior stays reproducible); otherwise the choice falls back to all
    applicable candidates. Tools without hand-written specs (e.g. BFCL tasks)
    get candidates derived from ``schema`` by fixed rules.
    """
    candidates = [
        spec for spec in _SPECS.get(tool_name, []) if spec["type"] in enabled_types
    ]
    if not candidates and schema is not None:
        candidates = [
            spec for spec in generate_specs_from_schema(schema) if spec["type"] in enabled_types
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


def to_canonical_args(
    arguments: dict[str, Any],
    drift: Drift | None,
    schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map an adapted call back to canonical form for the mock handlers.

    Applies the inverse of the drift (renames, enum values), then — when the
    canonical schema is provided — drops drift-only fields the original
    handler does not accept and coerces semantically equal values back to the
    canonical types (e.g. "3" -> 3) when the conversion is unambiguous.
    """
    canonical = dict(arguments)
    if drift is not None:
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
    if schema is None:
        return canonical
    canonical = {k: v for k, v in canonical.items() if k in schema["args"]}
    for arg, spec in schema["args"].items():
        if arg in canonical:
            canonical[arg] = _coerce_to_type(canonical[arg], spec.get("type"))
    return canonical


def _coerce_to_type(value: Any, type_name: str | None) -> Any:
    """Convert a drifted string value to the canonical type when unambiguous."""
    if not isinstance(value, str):
        return value
    if type_name == "integer":
        try:
            return int(value)
        except ValueError:
            return value
    if type_name == "number":
        try:
            number = float(value)
        except ValueError:
            return value
        return int(number) if number.is_integer() else number
    if type_name == "boolean":
        if value == "true":
            return True
        if value == "false":
            return False
    return value


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


def _canonical_key(key: str, drift: Drift | None) -> str:
    """Map a drifted-space key back to its canonical argument name."""
    if drift is not None and drift.type == "field_rename":
        if key == drift.params["new_name"]:
            return drift.field
    return key


def _value_acceptable(parsed_val: Any, acceptable_vals: list[Any]) -> bool:
    """Membership in the acceptable set, tolerant to drift-space type coercion
    (e.g. type_mutation comparing "5" against [5])."""
    if parsed_val in acceptable_vals:
        return True
    as_str = str(parsed_val)
    return any(as_str == str(v) for v in acceptable_vals)


def _acceptable_intent(
    parsed_new: dict[str, Any],
    expected_new: dict[str, Any],
    drift: Drift | None,
    acceptable: dict[str, list[Any]],
    active_schema: dict[str, Any] | None,
) -> bool:
    """BFCL-aware intent: canonical-name comparison with omission tolerance.

    - every expected parameter must be present with an acceptable value, or
      omitted when its acceptable set contains "" (BFCL omission semantics);
    - extra arguments are tolerated only when schema-declared or part of the
      task's acceptable map (a known ground-truth parameter, e.g. one dropped
      by a field_drop drift) — undeclared hallucinated arguments fail intent.
    """
    parsed_c = {_canonical_key(k, drift): v for k, v in parsed_new.items()}
    expected_c = {_canonical_key(k, drift): v for k, v in expected_new.items()}
    declared = (active_schema or {}).get("args", {})
    for key in parsed_c:
        if key not in expected_c and key not in declared and key not in acceptable:
            return False
    for pname, vals in acceptable.items():
        if pname not in expected_c:
            continue  # canonically absent (e.g. dropped by field_drop drift)
        if pname in parsed_c:
            if not _value_acceptable(parsed_c[pname], vals):
                return False
        elif "" not in vals:
            return False  # omission not permitted by BFCL semantics
    return True


def compatible(
    parsed: dict[str, Any],
    expected: dict[str, Any],
    drift: Drift | None,
    acceptable: dict[str, list[Any]] | None = None,
    active_schema: dict[str, Any] | None = None,
) -> bool:
    """True if parsed arguments are semantically correct in the drifted
    schema's space (see _value_matches for per-argument semantics).

    Keys are mapped back to canonical names before per-argument comparison, so
    semantic rules keyed on the canonical argument (arithmetic equivalence for
    calculator expressions) apply even when a drift renamed the argument
    (``expression`` -> ``expr``). When ``acceptable`` is provided (BFCL-derived
    tasks), BFCL acceptable-values semantics apply instead of exact matching;
    when it is None (synthetic suite), behavior is exactly as before.
    """
    parsed_new = to_new_space(parsed, drift)
    expected_new = to_new_space(expected, drift)
    if acceptable is not None:
        return _acceptable_intent(parsed_new, expected_new, drift, acceptable, active_schema)
    if drift is not None and drift.type == "unexpected_field":
        # The new required field may be absent in a pre-upgrade call; judge only
        # the arguments that exist in the canonical expectation.
        return all(
            _value_matches(_canonical_key(k, drift), parsed_new.get(k), v)
            for k, v in expected_new.items()
        )
    parsed_canon = {_canonical_key(k, drift): v for k, v in parsed_new.items()}
    expected_canon = {_canonical_key(k, drift): v for k, v in expected_new.items()}
    return _args_match(parsed_canon, expected_canon)
