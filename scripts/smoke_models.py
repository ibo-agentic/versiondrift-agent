"""The 16-model registry for PLAN.md 10.2 smoke tests (2026-10-04).

``native_tool_template`` is per `analysis/plan/feasibility.md`'s own
Hugging Face `tokenizer_config.json`/chat_template checks this project
already did (not re-guessed here): True for the 8 models whose chat
template has real tool-calling logic (Mistral v0.3's [TOOL_CALLS],
Qwen2.5/Qwen3's ChatML <tool_call>, Llama-3.1's builtin_tools/python_tag,
Phi-4-mini's <|tool|> wrapping, and all three Granite versions'
<|tool_call|> instruction) -- those 8 get the F3 native-format config in
addition to D and F4. The other 8 have some chat_template (needed for D's
"native chat wrapping" to work at all) but no tool-calling logic in it.
"""

from __future__ import annotations

MODEL_REGISTRY: dict[str, dict] = {
    "mistral_v01": {"path": "models/itlwas/mistral-7b-instruct-v0.1-q4_k_m.gguf", "native_tool_template": False},
    "mistral_v02": {"path": "models/itlwas/mistral-7b-instruct-v0.2-q4_k_m.gguf", "native_tool_template": False},
    "mistral_v03": {"path": "models/itlwas/mistral-7b-instruct-v0.3-q4_k_m.gguf", "native_tool_template": True},
    "qwen2": {"path": "models/qwen/qwen2-7b-instruct-q4_k_m.gguf", "native_tool_template": False},
    "qwen25": {"path": "models/qwen/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf", "native_tool_template": True},
    "qwen3": {"path": "models/qwen/Qwen3-8B-Q4_K_M.gguf", "native_tool_template": True},
    "llama3": {"path": "models/llama/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf", "native_tool_template": False},
    "llama31": {"path": "models/llama/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", "native_tool_template": True},
    "phi3_mini": {"path": "models/phi/Phi-3-mini-4k-instruct-Q4_K_M.gguf", "native_tool_template": False},
    "phi35_mini": {"path": "models/phi/Phi-3.5-mini-instruct-Q4_K_M.gguf", "native_tool_template": False},
    "phi4_mini": {"path": "models/phi/microsoft_Phi-4-mini-instruct-Q4_K_M.gguf", "native_tool_template": True},
    "granite30": {"path": "models/granite/granite-3.0-8b-instruct-Q4_K_M.gguf", "native_tool_template": True},
    "granite31": {"path": "models/granite/granite-3.1-8b-instruct-Q4_K_M.gguf", "native_tool_template": True},
    "granite32": {"path": "models/granite/ibm-granite_granite-3.2-8b-instruct-Q4_K_M.gguf", "native_tool_template": True},
    "gemma2_2b": {"path": "models/gemma/gemma-2-2b-it-Q4_K_M.gguf", "native_tool_template": False},
    "gemma3_4b": {"path": "models/gemma/google_gemma-3-4b-it-Q4_K_M.gguf", "native_tool_template": False},
}


def configs_for(model_key: str) -> list[dict]:
    """The D/F3/F4 config specs applicable to one model. F3 (native tool
    format) is included only when the registry marks a real native
    tool-calling template -- "F3 native tool format, only for models that
    have one" per the smoke-test instruction."""
    entry = MODEL_REGISTRY[model_key]
    configs = [
        {"name": "D", "prompt_format": "shared", "constrained_decoding": "off"},
        {"name": "F4_generic_json", "prompt_format": "shared", "constrained_decoding": "generic_json"},
    ]
    if entry["native_tool_template"]:
        configs.append({"name": "F3_native_tool_format", "prompt_format": "native", "constrained_decoding": "off"})
    return configs
