"""BFCL-derived task conversion and frozen selection for UpgradeCanary-BFCL-100.

Implements the "UpgradeCanary-BFCL-100 selection protocol" amendment in
docs/protocol.md. Selection uses task metadata only; model outcomes are never
consulted.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

SELECTION_SEED = 20260930
SELECT_COUNT = 100

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SOURCE_REL = Path(
    "external/gorilla/berkeley-function-call-leaderboard/bfcl_eval/data/BFCL_v4_simple_python.json"
)
ANSWERS_REL = Path(
    "external/gorilla/berkeley-function-call-leaderboard/bfcl_eval/data/possible_answer/BFCL_v4_simple_python.json"
)

CONDITIONS = ["baseline", "schema_drift", "runtime_fault"]

_TYPE_MAP = {
    "integer": "integer",
    "int": "integer",
    "number": "number",
    "float": "number",
    "string": "string",
    "boolean": "boolean",
    "bool": "boolean",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def question_text(record: dict[str, Any]) -> str:
    return "\n".join(
        message.get("content", "")
        for turn in record.get("question", [])
        for message in turn
    )


def internal_from_native(fn_doc: dict[str, Any]) -> dict[str, Any]:
    """Canonical internal schema for a BFCL-native function document."""
    props = fn_doc.get("parameters", {}).get("properties", {})
    required = set(fn_doc.get("parameters", {}).get("required", []))
    return {
        "name": fn_doc.get("name", ""),
        "description": fn_doc.get("description", ""),
        "args": {
            p: {"type": _TYPE_MAP.get(s.get("type"), "string"), "required": p in required}
            for p, s in props.items()
        },
    }


def rendered_prompt_chars(fn_doc: dict[str, Any], prompt: str, all_functions: list[dict[str, Any]] | None = None) -> int:
    """Length of the prompt the runner would send (eligibility rule 10).

    ``all_functions``, when given, measures the "multiple"-category prompt
    (every candidate tool rendered, not just the correct one) -- the real
    budget the model actually sees. ``None`` (default) keeps the original
    single-tool measurement used by the simple_python eligibility check,
    byte-for-byte unchanged.
    """
    from types import SimpleNamespace

    from upgradecanary.runner import build_prompt

    if all_functions is not None:
        task = SimpleNamespace(suite="bfcl", tool_schema=fn_doc, candidate_schemas=all_functions, prompt=prompt)
    else:
        task = SimpleNamespace(suite="bfcl", tool_schema=fn_doc, prompt=prompt)
    return len(build_prompt(task, internal_from_native(fn_doc)))


def is_eligible(record: dict[str, Any], answer: dict[str, Any] | None) -> tuple[bool, str]:
    if answer is None:
        return False, "missing_answer"
    functions = record.get("function") or []
    if len(functions) != 1:
        return False, "function_count"
    ground_truth = answer.get("ground_truth") or []
    if len(ground_truth) != 1:
        return False, "ground_truth_count"
    text = question_text(record)
    if any(ord(c) > 127 or not (c.isprintable() or c == "\t") for c in text):
        return False, "not_printable_ascii"
    if not (20 <= len(text) <= 400):
        return False, "question_length"
    low = text.lower()
    if "http" in low or "www." in low:
        return False, "url_in_question"
    fn = functions[0]
    props = fn.get("parameters", {}).get("properties", {})
    required = fn.get("parameters", {}).get("required", [])
    call = ground_truth[0]
    if not isinstance(call, dict) or len(call) != 1:
        return False, "ground_truth_shape"
    truth_args = next(iter(call.values()))
    for req in required:
        vals = truth_args.get(req)
        grounded = vals is not None and any(str(v).lower() in low for v in vals)
        has_default = "default" in props.get(req, {})
        if not (grounded or has_default):
            return False, f"ungrounded_required:{req}"
    for pname, vals in truth_args.items():
        if not isinstance(vals, list) or not vals:
            return False, f"bad_values:{pname}"
        for v in vals:
            if isinstance(v, bool):
                continue
            if not isinstance(v, (str, int, float)):
                return False, f"non_scalar:{pname}"
    if rendered_prompt_chars(fn, text) >= 1200:
        return False, "prompt_too_long"
    return True, "ok"


_INTERNAL_TO_NATIVE = {
    "integer": "integer",
    "number": "number",
    "string": "string",
    "boolean": "boolean",
}


def to_native_doc(internal_schema: dict[str, Any], base_native: dict[str, Any]) -> dict[str, Any]:
    """Rebuild a BFCL-native function document from a (possibly drifted)
    internal schema, preserving the native document shape.

    ``name``/``description`` come from ``base_native``; ``parameters.properties``
    are rebuilt from the internal schema's current args — entries that exist in
    the base document keep their original fields (description, default, items,
    enum) with the internal type applied when it maps cleanly; unmapped types
    are preserved verbatim; drift-added arguments (renames, new required
    fields) get a minimal entry. ``required`` is rebuilt from the internal
    required flags. For the canonical (baseline) schema this round-trips to
    the original native document.
    """
    base_props = base_native.get("parameters", {}).get("properties", {})
    properties: dict[str, Any] = {}
    for pname, spec in internal_schema.get("args", {}).items():
        base_entry = base_props.get(pname)
        type_name = spec.get("type")
        if base_entry is not None:
            entry = dict(base_entry)
            # Apply the internal type only when the base type is a mappable
            # scalar; exotic base types (array/dict/...) stay verbatim so the
            # baseline rendering round-trips to the original native document.
            if base_entry.get("type") in _TYPE_MAP and type_name in _INTERNAL_TO_NATIVE:
                # Apply the internal type only when it actually differs from the
                # base type's normalization (i.e. a drift mutated it); unchanged
                # arguments keep their original type name ("float" stays "float").
                if _TYPE_MAP[base_entry["type"]] != type_name:
                    entry["type"] = _INTERNAL_TO_NATIVE[type_name]
        else:
            entry = {"type": _INTERNAL_TO_NATIVE.get(type_name, "string")}
        properties[pname] = entry
    required = [p for p, s in internal_schema.get("args", {}).items() if s.get("required")]
    return {
        "name": base_native.get("name", internal_schema.get("name")),
        "description": base_native.get("description", ""),
        "parameters": {"type": "dict", "properties": properties, "required": required},
    }


def type_signature(fn: dict[str, Any], truth_args: dict[str, Any]) -> str:
    props = fn.get("parameters", {}).get("properties", {})
    types = sorted(_TYPE_MAP.get(props.get(p, {}).get("type"), "other") for p in truth_args)
    return ",".join(types)


def _coerce_value(value: Any, type_name: str) -> Any:
    """Align an answer value with the schema-declared type when unambiguous.

    BFCL ground-truth values occasionally disagree with the function schema
    (e.g. integer parameter with a string answer). Selection is unchanged;
    conversion coerces scalars safely so the canonical expected call
    validates against the advertised schema. Non-convertible values pass
    through unchanged.
    """
    if isinstance(value, bool):
        return value
    if type_name == "integer" and isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return value
    if type_name == "number" and isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return value
        return int(number) if number.is_integer() else number
    if type_name == "string" and isinstance(value, (int, float)):
        return str(value)
    if type_name == "boolean" and isinstance(value, str):
        if value == "true":
            return True
        if value == "false":
            return False
    return value


def convert(record: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    fn = record["function"][0]
    props = fn.get("parameters", {}).get("properties", {})
    required = set(fn.get("parameters", {}).get("required", []))
    args_schema = {}
    for pname, pspec in props.items():
        args_schema[pname] = {
            "type": _TYPE_MAP.get(pspec.get("type"), "string"),
            "required": pname in required,
        }
    call = answer["ground_truth"][0]
    name = next(iter(call))
    truth_args = call[name]
    acceptable = {}
    canonical = {}
    for pname, vals in truth_args.items():
        type_name = args_schema.get(pname, {}).get("type", "string")
        coerced = [_coerce_value(v, type_name) for v in vals]
        # Keep "" entries: BFCL uses "" to mark omission-tolerant parameters.
        # The canonical expected call uses the first non-empty value; a
        # parameter whose only value is "" is canonically absent.
        acceptable[pname] = coerced
        real = [v for v in coerced if v != ""]
        if not real:
            continue
        canonical[pname] = real[0]
    internal = {
        "name": fn["name"],
        "description": fn.get("description", ""),
        "args": args_schema,
    }
    return {
        "task_id": f"bfcl-{record['id']}",
        "prompt": question_text(record),
        "tool": fn["name"],
        "expected_call": {"name": fn["name"], "arguments": canonical},
        "condition_tags": list(CONDITIONS),
        "drift_type": None,
        "suite": "bfcl",
        "tool_schema": fn,
        "internal_schema": internal,
        "acceptable": acceptable,
        "source_id": record["id"],
    }


def select_tasks(
    eligible: list[dict[str, Any]], seed: int = SELECTION_SEED, n: int = SELECT_COUNT
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    """Seeded stratified sample by parameter-type signature (largest-remainder quotas)."""
    strata: dict[str, list[dict[str, Any]]] = {}
    for item in eligible:
        strata.setdefault(item["signature"], []).append(item)
    total = len(eligible)
    raw = {s: n * len(items) / total for s, items in strata.items()}
    quotas = {s: int(v) for s, v in raw.items()}
    remainder = n - sum(quotas.values())
    order = sorted(raw, key=lambda s: raw[s] - int(raw[s]), reverse=True)
    for s in order[:remainder]:
        quotas[s] += 1
    selected = []
    for s in sorted(strata):
        rng = random.Random(f"{seed}-{s}")
        items = list(strata[s])
        rng.shuffle(items)
        selected.extend(items[: quotas[s]])
    selected.sort(key=lambda it: it["task"]["task_id"])
    stats = {s: {"eligible": len(strata[s]), "selected": quotas[s]} for s in sorted(strata)}
    return selected, stats


def generate(data_dir: Path = DATA_DIR) -> dict[str, Any]:
    root = Path(__file__).resolve().parent.parent
    records = load_jsonl(root / SOURCE_REL)
    answer_by_id = {a["id"]: a for a in load_jsonl(root / ANSWERS_REL)}

    eligible: list[dict[str, Any]] = []
    seen_functions: set[str] = set()
    rejected = 0
    for record in records:
        answer = answer_by_id.get(record["id"])
        ok, _reason = is_eligible(record, answer)
        if not ok:
            rejected += 1
            continue
        fn_name = record["function"][0]["name"]
        if fn_name in seen_functions:  # rule 11: keep first eligible occurrence
            rejected += 1
            continue
        seen_functions.add(fn_name)
        task = convert(record, answer)
        eligible.append(
            {
                "task": task,
                "signature": type_signature(record["function"][0], answer["ground_truth"][0][fn_name]),
                "source_id": record["id"],
                "function": fn_name,
            }
        )

    selected, stats = select_tasks(eligible)
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(data_dir / "bfcl_tasks.jsonl", "w", encoding="utf-8") as fh:
        for item in selected:
            fh.write(json.dumps(item["task"], ensure_ascii=False) + "\n")
    with open(data_dir / "bfcl_tasks_provenance.jsonl", "w", encoding="utf-8") as fh:
        for item in selected:
            fh.write(
                json.dumps(
                    {
                        "task_id": item["task"]["task_id"],
                        "source_id": item["source_id"],
                        "function": item["function"],
                        "signature": item["signature"],
                        "question_chars": len(item["task"]["prompt"]),
                        "suite": "bfcl",
                        "protocol": "UpgradeCanary-BFCL-100 selection protocol (docs/protocol.md)",
                        "seed": SELECTION_SEED,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return {"eligible": len(eligible), "rejected": rejected, "selected": len(selected), "strata": stats}


# =============================================================================
# BFCL "multiple" category (PLAN.md 10.1 item 3): the model is shown SEVERAL
# candidate tool schemas and must pick the right one; still exactly one
# correct call. Implemented as fully separate functions (never touching
# is_eligible/convert/generate above) so the frozen simple_python selection
# in docs/protocol.md cannot be affected even by an unintended refactor --
# some logic below is intentionally duplicated from the simple_python path
# rather than shared, as the safer choice. See docs/protocol.md's
# "UpgradeCanary-BFCL-multiple-100 selection protocol" amendment and
# analysis/plan/feasibility.md section f for the design this follows.
# =============================================================================

MULTIPLE_SOURCE_REL = Path(
    "external/gorilla/berkeley-function-call-leaderboard/bfcl_eval/data/BFCL_v4_multiple.json"
)
MULTIPLE_ANSWERS_REL = Path(
    "external/gorilla/berkeley-function-call-leaderboard/bfcl_eval/data/possible_answer/BFCL_v4_multiple.json"
)


def find_correct_function(functions: list[dict[str, Any]], truth_name: str) -> dict[str, Any] | None:
    """The candidate in ``functions`` whose name matches the ground-truth
    call's function name, or None if no candidate matches (defends against
    malformed BFCL records -- never assume ``functions[0]`` is correct once
    there is more than one candidate)."""
    for fn in functions:
        if fn.get("name") == truth_name:
            return fn
    return None


def is_eligible_multiple(
    record: dict[str, Any], answer: dict[str, Any] | None, max_prompt_chars: int = 1200
) -> tuple[bool, str]:
    """Eligibility for the "multiple" category: same checks as
    ``is_eligible`` (printable ASCII, question length, no URL, required-arg
    grounding, scalar-only values, rendered-prompt-length budget), but
    requires >= 2 candidate functions (that is what "multiple" means for
    this BFCL category) and resolves the CORRECT one by matching the
    ground-truth call's function name rather than assuming index 0.

    ``max_prompt_chars`` defaults to 1200 to literally match simple_python's
    rule ("same selection rules otherwise" per PLAN.md 10.1 item 3) -- but
    see docs/protocol.md's multiple-category amendment / ENGINEERING_NOTES.md:
    at 1200, EVERY record in BFCL_v4_multiple.json is rejected (rendering
    >= 2 full tool schemas is categorically longer than rendering one), so
    this default alone cannot produce a 100-task suite. Pass an explicit,
    protocol-decided value to actually select tasks.
    """
    if answer is None:
        return False, "missing_answer"
    functions = record.get("function") or []
    if len(functions) < 2:
        return False, "not_multiple"
    ground_truth = answer.get("ground_truth") or []
    if len(ground_truth) != 1:
        return False, "ground_truth_count"
    call = ground_truth[0]
    if not isinstance(call, dict) or len(call) != 1:
        return False, "ground_truth_shape"
    truth_name = next(iter(call))
    fn = find_correct_function(functions, truth_name)
    if fn is None:
        return False, "ground_truth_function_not_in_candidates"
    text = question_text(record)
    if any(ord(c) > 127 or not (c.isprintable() or c == "\t") for c in text):
        return False, "not_printable_ascii"
    if not (20 <= len(text) <= 400):
        return False, "question_length"
    low = text.lower()
    if "http" in low or "www." in low:
        return False, "url_in_question"
    props = fn.get("parameters", {}).get("properties", {})
    required = fn.get("parameters", {}).get("required", [])
    truth_args = call[truth_name]
    for req in required:
        vals = truth_args.get(req)
        grounded = vals is not None and any(str(v).lower() in low for v in vals)
        has_default = "default" in props.get(req, {})
        if not (grounded or has_default):
            return False, f"ungrounded_required:{req}"
    for pname, vals in truth_args.items():
        if not isinstance(vals, list) or not vals:
            return False, f"bad_values:{pname}"
        for v in vals:
            if isinstance(v, bool):
                continue
            if not isinstance(v, (str, int, float)):
                return False, f"non_scalar:{pname}"
    if rendered_prompt_chars(fn, text, all_functions=functions) >= max_prompt_chars:
        return False, "prompt_too_long"
    return True, "ok"


def convert_multiple(record: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    """Like ``convert``, but ``tool`` / ``tool_schema`` / ``internal_schema``
    / ``expected_call`` all point at the CORRECT candidate (resolved by
    ground-truth name, never index 0), and ``candidate_schemas`` carries
    every candidate (including the correct one) for prompt rendering.
    """
    functions = record["function"]
    ground_truth = answer["ground_truth"][0]
    truth_name = next(iter(ground_truth))
    fn = find_correct_function(functions, truth_name)
    if fn is None:
        raise ValueError(f"ground-truth function {truth_name!r} not among candidates for {record['id']!r}")

    props = fn.get("parameters", {}).get("properties", {})
    required = set(fn.get("parameters", {}).get("required", []))
    args_schema = {}
    for pname, pspec in props.items():
        args_schema[pname] = {
            "type": _TYPE_MAP.get(pspec.get("type"), "string"),
            "required": pname in required,
        }
    truth_args = ground_truth[truth_name]
    acceptable = {}
    canonical = {}
    for pname, vals in truth_args.items():
        type_name = args_schema.get(pname, {}).get("type", "string")
        coerced = [_coerce_value(v, type_name) for v in vals]
        acceptable[pname] = coerced
        real = [v for v in coerced if v != ""]
        if not real:
            continue
        canonical[pname] = real[0]
    internal = {
        "name": fn["name"],
        "description": fn.get("description", ""),
        "args": args_schema,
    }
    return {
        "task_id": f"bfcl-multiple-{record['id']}",
        "prompt": question_text(record),
        "tool": fn["name"],
        "expected_call": {"name": fn["name"], "arguments": canonical},
        "condition_tags": list(CONDITIONS),
        "drift_type": None,
        "suite": "bfcl",
        "tool_schema": fn,
        "internal_schema": internal,
        "acceptable": acceptable,
        "source_id": record["id"],
        "candidate_schemas": functions,
    }


def generate_multiple(data_dir: Path = DATA_DIR, max_prompt_chars: int = 1200) -> dict[str, Any]:
    """Generate BFCL-multiple-100: same fixed SELECTION_SEED, same n=100,
    same stratified largest-remainder selection (select_tasks(), reused
    unchanged) as simple_python -- "same selection rules otherwise" per
    PLAN.md 10.1 item 3. Writes data/bfcl_multiple_tasks.jsonl and
    data/bfcl_multiple_tasks_provenance.jsonl; never touches
    bfcl_tasks.jsonl (the simple_python file).

    ``max_prompt_chars``: see is_eligible_multiple's docstring -- the
    default (1200, matching simple_python) yields 0 eligible tasks for this
    category and cannot select 100; this is a genuine, data-driven protocol
    question (not a bug), flagged in ENGINEERING_NOTES.md pending a decision.
    """
    root = Path(__file__).resolve().parent.parent
    records = load_jsonl(root / MULTIPLE_SOURCE_REL)
    answer_by_id = {a["id"]: a for a in load_jsonl(root / MULTIPLE_ANSWERS_REL)}

    eligible: list[dict[str, Any]] = []
    seen_functions: set[str] = set()
    rejected = 0
    for record in records:
        answer = answer_by_id.get(record["id"])
        ok, _reason = is_eligible_multiple(record, answer, max_prompt_chars=max_prompt_chars)
        if not ok:
            rejected += 1
            continue
        truth_name = next(iter(answer["ground_truth"][0]))
        fn = find_correct_function(record["function"], truth_name)
        if fn["name"] in seen_functions:  # rule 11, on the CORRECT tool's name
            rejected += 1
            continue
        seen_functions.add(fn["name"])
        task = convert_multiple(record, answer)
        eligible.append(
            {
                "task": task,
                "signature": f"{type_signature(fn, answer['ground_truth'][0][truth_name])},n{len(record['function'])}",
                "source_id": record["id"],
                "function": fn["name"],
            }
        )

    selected, stats = select_tasks(eligible)
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(data_dir / "bfcl_multiple_tasks.jsonl", "w", encoding="utf-8") as fh:
        for item in selected:
            fh.write(json.dumps(item["task"], ensure_ascii=False) + "\n")
    with open(data_dir / "bfcl_multiple_tasks_provenance.jsonl", "w", encoding="utf-8") as fh:
        for item in selected:
            fh.write(
                json.dumps(
                    {
                        "task_id": item["task"]["task_id"],
                        "source_id": item["source_id"],
                        "function": item["function"],
                        "num_candidates": len(item["task"]["candidate_schemas"]),
                        "signature": item["signature"],
                        "question_chars": len(item["task"]["prompt"]),
                        "suite": "bfcl",
                        "protocol": "UpgradeCanary-BFCL-multiple-100 selection protocol (docs/protocol.md)",
                        "seed": SELECTION_SEED,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return {"eligible": len(eligible), "rejected": rejected, "selected": len(selected), "strata": stats}
