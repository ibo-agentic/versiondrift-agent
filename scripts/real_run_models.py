"""Model registry for PLAN v1's real D-protocol runs (2026-10-05), ordered
fast-to-slow (small/quick models first, Qwen3 last) per the explicit
instruction -- ranking is each model's own D-protocol seconds/record from
analysis/plan/smoke_report.md's smoke test, not guessed.
"""

from __future__ import annotations

# (model_key, gguf_path) -- same paths as scripts/smoke_models.py.
# Order matches ascending D-protocol seconds/record from the smoke test.
MODEL_ORDER: list[tuple[str, str]] = [
    ("gemma2_2b", "models/gemma/gemma-2-2b-it-Q4_K_M.gguf"),
    ("gemma3_4b", "models/gemma/google_gemma-3-4b-it-Q4_K_M.gguf"),
    ("phi3_mini", "models/phi/Phi-3-mini-4k-instruct-Q4_K_M.gguf"),
    ("qwen2", "models/qwen/qwen2-7b-instruct-q4_k_m.gguf"),
    ("llama31", "models/llama/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"),
    ("mistral_v01", "models/itlwas/mistral-7b-instruct-v0.1-q4_k_m.gguf"),
    ("qwen25", "models/qwen/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf"),
    ("mistral_v03", "models/itlwas/mistral-7b-instruct-v0.3-q4_k_m.gguf"),
    ("llama3", "models/llama/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf"),
    ("granite32", "models/granite/ibm-granite_granite-3.2-8b-instruct-Q4_K_M.gguf"),
    ("granite31", "models/granite/granite-3.1-8b-instruct-Q4_K_M.gguf"),
    ("granite30", "models/granite/granite-3.0-8b-instruct-Q4_K_M.gguf"),
    ("phi4_mini", "models/phi/microsoft_Phi-4-mini-instruct-Q4_K_M.gguf"),
    ("mistral_v02", "models/itlwas/mistral-7b-instruct-v0.2-q4_k_m.gguf"),
    ("phi35_mini", "models/phi/Phi-3.5-mini-instruct-Q4_K_M.gguf"),
    ("qwen3", "models/qwen/Qwen3-8B-Q4_K_M.gguf"),
]

SUITES: dict[str, str] = {
    "synthetic": "data/base_tasks.jsonl",
    "bfcl_simple": "data/bfcl_tasks.jsonl",
    "bfcl_multiple": "data/bfcl_multiple_tasks.jsonl",
}

EXPECTED_RECORDS_PER_RUN = 100 * 3 * 3  # 100 tasks x 3 conditions x 3 trials = 900


def all_runs() -> list[tuple[str, str, str, str]]:
    """Every (model_key, gguf_path, suite, data_path) in run order."""
    runs = []
    for model_key, path in MODEL_ORDER:
        for suite, data_path in SUITES.items():
            runs.append((model_key, path, suite, data_path))
    return runs
