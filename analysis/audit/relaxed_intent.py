"""Relaxed-intent diagnostic (audit follow-up, human spot-check analysis).

Reuses upgradecanary/perturbations/schema_drift.py's own canonicalization
helpers (to_new_space, _canonical_key, _value_acceptable, _value_matches)
UNCHANGED -- this module never imports or modifies the production
compatible()/_acceptable_intent() functions' source, it only calls their
building blocks and adds a parallel, more lenient final comparison, used
for diagnostics only. The official args_intent_match metric (and hence the
official score) is never touched.

Five leniencies, directly derived from the human spot-check
(intent_spotcheck_filled.csv, 8/8 disagreements all rule=False/human=yes):
  1. properties_wrapper : parsed == {"properties": {...}}; unwrap it.
  2. string_bool         : "true"/"false" string accepted where a bool
                           value is expected/acceptable.
  3. unit_number         : a string like "5m"/"6cm" accepted where the
                           bare number (5, 6) is expected/acceptable --
                           only when the suffix is alphabetic.
  4. unit_synonym        : a small, evidence-based map of distance/mass
                           unit spellings (mi<->mile(s), km<->kilometer(s),
                           kg<->kilogram(s), lb<->pound(s)/lbs) treated as
                           equal on either side of the comparison.
  5. swapped_symmetric   : two canonical argument keys sharing a common
                           stem with a trailing digit (teamN, colorN, ...)
                           whose values are exactly swapped relative to
                           expected are accepted as equal (order-
                           insensitive pair).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from upgradecanary.perturbations.schema_drift import (
    Drift,
    _canonical_key,
    _value_acceptable,
    _value_matches,
    to_new_space,
)

ALL_CAUSES = ("properties_wrapper", "string_bool", "unit_number", "unit_synonym", "swapped_symmetric")

_UNIT_SYNONYMS = {
    "mi": {"mi", "mile", "miles"},
    "km": {"km", "kilometer", "kilometers", "kilometre", "kilometres", "kms"},
    "kg": {"kg", "kilogram", "kilograms", "kgs"},
    "lb": {"lb", "lbs", "pound", "pounds"},
}
_SYNONYM_CANON = {syn: canon for canon, syns in _UNIT_SYNONYMS.items() for syn in syns}

_NUMBER_UNIT_RE = re.compile(r"^(-?\d+(?:\.\d+)?)([a-zA-Z]+)$")
_TRAILING_DIGIT_RE = re.compile(r"^(.*?)(\d+)$")


def _unwrap_properties(d: dict[str, Any]) -> dict[str, Any]:
    if isinstance(d, dict) and set(d.keys()) == {"properties"} and isinstance(d["properties"], dict):
        return d["properties"]
    return d


def _norm_value(v: Any, causes: set[str]) -> Any:
    if "string_bool" in causes and isinstance(v, str):
        low = v.strip().lower()
        if low == "true":
            return True
        if low == "false":
            return False
    if "unit_number" in causes and isinstance(v, str):
        m = _NUMBER_UNIT_RE.match(v.strip())
        if m:
            num = m.group(1)
            return float(num) if "." in num else int(num)
    if "unit_synonym" in causes and isinstance(v, str):
        key = v.strip().lower()
        if key in _SYNONYM_CANON:
            return _SYNONYM_CANON[key]
    return v


def _values_equal_relaxed(key: str, parsed_val: Any, target_val: Any, causes: set[str]) -> bool:
    if _value_matches(key, parsed_val, target_val):  # includes arithmetic equivalence for "expression"
        return True
    return _norm_value(parsed_val, causes) == _norm_value(target_val, causes)


def _acceptable_relaxed(parsed_val: Any, acceptable_vals: list[Any], causes: set[str]) -> bool:
    if _value_acceptable(parsed_val, acceptable_vals):
        return True
    pv = _norm_value(parsed_val, causes)
    return any(_norm_value(v, causes) == pv or _value_acceptable(pv, [v]) for v in acceptable_vals)


def _stem(key: str) -> tuple[str, str] | None:
    m = _TRAILING_DIGIT_RE.match(key)
    if m and m.group(1):
        return m.group(1), m.group(2)
    return None


def _apply_swap(parsed_c: dict[str, Any], expected_c: dict[str, Any], causes: set[str]) -> dict[str, Any]:
    """Try swapping each stem-paired pair of keys; keep the swap if it
    makes both members match expected (when they didn't before)."""
    if "swapped_symmetric" not in causes:
        return parsed_c
    stems: dict[str, list[str]] = {}
    for k in parsed_c:
        s = _stem(k)
        if s:
            stems.setdefault(s[0], []).append(k)
    out = dict(parsed_c)
    for base, keys in stems.items():
        if len(keys) != 2:
            continue
        k1, k2 = keys
        if k1 not in expected_c or k2 not in expected_c:
            continue
        already_ok = (
            _values_equal_relaxed(k1, out[k1], expected_c[k1], causes)
            and _values_equal_relaxed(k2, out[k2], expected_c[k2], causes)
        )
        if already_ok:
            continue
        swapped_ok = (
            _values_equal_relaxed(k1, out[k2], expected_c[k1], causes)
            and _values_equal_relaxed(k2, out[k1], expected_c[k2], causes)
        )
        if swapped_ok:
            out[k1], out[k2] = out[k2], out[k1]
    return out


def relaxed_compatible(
    parsed: dict[str, Any],
    expected: dict[str, Any],
    drift: Drift | None,
    acceptable: dict[str, list[Any]] | None,
    active_schema: dict[str, Any] | None,
    causes: set[str],
) -> bool:
    """More lenient drop-in for schema_drift.compatible(), diagnostic only."""
    if "properties_wrapper" in causes:
        parsed = _unwrap_properties(parsed)
    if not isinstance(parsed, dict):
        return False

    parsed_new = to_new_space(parsed, drift)
    expected_new = to_new_space(expected, drift)
    parsed_c = {_canonical_key(k, drift): v for k, v in parsed_new.items()}
    expected_c = {_canonical_key(k, drift): v for k, v in expected_new.items()}
    parsed_c = _apply_swap(parsed_c, expected_c, causes)

    declared = (active_schema or {}).get("args", {})

    if acceptable is not None:
        for key in parsed_c:
            if key not in expected_c and key not in declared and key not in acceptable:
                return False
        for pname, vals in acceptable.items():
            if pname not in expected_c:
                continue
            if pname in parsed_c:
                if not _acceptable_relaxed(parsed_c[pname], vals, causes):
                    return False
            elif "" not in vals:
                return False
        return True

    if drift is not None and drift.type == "unexpected_field":
        return all(_values_equal_relaxed(k, parsed_c.get(k), v, causes) for k, v in expected_c.items())
    if set(parsed_c) != set(expected_c):
        return False
    return all(_values_equal_relaxed(k, parsed_c[k], expected_c[k], causes) for k in expected_c)
