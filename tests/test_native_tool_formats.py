"""PLAN.md F3 follow-up (2026-10-04): native tool-calling output formats.

Example outputs below are modeled on each family's own documented/verified
convention (see docs/ENGINEERING_NOTES.md for the exact source quoted per
format -- each was checked against that model's own tokenizer_config.json
or model card this session, not assumed from memory alone, except
Phi-4-mini's, which is explicitly flagged UNVERIFIED there since no
official example of its tool-call OUTPUT (as opposed to its input tool
definition wrapping) could be found).
"""

from __future__ import annotations

from upgradecanary.parsing import extract_tool_call, extract_tool_call_with_format

# --- Qwen: <tool_call>\n{"name": ..., "arguments": {...}}\n</tool_call> -----
# Verified against Qwen/Qwen2.5-7B-Instruct's own tokenizer_config.json
# chat_template this session.
QWEN_EXAMPLE = '<tool_call>\n{"name": "get_weather", "arguments": {"city": "Paris"}}\n</tool_call>'

# --- Mistral v0.3: [TOOL_CALLS] followed by a JSON list --------------------
# [TOOL_CALLS] confirmed as a real registered special token (id 5) in
# mistralai/Mistral-7B-Instruct-v0.3's tokenizer_config.json this session;
# the list-of-one-call shape is Mistral's documented function-calling
# convention.
MISTRAL_EXAMPLE = '[TOOL_CALLS] [{"name": "get_weather", "arguments": {"city": "Paris"}}]'

# --- Granite: <|tool_call|> (prefix only, no closing tag) + a JSON list ----
# Verified verbatim against ibm-granite/granite-3.1-8b-instruct's chat_template
# this session: "respond with <|tool_call|> followed by a JSON list of tools".
GRANITE_EXAMPLE = '<|tool_call|>[{"name": "get_weather", "arguments": {"city": "Paris"}}]'

# --- Phi-4-mini: <|tool_call|>...<|/tool_call|> (paired) -- UNVERIFIED -----
# microsoft/Phi-4-mini-instruct's tokenizer_config.json confirms both
# <|tool_call|> and <|/tool_call|> exist as special tokens, and its model
# card shows <|tool|>...<|/tool|> wrapping the INPUT tool definitions
# (symmetric open/close convention), but no official example of the
# OUTPUT tool-call text was found this session -- this example is a
# best-effort guess consistent with the tokens that exist, not a
# confirmed format. Flag for correction at smoke-test time if wrong.
PHI4_EXAMPLE = '<|tool_call|>{"name": "get_weather", "arguments": {"city": "Paris"}}<|/tool_call|>'

# --- Llama 3.1: bare object using "parameters" instead of "arguments" ------
# Confirmed via explicit keyword match against unsloth/Meta-Llama-3.1-8B-
# Instruct's tokenizer_config.json during the earlier feasibility check
# (analysis/plan/feasibility.md): tools/builtin_tools/<|python_tag|> present.
LLAMA31_EXAMPLE = '<|python_tag|>{"name": "get_weather", "parameters": {"city": "Paris"}}'

# --- Untagged list-wrapped (no specific family claimed) ---------------------
LIST_WRAPPED_EXAMPLE = '[{"name": "get_weather", "arguments": {"city": "Paris"}}]'

# --- Granite-3.0: OpenAI-flavored hybrid, tool name as a bare string ------
# 2026-10-07, found in real F3 run data (results_v2/F3/granite30/), not
# invented: Granite-3.0 has no explicit in-prompt instruction for its
# tool-call format at all (confirmed by reading its chat_template
# directly -- the tools list is dumped with no accompanying natural-
# language instruction on how to respond), and sometimes drifts to this
# shape instead of its own <|tool_call|> convention. Deliberately
# distinct from true OpenAI format (where "function" is a nested OBJECT
# with its own "name" key) -- here "function" is a plain string, the
# tool name directly.
GRANITE30_FUNCTION_STRING_EXAMPLE = (
    '{"type": "function", "function": "get_weather", "arguments": {"city": "Paris"}}'
)

EXPECTED_CALL = {"name": "get_weather", "arguments": {"city": "Paris"}}


def test_qwen_tag_format():
    call, fmt = extract_tool_call_with_format(QWEN_EXAMPLE)
    assert call == EXPECTED_CALL
    assert fmt == "qwen_tool_call_tag"


def test_mistral_tool_calls_tag_format():
    call, fmt = extract_tool_call_with_format(MISTRAL_EXAMPLE)
    assert call == EXPECTED_CALL
    assert fmt == "mistral_tool_calls_tag"


def test_granite_tool_call_tag_format():
    call, fmt = extract_tool_call_with_format(GRANITE_EXAMPLE)
    assert call == EXPECTED_CALL
    assert fmt == "granite_tool_call_tag"


def test_phi4_tool_call_tag_format():
    call, fmt = extract_tool_call_with_format(PHI4_EXAMPLE)
    assert call == EXPECTED_CALL
    assert fmt == "phi4_tool_call_tag"


