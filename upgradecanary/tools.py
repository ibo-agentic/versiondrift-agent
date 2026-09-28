"""Mock tool registry and executor.

Handlers are pure, canned, and deterministic: the same arguments always yield
the same result. The executor validates calls against a (possibly drifted)
schema, maps adapted arguments back to canonical form, invokes the handler,
and wraps the outcome with any injected runtime fault.
"""

from __future__ import annotations

import ast
import operator
from typing import Any

from .perturbations.runtime_faults import Fault, apply_fault
from .perturbations.schema_drift import Drift, to_canonical_args

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}

# Canonical (pre-upgrade) schemas. Keep in sync with data/base_tasks.jsonl.
BASE_SCHEMAS: dict[str, dict[str, Any]] = {
    "get_weather": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "args": {
            "city": {"type": "string", "required": True},
            "unit": {"type": "string", "required": True, "enum": ["celsius", "fahrenheit"]},
        },
    },
    "calculator": {
        "name": "calculator",
        "description": "Evaluate an arithmetic expression.",
        "args": {
            "expression": {"type": "string", "required": True},
        },
    },
    "get_time": {
        "name": "get_time",
        "description": "Get the current time in a timezone.",
        "args": {
            "timezone": {"type": "string", "required": True},
        },
    },
    "convert_units": {
        "name": "convert_units",
        "description": "Convert a numeric value between units.",
        "args": {
            "value": {"type": "number", "required": True},
            "from_unit": {"type": "string", "required": True},
            "to_unit": {"type": "string", "required": True},
        },
    },
    "search_docs": {
        "name": "search_docs",
        "description": "Search the documentation index.",
        "args": {
            "query": {"type": "string", "required": True},
            "top_k": {"type": "integer", "required": False},
        },
    },
    "get_stock_price": {
        "name": "get_stock_price",
        "description": "Get the latest price for a stock symbol.",
        "args": {
            "symbol": {"type": "string", "required": True},
        },
    },
}


def list_tools() -> list[str]:
    return sorted(BASE_SCHEMAS)


def validate_call(
    name: str,
    arguments: dict[str, Any],
    schema: dict[str, Any],
    strict: bool,
) -> list[str]:
    """Validate a call against a (possibly drifted) schema; returns problems."""
    problems: list[str] = []
    if name != schema["name"]:
        return [f"unknown tool '{name}' (expected '{schema['name']}')"]
    declared = schema["args"]
    unknown = sorted(set(arguments) - set(declared))
    if unknown and strict:
        problems.append(f"unknown arguments: {unknown}")
    for arg, spec in declared.items():
        if spec.get("required") and arg not in arguments:
            problems.append(f"missing required argument '{arg}'")
    for arg, value in arguments.items():
        if arg not in declared:
            continue
        spec = declared[arg]
        type_name = spec.get("type")
        if type_name and not _TYPE_CHECKS[type_name](value):
            problems.append(
                f"argument '{arg}' expected type {type_name}, got {type(value).__name__}"
            )
        if spec.get("enum") and value not in spec["enum"]:
            problems.append(f"argument '{arg}' value {value!r} not in enum {spec['enum']}")
    return problems


def execute(
    call: dict[str, Any],
    schema: dict[str, Any],
    drift: Drift | None,
    fault: Fault | None,
    strict: bool,
) -> dict[str, Any]:
    """Validate, canonicalize, invoke the handler, and apply the fault."""
    name = call.get("name", "")
    arguments = call.get("arguments", {})
    problems = validate_call(name, arguments, schema, strict)
    if problems:
        return {"ok": False, "error": {"type": "validation", "problems": problems}}
    canonical = to_canonical_args(arguments, drift, BASE_SCHEMAS.get(name))
    result = HANDLERS[name](**canonical)
    return apply_fault(name, result, fault)


# --- deterministic canned handlers -----------------------------------------

_WEATHER = {
    "Berlin": (21.0, "sunny"),
    "Phoenix": (38.5, "hot and clear"),
    "Tokyo": (24.0, "light rain"),
}
_TIMES = {
    "Europe/Paris": "2025-01-15T14:30:00+01:00",
    "Asia/Tokyo": "2025-01-15T22:30:00+09:00",
    "America/New_York": "2025-01-15T08:30:00-05:00",
}
_UNIT_FACTORS = {
    ("km", "mi"): 0.621371,
    ("mi", "km"): 1.60934,
    ("kg", "lb"): 2.20462,
    ("lb", "kg"): 0.453592,
}
_DOCS = {
    "vector index compaction": [
        "Compaction scheduling in LSM trees",
        "Vector index maintenance playbook",
        "Segment merge strategies",
    ],
    "write amplification": [
        "Write amplification in LSM storage",
        "Tuning flush thresholds",
        "Compaction score deep dive",
    ],
}
_PRICES = {"ACME": 142.5, "GLOB": 87.25}


def _get_weather(city: str, unit: str = "celsius") -> dict[str, Any]:
    temp_c, conditions = _WEATHER[city]
    temp = temp_c if unit == "celsius" else round(temp_c * 9 / 5 + 32, 1)
    return {"city": city, "temp": temp, "unit": unit, "conditions": conditions}


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def _safe_eval(expression: str):
    node = ast.parse(expression, mode="eval").body

    def ev(n: ast.AST):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN_OPS:
            return _BIN_OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UNARY_OPS:
            return _UNARY_OPS[type(n.op)](ev(n.operand))
        raise ValueError(f"unsupported expression element: {ast.dump(n)}")

    return ev(node)


def _calculator(expression: str) -> dict[str, Any]:
    return {"expression": expression, "result": _safe_eval(expression)}


def _get_time(timezone: str) -> dict[str, Any]:
    return {"timezone": timezone, "time": _TIMES[timezone]}


def _convert_units(value: float, from_unit: str, to_unit: str) -> dict[str, Any]:
    if (from_unit, to_unit) not in _UNIT_FACTORS:
        raise ValueError(f"unsupported conversion {from_unit!r} -> {to_unit!r}")
    return {
        "value": value,
        "from_unit": from_unit,
        "to_unit": to_unit,
        "converted": round(value * _UNIT_FACTORS[(from_unit, to_unit)], 4),
    }


def _search_docs(query: str, top_k: int = 3) -> dict[str, Any]:
    return {"query": query, "results": _DOCS.get(query, [])[:top_k]}


def _get_stock_price(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "price": _PRICES[symbol],
        "currency": "USD",
        "as_of": "2025-01-15T13:00:00+00:00",
    }


HANDLERS = {
    "get_weather": _get_weather,
    "calculator": _calculator,
    "get_time": _get_time,
    "convert_units": _convert_units,
    "search_docs": _search_docs,
    "get_stock_price": _get_stock_price,
}
