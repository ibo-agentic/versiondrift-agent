"""Where the Kaggle runs of Phase 2 get their GGUF files.

Q8_0 (F5): kaggle_plan.Q8_SOURCES, unchanged from Phase 1.
Q4_K_M (D and R baselines on Kaggle): the SAME files the laptop uses. Repository, file name, size and
SHA-256 come from docs/model_manifest.md (each hash is the file's own Hugging Face lfs.oid); verified
against the Hugging Face tree API on 2026-10-19. The worker re-computes the SHA-256 of every download
and refuses a model whose hash differs.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kaggle_plan import GGUFFile, Q8_SOURCES  # noqa: E402

Q4_K_M_SOURCES: dict[str, tuple[GGUFFile, ...]] = {
    "mistral_v01": (GGUFFile("itlwas/Mistral-7B-Instruct-v0.1-Q4_K_M-GGUF", "mistral-7b-instruct-v0.1-q4_k_m.gguf",
                             "1af6bf966c4113f0cb5de7af42f38572075c9798bc16e6c72faee051bd7d6d33", 4368440864),),
    "mistral_v02": (GGUFFile("itlwas/Mistral-7B-Instruct-v0.2-Q4_K_M-GGUF", "mistral-7b-instruct-v0.2-q4_k_m.gguf",
                             "aaae8abe274e1521d5aa80bf32cf18b408fc44b9d6869acbdc815440296d275e", 4368440544),),
    "mistral_v03": (GGUFFile("itlwas/Mistral-7B-Instruct-v0.3-Q4_K_M-GGUF", "mistral-7b-instruct-v0.3-q4_k_m.gguf",
                             "9a643d2815e427e6622c3ef7f284af942bd0c58463a7c94f726fa882f487a404", 4372815808),),
    "qwen2": (GGUFFile("Qwen/Qwen2-7B-Instruct-GGUF", "qwen2-7b-instruct-q4_k_m.gguf",
                       "ed93dfc426f926451fa3ec7f996a787a31cfd97e55d7769568fbffc2d69861c2", 4683071264),),
    # two-part split GGUF; llama.cpp loads it from part 1 when part 2 sits beside it
    "qwen25": (GGUFFile("Qwen/Qwen2.5-7B-Instruct-GGUF", "qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
                        "dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db", 3993201344),
               GGUFFile("Qwen/Qwen2.5-7B-Instruct-GGUF", "qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf",
                        "539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a", 689872288)),
    "qwen3": (GGUFFile("Qwen/Qwen3-8B-GGUF", "Qwen3-8B-Q4_K_M.gguf",
                       "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785", 5027783488),),
    "llama3": (GGUFFile("bartowski/Meta-Llama-3-8B-Instruct-GGUF", "Meta-Llama-3-8B-Instruct-Q4_K_M.gguf",
                        "8ba9baf3a7345f705a11878397500fb25174034f0fd784e83aa4a96aaa47735f", 4920734272),),
    "llama31": (GGUFFile("bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
                         "7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c", 4920739232),),
    "granite30": (GGUFFile("bartowski/granite-3.0-8b-instruct-GGUF", "granite-3.0-8b-instruct-Q4_K_M.gguf",
                           "360c8e306b9a40c59080e60cb51305867457dfa7e66b99fdffdf5afaab8ba34b", 4942856416),),
    "granite31": (GGUFFile("bartowski/granite-3.1-8b-instruct-GGUF", "granite-3.1-8b-instruct-Q4_K_M.gguf",
                           "b72cfca8e30f23af77f922ce18d6fe1a5d4925907dddf7249c0cabc2739d48c8", 4942858720),),
    "granite32": (GGUFFile("bartowski/ibm-granite_granite-3.2-8b-instruct-GGUF",
                           "ibm-granite_granite-3.2-8b-instruct-Q4_K_M.gguf",
                           "bd041eb5bc5e75e4f9a863372000046fd6490374f4dec07f399ca152b1df09c2", 4942859808),),
}


def files_for(model: str, quant: str) -> tuple[GGUFFile, ...]:
    table = {"Q8_0": Q8_SOURCES, "Q4_K_M": Q4_K_M_SOURCES}[quant]
    return table[model]
