"""Run plan for the Kaggle (2x T4) F5 / R_F5 / hardware-check runs.

Pure data + small pure functions: no I/O, no model, no GPU. Imported by the
Kaggle worker, by scripts/import_kaggle_results.py and by
scripts/compare_kaggle_hwcheck.py, so all three agree on what a "run" is.

Nothing here changes an experiment setting. Every config is built by the
laptop's own ``scripts.real_run_one.build_config`` (see kaggle_run_one.py);
this file only says WHICH (protocol, model, quant, suite) runs to do and
WHERE each GGUF comes from.

Expected SHA-256 / sizes were read from each Hugging Face repo's tree API
(``lfs.oid``) on 2026-10-13. The Kaggle worker recomputes the SHA-256 of the
downloaded bytes and refuses to run a model whose hash differs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# llama-cpp-python version used for every laptop run (run_manifest.json,
# model_backend.llama_cpp_python_version). The notebook asserts this exact
# string after install and stops otherwise -- it never swaps versions.
LLAMA_CPP_PYTHON_VERSION = "0.3.35"

SEED = 1234
SUITES = ("synthetic", "bfcl_simple", "bfcl_multiple")
EXPECTED_RECORDS_PER_RUN = 900  # 100 tasks x 3 conditions x 3 trials

HF_RESOLVE = "https://huggingface.co/{repo}/resolve/main/{filename}"

# result-folder name -> (base laptop protocol whose config is used, quant label)
PROTOCOLS = {
    "KAGGLE_HWCHECK": {"base": "D", "quant": None},      # D config, Q4_K_M, as on laptop
    "F5": {"base": "D", "quant": "Q8_0"},                # D config + Q8_0
    "R_F5": {"base": "R", "quant": "Q8_0"},              # R config + Q8_0
}

# Expected run_factors per result-folder protocol (checked by the importer).
EXPECTED_FACTORS = {
    "KAGGLE_HWCHECK": {"F1_max_tokens": 256, "F4_constrained_decoding": "off",
                       "F5_quant_level": "unspecified", "F3_prompt_format": "shared"},
    "F5": {"F1_max_tokens": 256, "F4_constrained_decoding": "off",
           "F5_quant_level": "Q8_0", "F3_prompt_format": "shared"},
    "R_F5": {"F1_max_tokens": 1024, "F4_constrained_decoding": "generic_json",
             "F5_quant_level": "Q8_0", "F3_prompt_format": "shared"},
}

# Laptop folder that the hardware check is compared against.
HWCHECK_LAPTOP_PROTOCOL = "D"


@dataclass(frozen=True)
class GGUFFile:
    repo: str
    filename: str
    sha256: str
    size: int

    @property
    def url(self) -> str:
        return HF_RESOLVE.format(repo=self.repo, filename=self.filename)


@dataclass(frozen=True)
class Bundle:
    """One model file (set) plus every run that uses it, so each file is
    downloaded once, used for all its runs, then deleted (T4 disk budget)."""
    name: str                       # e.g. "llama31__Q8_0"
    model_key: str
    quant: str                      # "Q8_0" | "Q4_K_M"
    files: tuple[GGUFFile, ...]     # files[0] is the one llama.cpp is pointed at
    jobs: tuple[tuple[str, str], ...]  # (result protocol, suite)


# ---- Q8_0 sources (F5 / R_F5) ---------------------------------------------
# Mistral: the itlwas repos used for Q4_K_M ship ONLY Q4_K_M (verified via the
# HF API). QuantFactory is the one uploader that has v0.1, v0.2 AND v0.3 at
# Q8_0 with the same naming/pipeline, so all three Mistral versions stay
# matched on uploader -- but it is NOT the Q4_K_M uploader. DEVIATIONS draft.
Q8_SOURCES: dict[str, tuple[GGUFFile, ...]] = {
    "mistral_v01": (GGUFFile("QuantFactory/Mistral-7B-Instruct-v0.1-GGUF", "Mistral-7B-Instruct-v0.1.Q8_0.gguf",
                             "eb1d45a507b3f74bf9ae16189be93dcacab1dd4577f134565913b024737a7a6a", 7695857888),),
    "mistral_v02": (GGUFFile("QuantFactory/Mistral-7B-Instruct-v0.2-GGUF", "Mistral-7B-Instruct-v0.2.Q8_0.gguf",
                             "7245da8144b0636e0a776cb3b0b706421bb02d2034b1c5e8de19cd37e05a54d9", 7695857888),),
    "mistral_v03": (GGUFFile("QuantFactory/Mistral-7B-Instruct-v0.3-GGUF", "Mistral-7B-Instruct-v0.3.Q8_0.gguf",
                             "c19dd08e2787e8337d3b58f035cfc737d4510bde5dad7415dabed80bde9d1b80", 7702564800),),
    "qwen2": (GGUFFile("Qwen/Qwen2-7B-Instruct-GGUF", "qwen2-7b-instruct-q8_0.gguf",
                       "945823750c8eb6aa685692753ae90cd9551a56618d03051241268f53cdbd8352", 8098522912),),
    # Qwen2.5 Q8_0 is a 3-part split GGUF; llama.cpp loads from part 1 when
    # the other parts sit beside it (same as the laptop's 2-part Q4_K_M).
    "qwen25": (
        GGUFFile("Qwen/Qwen2.5-7B-Instruct-GGUF", "qwen2.5-7b-instruct-q8_0-00001-of-00003.gguf",
                 "26e30cb4559f0d9e9e11f34d351292af6f42199ce3fa742b5e7c5af4bc35b0f0", 3980069248),
        GGUFFile("Qwen/Qwen2.5-7B-Instruct-GGUF", "qwen2.5-7b-instruct-q8_0-00002-of-00003.gguf",
                 "e93856ce0cb05d5abd698eb439c0fea3acd412d9040f5ab7d2d4d088add5287d", 3942935680),
        GGUFFile("Qwen/Qwen2.5-7B-Instruct-GGUF", "qwen2.5-7b-instruct-q8_0-00003-of-00003.gguf",
                 "8f29c0e4173d4d92d35c52a7c5807c34a3edfe6bb078ea785d145b7d88c16e44", 175520480),
    ),
    "qwen3": (GGUFFile("Qwen/Qwen3-8B-GGUF", "Qwen3-8B-Q8_0.gguf",
                       "408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6", 8709518112),),
    "llama3": (GGUFFile("bartowski/Meta-Llama-3-8B-Instruct-GGUF", "Meta-Llama-3-8B-Instruct-Q8_0.gguf",
                        "583c616da14b82930f887f991ab446711da0b029166200b67892d7c9f8f45958", 8540770880),),
    "llama31": (GGUFFile("bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", "Meta-Llama-3.1-8B-Instruct-Q8_0.gguf",
                         "9da71c45c90a821809821244d4971e5e5dfad7eb091f0b8ff0546392393b6283", 8540775840),),
    "granite30": (GGUFFile("bartowski/granite-3.0-8b-instruct-GGUF", "granite-3.0-8b-instruct-Q8_0.gguf",
                           "b470554539f90a26c0a2d23d7df7398a4f46cff6f5cecfb2778fc110ff6483cd", 8684244096),),
    "granite31": (GGUFFile("bartowski/granite-3.1-8b-instruct-GGUF", "granite-3.1-8b-instruct-Q8_0.gguf",
                           "70d56efa48c46d941790f17fa0486528e9aab8b82b4e453d2e09e932570a092a", 8684246400),),
    "granite32": (GGUFFile("bartowski/ibm-granite_granite-3.2-8b-instruct-GGUF",
                           "ibm-granite_granite-3.2-8b-instruct-Q8_0.gguf",
                           "e93b442ba2ce753cf1a3904c6ebd1ccfc3f961f5eb8ccc34b9a7e2e4cc1d14a4", 8684247488),),
}

# ---- Q4_K_M sources for the hardware check: the SAME files as the laptop ----
# (hashes match docs/model_manifest.md sections 2 and 5).
Q4_SOURCES: dict[str, tuple[GGUFFile, ...]] = {
    "llama3": (GGUFFile("bartowski/Meta-Llama-3-8B-Instruct-GGUF", "Meta-Llama-3-8B-Instruct-Q4_K_M.gguf",
                        "8ba9baf3a7345f705a11878397500fb25174034f0fd784e83aa4a96aaa47735f", 4920734272),),
    "llama31": (GGUFFile("bartowski/Meta-Llama-3.1-8B-Instruct-GGUF", "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
                         "7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c", 4920739232),),
}

# Hardware check = an adjacent upgrade pair (llama3 -> llama31), so the
# machine-to-machine difference can be read directly against a pair difference.
HWCHECK_MODELS = ("llama3", "llama31")
# Held-out 8B models (R_F5 scope). Order is the order in the user's request.
HELD_OUT_8B = ("llama3", "llama31", "granite30", "granite31", "granite32")
ALL_Q8_MODELS = ("mistral_v01", "mistral_v02", "mistral_v03", "qwen2", "qwen25", "qwen3",
                 "llama3", "llama31", "granite30", "granite31", "granite32")

# Scheduling order inside a phase: longest bundles first so two GPUs finish
# together (qwen3 = thinking on = slowest; held-out models carry 6 runs).
_Q8_ORDER = ("qwen3",) + HELD_OUT_8B + ("qwen25", "qwen2", "mistral_v03", "mistral_v02", "mistral_v01")
assert set(_Q8_ORDER) == set(ALL_Q8_MODELS) and len(_Q8_ORDER) == len(ALL_Q8_MODELS)


def build_bundles(phases=("hwcheck", "F5", "R_F5")) -> list[Bundle]:
    bundles: list[Bundle] = []
    if "hwcheck" in phases:
        for m in HWCHECK_MODELS:
            bundles.append(Bundle(
                name=f"{m}__Q4_K_M", model_key=m, quant="Q4_K_M", files=Q4_SOURCES[m],
                jobs=tuple(("KAGGLE_HWCHECK", s) for s in SUITES),
            ))
    for m in _Q8_ORDER:
        jobs: list[tuple[str, str]] = []
        if "F5" in phases:
            jobs += [("F5", s) for s in SUITES]
        if "R_F5" in phases and m in HELD_OUT_8B:
            jobs += [("R_F5", s) for s in SUITES]
        if jobs:
            bundles.append(Bundle(name=f"{m}__Q8_0", model_key=m, quant="Q8_0",
                                  files=Q8_SOURCES[m], jobs=tuple(jobs)))
    return bundles


def all_jobs(phases=("hwcheck", "F5", "R_F5")) -> list[tuple[str, str, str]]:
    return [(p, b.model_key, s) for b in build_bundles(phases) for (p, s) in b.jobs]


def lf_normalized_sha256(path) -> str:
    """SHA-256 of a text file with CRLF -> LF, so a Windows checkout and a
    Linux ``git archive`` of the same commit hash identically."""
    import hashlib
    from pathlib import Path

    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def run_rel_dir(protocol: str, model_key: str, suite: str) -> str:
    """Same layout as the laptop: results_v2/<protocol>/<model>/<suite>/."""
    return f"results_v2/{protocol}/{model_key}/{suite}"


def experiment_name(protocol: str, model_key: str, suite: str) -> str:
    """Matches the laptop's f"upgradecanary-real-{protocol}-{model}-{suite}"."""
    return f"upgradecanary-real-{protocol}-{model_key}-{suite}"
