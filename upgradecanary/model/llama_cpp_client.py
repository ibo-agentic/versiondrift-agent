"""llama.cpp backend via llama-cpp-python (lazy import, GGUF 4-bit friendly).

Only instantiated when ``model.provider: llama_cpp`` is set. Nothing here
downloads models — point ``model.path`` at a GGUF file you placed under models/.
"""

from __future__ import annotations

import os
import sys
from typing import Any

# Handles returned by os.add_dll_directory; kept alive for the process
# lifetime so Windows does not drop the added DLL search paths.
_dll_dir_handles: list[object] = []


def _add_bundled_cuda_dll_dirs() -> None:
    """Register NVIDIA CUDA runtime DLL folders bundled in the current venv.

    llama-cpp-python's CUDA wheels ship cudart/cublas under
    site-packages/nvidia/*/bin; adding them here lets llama.dll resolve its
    CUDA dependencies without CUDA being on PATH.
    """
    candidates = [
        os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cuda_runtime", "bin"),
        os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cublas", "bin"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            _dll_dir_handles.append(os.add_dll_directory(path))


class LlamaCppClient:
    def __init__(self, model_cfg: dict[str, Any]) -> None:
        _add_bundled_cuda_dll_dirs()
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
        # CPU-only llama-cpp-python builds simply ignore n_gpu_layers.
        self._llm = Llama(
            model_path=path,
            n_ctx=int(model_cfg.get("n_ctx", 4096)),
            n_gpu_layers=int(model_cfg.get("n_gpu_layers", -1)),
            seed=int(model_cfg.get("seed", 0)),
            verbose=False,
        )
        self._temperature = float(model_cfg.get("temperature", 0.0))
        self._max_tokens = int(model_cfg.get("max_tokens", 512))
        self._seed = int(model_cfg.get("seed", 0))
        # Optional instruct-style wrapping (e.g. Mistral: "<s>[INST]\n{prompt}\n[/INST]").
        # Applied only here, so the mock provider and the runner stay
        # template-agnostic. None = send the raw prompt unchanged.
        self._prompt_template = model_cfg.get("prompt_template") or None
        self._stop = model_cfg.get("stop") or None
        # Sampling params not exposed in configs (library defaults apply);
        # read back here so run_manifest.json can log what was actually in
        # effect (2026-10-02 audit follow-up, item 4).
        self._top_p = float(model_cfg.get("top_p", 0.95))
        self._top_k = int(model_cfg.get("top_k", 40))
        self._min_p = float(model_cfg.get("min_p", 0.05))
        self._repeat_penalty = float(model_cfg.get("repeat_penalty", 1.0))
        self._last_finish_reason: str | None = None

        from llama_cpp import __version__ as _llama_cpp_version

        self._backend_info = {
            "provider": "llama_cpp",
            "llama_cpp_python_version": _llama_cpp_version,
            "model_path": path,
            "n_ctx": int(model_cfg.get("n_ctx", 4096)),
            "n_gpu_layers": int(model_cfg.get("n_gpu_layers", -1)),
            "sampling_defaults_not_overridden": {
                "top_p": self._top_p,
                "top_k": self._top_k,
                "min_p": self._min_p,
                "repeat_penalty": self._repeat_penalty,
            },
        }

    def backend_info(self) -> dict[str, Any]:
        """Backend/version/sampling-params snapshot for run_manifest.json."""
        return dict(self._backend_info)

    def generate(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        *,
        temperature: float | None = None,
        seed: int | None = None,
    ) -> str:
        if self._prompt_template is not None:
            prompt = self._prompt_template.format(prompt=prompt)
        # Per-call temperature/seed support repeated trials. llama-cpp-python
        # accepts both per call; seeding is best-effort on GPU (see README).
        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "temperature": self._temperature if temperature is None else float(temperature),
            "max_tokens": self._max_tokens,
            "seed": self._seed if seed is None else int(seed),
            # Explicit so run_manifest.json's logged values are always what
            # was actually sent (2026-10-02 follow-up, item 4). These equal
            # llama-cpp-python's own defaults unless a config overrides them,
            # so rerunning any existing config is unaffected.
            "top_p": self._top_p,
            "top_k": self._top_k,
            "min_p": self._min_p,
            "repeat_penalty": self._repeat_penalty,
        }
        if self._stop:
            kwargs["stop"] = self._stop
        output = self._llm.create_completion(**kwargs)
        choice = output["choices"][0]
        self._last_finish_reason = choice.get("finish_reason")
        return choice["text"]

    def last_truncated(self) -> bool | None:
        if self._last_finish_reason is None:
            return None
        return self._last_finish_reason == "length"
