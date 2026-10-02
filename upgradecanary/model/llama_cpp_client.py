"""llama.cpp backend via llama-cpp-python (lazy import, GGUF 4-bit friendly).

Only instantiated when ``model.provider: llama_cpp`` is set. Nothing here
downloads models — point ``model.path`` at a GGUF file you placed under models/.
"""

from __future__ import annotations

import json
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

        # PLAN.md section 4/10.1: chat_wrapping picks how the turn structure
        # is built. "legacy" (DEFAULT -- unset in every existing config, so
        # every historical run reproduces byte-identically) keeps the old
        # hand-built prompt_template string substitution above, unchanged.
        # "native" reads the model's own chat template straight out of the
        # GGUF's metadata (tokenizer.chat_template) and renders a plain
        # single-user-turn prompt with it -- no tool template, per PLAN.md's
        # default protocol D. See ENGINEERING_NOTES.md for how the old
        # per-model hand-built wrappers worked.
        self._chat_wrapping = model_cfg.get("chat_wrapping", "legacy")
        if self._chat_wrapping not in ("legacy", "native"):
            raise ValueError(f"model.chat_wrapping must be 'legacy' or 'native', got {self._chat_wrapping!r}")
        self._native_formatter = None
        if self._chat_wrapping == "native":
            self._native_formatter = self._build_native_formatter()
            if self._native_formatter is None:
                raise RuntimeError(
                    f"model.chat_wrapping is 'native' but '{path}' has no "
                    "tokenizer.chat_template in its GGUF metadata -- there is "
                    "no native template to read. Use chat_wrapping: legacy "
                    "(with an explicit prompt_template) for this model, or "
                    "re-convert/choose a GGUF that preserves the template."
                )

        # PLAN.md F2: thinking on/off (Qwen3 only; harmless no-op for any
        # template that doesn't reference "enable_thinking"). Only takes
        # effect under chat_wrapping: native, since that's the only path
        # where we render the Jinja template ourselves with a controllable
        # kwarg -- see ENGINEERING_NOTES.md for why legacy wrapping's
        # existing empty-<think>-prefill trick (real_trials_qwen3_nothink.yaml)
        # remains the only supported way to control thinking under legacy.
        thinking = model_cfg.get("thinking", "default")
        if thinking not in ("default", "on", "off"):
            raise ValueError(f"model.thinking must be 'default', 'on', or 'off', got {thinking!r}")
        self._thinking = thinking
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
            "chat_wrapping": self._chat_wrapping,
            "native_chat_template_found": self._native_formatter is not None,
            "thinking": self._thinking,
        }

    def _build_native_formatter(self):
        """Jinja2ChatFormatter built directly from the GGUF's own embedded
        tokenizer.chat_template, mirroring exactly what llama_cpp.Llama's own
        __init__ does internally (llama.py ~line 505-536) -- built here
        ourselves (not reused from self._llm's auto-registered handlers) so
        we can pass extra render kwargs (e.g. enable_thinking) that the
        high-level create_chat_completion() API has no parameter for; see
        Jinja2ChatFormatter.__call__'s **kwargs -> environment.render(**kwargs)
        in llama_chat_format.py. Returns None if the GGUF has no template.
        """
        template = self._llm.metadata.get("tokenizer.chat_template")
        if not template:
            return None
        from llama_cpp.llama_chat_format import Jinja2ChatFormatter

        eos_id = self._llm.token_eos()
        bos_id = self._llm.token_bos()
        eos_token = self._llm._model.token_get_text(eos_id) if eos_id != -1 else ""
        bos_token = self._llm._model.token_get_text(bos_id) if bos_id != -1 else ""
        return Jinja2ChatFormatter(
            template=template,
            eos_token=eos_token,
            bos_token=bos_token,
            stop_token_ids=[eos_id] if eos_id != -1 else None,
        )

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
        tools: list[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> str:
        stop = self._stop
        if self._chat_wrapping == "native":
            render_kwargs: dict[str, Any] = {}
            if self._thinking != "default":
                render_kwargs["enable_thinking"] = self._thinking == "on"
            rendered = self._native_formatter(
                messages=[{"role": "user", "content": prompt}],
                tools=tools,
                **render_kwargs,
            )
            prompt = rendered.prompt
            if stop is None and rendered.stop:
                stop = [rendered.stop] if isinstance(rendered.stop, str) else list(rendered.stop)
        elif self._prompt_template is not None:
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
        if stop:
            kwargs["stop"] = stop
        if response_schema is not None:
            from llama_cpp import LlamaGrammar

            kwargs["grammar"] = LlamaGrammar.from_json_schema(json.dumps(response_schema))
        output = self._llm.create_completion(**kwargs)
        choice = output["choices"][0]
        self._last_finish_reason = choice.get("finish_reason")
        return choice["text"]

    def last_truncated(self) -> bool | None:
        if self._last_finish_reason is None:
            return None
        return self._last_finish_reason == "length"
