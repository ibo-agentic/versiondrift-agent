"""Deterministically regenerate data/base_tasks.jsonl (100 synthetic tasks).

Pure construction — no RNG, no network, no external calls. Tool mix is
balanced (+-5 tasks); drift_type hints are stratified across the five drift
types subject to each tool's applicability (see _SPECS in
upgradecanary/perturbations/schema_drift.py).

Run from the repo root:  python scripts/generate_tasks.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "base_tasks.jsonl"

TOOLS = [
    "get_weather",
    "search_docs",
    "convert_units",
    "calculator",
    "get_time",
    "get_stock_price",
]

# Balanced tool coverage: 20/20/15/15/15/15 = 100.
COUNTS = {
    "get_weather": 20,
    "search_docs": 20,
    "convert_units": 15,
    "calculator": 15,
    "get_time": 15,
    "get_stock_price": 15,
}

# Stratified drift coverage. Non-rename types are only expressible on specific
# tools, so field_rename necessarily carries the tools that support nothing
# else (calculator, get_time, get_stock_price).
DRIFT_SPLIT = {
    "get_weather": ["enum_drift"] * 10 + ["unexpected_field"] * 10,
    "search_docs": ["field_drop"] * 10 + ["type_mutation"] * 10,
    "convert_units": ["type_mutation"] * 7 + ["field_rename"] * 8,
    "calculator": ["field_rename"] * 15,
    "get_time": ["field_rename"] * 15,
    "get_stock_price": ["field_rename"] * 15,
}

CONDITIONS = ["baseline", "schema_drift", "runtime_fault"]

CITIES = ["Berlin", "Phoenix", "Tokyo"]
UNITS = ["celsius", "fahrenheit"]
ZONES = ["Europe/Paris", "Asia/Tokyo", "America/New_York"]
CONVERSIONS = [(5, "km", "mi"), (10, "mi", "km"), (3, "kg", "lb"), (8, "lb", "kg")]
QUERIES = ["vector index compaction", "write amplification"]
SYMBOLS = ["ACME", "GLOB"]


def build(tool: str, i: int) -> dict:
    """Build one task dict (without task_id/drift_type) for per-tool index i."""
    if tool == "get_weather":
        city, unit = CITIES[i % 3], UNITS[i % 2]
        prompts = [
            f"What is the current weather in {city}? Give me the temperature in {unit}.",
            f"Check the weather in {city} and report the temperature in {unit}.",
            f"How warm is it in {city} right now? Answer in {unit}.",
            f"Fetch the current weather for {city} using degrees {unit}.",
        ]
        args = {"city": city, "unit": unit}
    elif tool == "search_docs":
        query, top_k = QUERIES[i % 2], 1 + (i % 3)
        prompts = [
            f'Search the docs for "{query}" and return the top {top_k} hits.',
            f"Find documentation about {query}; I want the top {top_k} results.",
            f"Look up {query} in the documentation and show {top_k} entries.",
        ]
        args = {"query": query, "top_k": top_k}
    elif tool == "convert_units":
        value, from_unit, to_unit = CONVERSIONS[i % 4]
        prompts = [
            f"Convert {value} {from_unit} to {to_unit}.",
            f"How many {to_unit} is {value} {from_unit}?",
            f"Translate {value} {from_unit} into {to_unit}.",
        ]
        args = {"value": value, "from_unit": from_unit, "to_unit": to_unit}
    elif tool == "calculator":
        expression = f"{7 + i} * {3 + (i % 5)} + {11 + i}"
        prompts = [
            f"Calculate {expression} for me.",
            f"What is {expression}?",
            f"Compute {expression} exactly.",
            f"Evaluate {expression}.",
        ]
        args = {"expression": expression}
    elif tool == "get_time":
        zone = ZONES[i % 3]
        prompts = [
            f"What time is it right now in {zone}?",
            f"Tell me the current time in the {zone} timezone.",
            f"Check the clock for {zone}.",
        ]
        args = {"timezone": zone}
    else:  # get_stock_price
        symbol = SYMBOLS[i % 2]
        prompts = [
            f"What is the current stock price of {symbol}?",
            f"Get me the latest price for {symbol} stock.",
            f"Quote {symbol} for me.",
        ]
        args = {"symbol": symbol}
    return {
        "prompt": prompts[i % len(prompts)],
        "tool": tool,
        "expected_call": {"name": tool, "arguments": args},
        "condition_tags": list(CONDITIONS),
    }


def main() -> None:
    per_tool: dict[str, list[dict]] = {}
    for tool in TOOLS:
        per_tool[tool] = [build(tool, i) for i in range(COUNTS[tool])]

    # Round-robin interleave so consecutive task ids mix tools.
    merged: list[dict] = []
    cursors = {tool: 0 for tool in TOOLS}
    for n in range(sum(COUNTS.values())):
        for tool in TOOLS:
            i = cursors[tool]
            if i < COUNTS[tool]:
                task = {"task_id": f"task-{n + 1:03d}", **per_tool[tool][i]}
                task["drift_type"] = DRIFT_SPLIT[tool][i]
                cursors[tool] = i + 1
                merged.append(task)
                break

    assert len(merged) == 100
    assert len({t["task_id"] for t in merged}) == 100
    OUT.write_text(
        "".join(json.dumps(task, ensure_ascii=False) + "\n" for task in merged),
        encoding="utf-8",
    )
    print(f"wrote {len(merged)} tasks to {OUT}")


if __name__ == "__main__":
    main()
