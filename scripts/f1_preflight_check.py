"""F1 preflight (2026-10-05): before running anything, check whether any
task's rendered D-style prompt, tokenized by each model's own tokenizer,
would exceed F1's tighter budget (n_ctx=4096, max_tokens=1024 -> prompt
must be <= 3072 tokens). Loads each model only for tokenization (no
generation), checks the baseline condition's prompt for every task in
every suite (the worst case per task -- schema_drift's prompt is the
same schema just renamed/mutated, not meaningfully longer; fault_
reporting's prompt is short and fixed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "analysis" / "audit"))
import _dll_preload  # noqa: E402

_dll_preload.preload()

from scripts.real_run_models import MODEL_ORDER, SUITES  # noqa: E402
from upgradecanary.model.llama_cpp_client import LlamaCppClient  # noqa: E402
from upgradecanary.runner import build_prompt, task_base_schema  # noqa: E402
from upgradecanary.tasks import load_tasks  # noqa: E402

N_CTX = 4096
MAX_TOKENS = 1024
BUDGET = N_CTX - MAX_TOKENS  # 3072


def main() -> int:
    violations = []
    results = []
    for model_key, gguf_path in MODEL_ORDER:
        print(f"=== {model_key} ===", flush=True)
        client = LlamaCppClient({
            "path": gguf_path, "chat_wrapping": "native", "n_ctx": N_CTX,
            "n_gpu_layers": -1, "seed": 0, "temperature": 0.0, "max_tokens": 1,
        })
        worst_for_model = 0
        worst_task_for_model = None
        for suite, data_path in SUITES.items():
            tasks = load_tasks(REPO_ROOT / data_path)
            for task in tasks:
                schema = task_base_schema(task)
                prompt = build_prompt(task, schema, prompt_format="shared")
                rendered = client._native_formatter(messages=[{"role": "user", "content": prompt}], tools=None)
                text_to_tokenize, add_bos = __import__(
                    "upgradecanary.model.llama_cpp_client", fromlist=["resolve_native_prompt_text"]
                ).resolve_native_prompt_text(rendered.prompt, client._native_bos_token, client._native_wants_bos)
                token_ids = client._llm.tokenize(text_to_tokenize.encode("utf-8"), add_bos=add_bos, special=True)
                n = len(token_ids)
                if n > worst_for_model:
                    worst_for_model = n
                    worst_task_for_model = f"{suite}/{task.task_id}"
                if n > BUDGET:
                    violations.append((model_key, suite, task.task_id, n))
        print(f"  worst prompt: {worst_for_model} tokens ({worst_task_for_model}), budget={BUDGET}", flush=True)
        results.append((model_key, worst_for_model, worst_task_for_model))
        del client

    print("\n=== SUMMARY ===")
    for model_key, worst, task_id in results:
        flag = " <-- EXCEEDS BUDGET" if worst > BUDGET else ""
        print(f"{model_key:12s} worst={worst:5d} budget={BUDGET}{flag}")

    if violations:
        print("\n=== VIOLATIONS (prompt + 1024 > 4096) ===")
        for v in violations:
            print(f"  {v[0]}/{v[1]}/{v[2]}: {v[3]} tokens (needs <= {BUDGET})")
        return 1
    print("\nNo violations. Safe to proceed with F1 at max_tokens=1024 for all 16 models.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
