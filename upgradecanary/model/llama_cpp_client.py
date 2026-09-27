"""llama.cpp backend via llama-cpp-python (lazy import, GGUF 4-bit friendly).

Only instantiated when ``model.provider: llama_cpp`` is set. Nothing here
downloads models — point ``model.path`` at a GGUF file you placed under models/.
"""

from __future__ import annotations

import os
from typing import Any


class LlamaCppClient:
    def __init__(self, model_cfg: dict[str, Any]) -> None:
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python is not installed. Install it with: "
                "pip install llama-cpp-python (see README for the Windows CUDA wheel)."
            ) from exc

        path = model_cfg.get("path", "")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"GGUF model not found at '{path}'. This project never downloads models; "
                "place a 4-bit GGUF file under models/ and update model.path (see README)."
            )

        # -1 puts all layers on the GPU; a Q4_K_M 7-8B model fits comfortably in 8GB.
        self._llm = Llama(
            model_path=path,
            n_ctx=int(model_cfg.get("n_ctx", 4096)),
            n_gpu_layers=-1,
            seed=int(model_cfg.get("seed", 0)),
            verbose=False,
        )
        self._temperature = float(model_cfg.get("temperature", 0.0))
        self._max_tokens = int(model_cfg.get("max_tokens", 512))
        self._seed = int(model_cfg.get("seed", 0))

    def generate(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        output = self._llm.create_completion(
            prompt=prompt,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            seed=self._seed,
        )
        return output["choices"][0]["text"]
