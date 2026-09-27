"""Model client registry."""

from __future__ import annotations

from typing import Any

from .base import ModelClient
from .mock_llm import MockModelClient


def create_client(model_cfg: dict[str, Any]) -> ModelClient:
    provider = model_cfg.get("provider", "mock")
    if provider == "mock":
        return MockModelClient(model_cfg.get("mock", {}))
    if provider == "llama_cpp":
        from .llama_cpp_client import LlamaCppClient

        return LlamaCppClient(model_cfg)
    raise ValueError(f"Unknown model provider: {provider!r} (expected 'mock' or 'llama_cpp')")


__all__ = ["ModelClient", "MockModelClient", "create_client"]
