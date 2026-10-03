"""Schema conversions for PLAN.md F3 (native tool-calling prompt format) and
F4 (constrained decoding). Pure functions, no model/IO -- translate this
project's internal tool-schema shape (``{"name", "description", "args":
{argname: {"type", "required", "enum"?, "default"?}}}``) into the two
external shapes other code needs:

- an OpenAI-style ``tools`` list entry (F3's ``prompt_format: native``,
  passed to ``ModelClient.generate(tools=...)``)
- a JSON Schema for the full ``{"name", "arguments"}`` response envelope
  (F4's ``constrained_decoding: generic_json`` / ``full_schema``, passed to
  ``ModelClient.generate(response_schema=...)`` -> ``LlamaGrammar.from_json_schema``)

Internal type names map to JSON Schema types as: string->string,
number->number, integer->integer, boolean->boolean (JSON Schema's own
vocabulary already matches ours for every type this project uses).
"""

from __future__ import annotations

from typing import Any

# F4 generic_json: structure only (name/arguments present with the right
# JSON *types*), no knowledge of which tool or which arguments -- the
# weakest constraint level, same for every record in a run.
GENERIC_JSON_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "arguments": {"type": "object"},
    },
    "required": ["name", "arguments"],
}


def args_to_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """The "arguments" object's JSON Schema, derived from one tool schema's
    ``args`` dict. Used standalone by F3 (inside an OpenAI tool's
    ``parameters``) and nested by F4's full_schema (inside the response
    envelope's ``arguments`` property)."""
    args = schema.get("args", {})
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, spec in args.items():
        prop: dict[str, Any] = {"type": spec.get("type", "string")}
        if "enum" in spec:
            prop["enum"] = list(spec["enum"])
        if "default" in spec:
            prop["default"] = spec["default"]
        properties[name] = prop
        if spec.get("required"):
            required.append(name)
    out: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        out["required"] = required
    return out


def schema_to_openai_tool(schema: dict[str, Any]) -> dict[str, Any]:
    """One internal tool schema -> one OpenAI-style ``tools=[...]`` entry
    (PLAN.md F3, ``prompt_format: native``)."""
    return {
        "type": "function",
        "function": {
            "name": schema.get("name", ""),
            "description": schema.get("description", ""),
            "parameters": args_to_json_schema(schema),
        },
    }


def full_schema_response_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """JSON Schema for the exact ``{"name": <this tool>, "arguments": {...}}``
    response envelope, constraining BOTH the tool name (via ``const``) and
    each argument's declared type (PLAN.md F4 ``constrained_decoding:
    full_schema``).

    PLAN.md's own F4 note applies: built from the ACTIVE (possibly
    drifted) schema, this forces the drifted field names/types onto the
    model's output, so the model no longer has to adapt to drift by
    itself -- that changes what schema_drift measures under this level,
    and the plan says to analyze it separately rather than mix it into the
    nuisance set.
    """
    return {
        "type": "object",
        "properties": {
            "name": {"const": schema.get("name", "")},
            "arguments": args_to_json_schema(schema),
        },
        "required": ["name", "arguments"],
    }


def response_schema_for(mode: str, schema: dict[str, Any] | None) -> dict[str, Any] | None:
    """Resolve PLAN.md F4's three levels to a response_schema (or None for
    "off"). ``schema`` is the task's active (possibly drifted) tool schema;
    only needed for "full_schema"."""
    if mode == "off":
        return None
    if mode == "generic_json":
        return GENERIC_JSON_RESPONSE_SCHEMA
    if mode == "full_schema":
        if schema is None:
            raise ValueError("constrained_decoding: full_schema requires an active tool schema")
        return full_schema_response_schema(schema)
    raise ValueError(f"constrained_decoding must be 'off', 'generic_json', or 'full_schema', got {mode!r}")
