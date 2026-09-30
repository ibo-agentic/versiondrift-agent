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


def rendered_prompt_chars(fn_doc: dict[str, Any], prompt: str) -> int:
    """Length of the prompt the runner would send (eligibility rule 10)."""
    from types import SimpleNamespace

    from upgradecanary.runner import build_prompt

    task = SimpleNamespace(suite="bfcl", tool_schema=fn_doc, prompt=prompt)
    return len(build_prompt(task, None))


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