def test_granite_and_phi4_share_opening_tag_but_are_disambiguated_by_the_closing_one():
    # Both use the literal "<|tool_call|>" opener; only the paired (Phi-4)
    # form also has "<|/tool_call|>". Confirms detection order handles this.
    granite_call, granite_fmt = extract_tool_call_with_format(GRANITE_EXAMPLE)
    phi4_call, phi4_fmt = extract_tool_call_with_format(PHI4_EXAMPLE)
    assert granite_fmt == "granite_tool_call_tag"
    assert phi4_fmt == "phi4_tool_call_tag"
    assert granite_call == phi4_call == EXPECTED_CALL


def test_llama31_parameters_alias_format():
    call, fmt = extract_tool_call_with_format(LLAMA31_EXAMPLE)
    assert call == EXPECTED_CALL  # normalized to "arguments" internally
    assert fmt == "parameters_alias"


def test_granite30_function_as_string_alias_format():
    call, fmt = extract_tool_call_with_format(GRANITE30_FUNCTION_STRING_EXAMPLE)
    assert call == EXPECTED_CALL  # "function" (string) normalized to "name"
    assert fmt == "function_name_alias"


def test_function_as_nested_object_still_parses_but_not_via_the_new_alias():
    # The real OpenAI shape ("function" is a nested object with its own
    # "name" inside, not a bare string) must NOT trigger the new
    # Granite-3.0 alias (obj.get("function") is a dict there, not a
    # string, so the alias check correctly skips it) -- but it still
    # parses successfully, because _call_candidates() scans for a JSON
    # object/array starting at EVERY "{"/"[" in the text, including
    # nested ones, and the inner {"name": ..., "arguments": ...} object
    # matches the plain canonical shape on its own. Confirms the new
    # alias doesn't duplicate-handle or interfere with this pre-existing
    # (already-correct) behavior.
    raw = '{"type": "function", "function": {"name": "get_weather", "arguments": {"city": "Paris"}}}'
    call, fmt = extract_tool_call_with_format(raw)
    assert call == EXPECTED_CALL
    assert fmt == "bare_json"  # via the inner nested object, not the alias


def test_untagged_list_wrapped_format():
    call, fmt = extract_tool_call_with_format(LIST_WRAPPED_EXAMPLE)
    assert call == EXPECTED_CALL
    assert fmt == "list_wrapped"


def test_original_bare_json_format_unchanged():
    raw = '{"name": "get_weather", "arguments": {"city": "Paris"}}'
    call, fmt = extract_tool_call_with_format(raw)
    assert call == EXPECTED_CALL
    assert fmt == "bare_json"


def test_original_tool_call_envelope_format_unchanged():
    raw = '{"tool_call": {"name": "get_weather", "arguments": {"city": "Paris"}}}'
    call, fmt = extract_tool_call_with_format(raw)
    assert call == EXPECTED_CALL
    assert fmt == "bare_json"


def test_unparseable_returns_none_none():
    call, fmt = extract_tool_call_with_format("I cannot help with that.")
    assert call is None
    assert fmt is None


def test_detected_tag_reported_even_when_content_inside_is_unparseable():
    # Diagnostically useful: we know a model attempted the Qwen tag
    # convention even though what's inside it didn't parse.
    call, fmt = extract_tool_call_with_format("<tool_call>\nnot valid json\n</tool_call>")
    assert call is None
    assert fmt == "qwen_tool_call_tag"


def test_extract_tool_call_backward_compatible_wrapper_discards_format():
    # The plain extract_tool_call() (used by every existing call site)
    # must still work unchanged for every new shape too.
    assert extract_tool_call(QWEN_EXAMPLE) == EXPECTED_CALL
    assert extract_tool_call(MISTRAL_EXAMPLE) == EXPECTED_CALL
    assert extract_tool_call(GRANITE_EXAMPLE) == EXPECTED_CALL
    assert extract_tool_call(LLAMA31_EXAMPLE) == EXPECTED_CALL
    assert extract_tool_call(LIST_WRAPPED_EXAMPLE) == EXPECTED_CALL


def test_strip_think_and_lenient_options_still_work_with_new_formats():
    raw = "<think>reasoning</think>\n" + QWEN_EXAMPLE
    call, fmt = extract_tool_call_with_format(raw, strip_think=True)
    assert call == EXPECTED_CALL
    assert fmt == "qwen_tool_call_tag"


def test_list_wrapped_with_invalid_escape_recovers_under_lenient():
    raw = '[{"name": "get\\_weather", "arguments": {"city": "Paris"}}]'
    call, fmt = extract_tool_call_with_format(raw, lenient=True)
    assert call == {"name": "get_weather", "arguments": {"city": "Paris"}}
    assert fmt == "list_wrapped"
    # Strict (default) must NOT recover -- unchanged diagnostic boundary.
    call_strict, _ = extract_tool_call_with_format(raw, lenient=False)
    assert call_strict is None
