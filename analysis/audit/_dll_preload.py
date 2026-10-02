"""Windows DLL-loading workaround for this machine only. NOT a project file;
lives under analysis/audit/ and is imported explicitly by the runner
wrapper, never by upgradecanary/ itself.

On this machine, `import llama_cpp` fails ("Failed to load shared library
...llama.dll ... or one of its dependencies") even with the CUDA runtime
dirs registered (upgradecanary/model/llama_cpp_client.py's own
_add_bundled_cuda_dll_dirs). Loading each DLL in llama_cpp/lib individually,
in dependency order, before letting `llama_cpp` do its own import works
around it (verified interactively: each individual ctypes.CDLL succeeds,
and once they're resident, `import llama_cpp` succeeds too).

Call preload() once, before importing anything from llama_cpp or
upgradecanary.model.llama_cpp_client, anywhere that needs to run a real
model on this machine.
"""

from __future__ import annotations

import ctypes
import os
import sys

_DONE = False


def preload() -> None:
    global _DONE
    if _DONE:
        return
    base = sys.prefix
    dirs = [
        os.path.join(base, "Lib", "site-packages", "nvidia", "cuda_runtime", "bin"),
        os.path.join(base, "Lib", "site-packages", "nvidia", "cublas", "bin"),
        os.path.join(base, "Lib", "site-packages", "llama_cpp", "lib"),
    ]
    for d in dirs:
        if os.path.isdir(d):
            os.add_dll_directory(d)

    libdir = os.path.join(base, "Lib", "site-packages", "llama_cpp", "lib")
    order = ["ggml-base.dll", "ggml-cpu.dll", "ggml-cuda.dll", "ggml.dll", "mtmd.dll", "llama.dll"]
    for name in order:
        path = os.path.join(libdir, name)
        if os.path.exists(path):
            ctypes.CDLL(path)
    _DONE = True
