"""Install the EXACT pinned llama-cpp-python (CUDA) on Kaggle, reusing a
previously built wheel when one is attached as an Input.

Order:
  1. a wheel of exactly the pinned version found under /kaggle/input
     (a dataset you made from session 1's /kaggle/working/wheels/) ->
     pip install it, verify in a fresh interpreter;
  2. otherwise (or if that wheel does not install/verify on this image)
     build the pinned version from source for the T4 with `pip wheel`,
     save the wheel to ``wheel_out_dir`` (under /kaggle/working, so you can
     download it), install it, verify.

It never installs a different version: any failure raises. The wheel's
version is checked from its file name AND from the installed package.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BUILD_CMAKE_ARGS = "-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=75"
_WHEEL_RE = re.compile(r"^llama_cpp_python-([^-]+)-([^-]+)-([^-]+)-([^-]+)\.whl$")


def wheel_version(filename: str) -> str | None:
    m = _WHEEL_RE.match(Path(filename).name)
    return m.group(1) if m else None


def wheel_python_tag(filename: str) -> str | None:
    m = _WHEEL_RE.match(Path(filename).name)
    return m.group(2) if m else None


def find_wheels(input_root, version: str) -> list[Path]:
    """Wheels of exactly ``version`` under input_root, best match first
    (wheels whose python tag matches this interpreter come first)."""
    root = Path(input_root)
    if not root.exists():
        return []
    found = [p for p in root.rglob("llama_cpp_python-*.whl") if wheel_version(p.name) == version]
    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    return sorted(found, key=lambda p: (wheel_python_tag(p.name) != tag, p.name))


def installed_version() -> str | None:
    import importlib.metadata as md

    try:
        return md.version("llama-cpp-python")
    except md.PackageNotFoundError:
        return None


def verify_in_fresh_interpreter(version: str) -> tuple[bool, str]:
    r = subprocess.run([sys.executable, "-c",
                        "import llama_cpp; print(llama_cpp.__version__, llama_cpp.llama_supports_gpu_offload())"],
                       capture_output=True, text=True)
    parts = r.stdout.split()
    if r.returncode != 0 or len(parts) < 2:
        return False, f"import failed: {(r.stderr or r.stdout)[-600:]}"
    ver, gpu = parts[0], parts[1]
    if ver != version:
        return False, f"installed version {ver}, need {version}"
    if gpu != "True":
        return False, "built WITHOUT CUDA offload; refusing to run on CPU"
    return True, f"llama-cpp-python {ver} with GPU offload"


def _pip(*args: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "pip", *args], capture_output=True, text=True, env=env)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_llama_cpp(version: str, input_root="/kaggle/input", wheel_out_dir="/kaggle/working/wheels") -> dict:
    """Returns {"how": ..., "wheel": ..., "message": ...}; raises RuntimeError
    (never substitutes another version) if the pinned one cannot be had."""
    log: list[str] = []
    for w in find_wheels(input_root, version):
        r = _pip("install", "--no-cache-dir", "--force-reinstall", str(w))
        ok, msg = verify_in_fresh_interpreter(version) if r.returncode == 0 else (False, r.stderr[-400:])
        if ok:
            return {"how": "installed from attached wheel", "wheel": str(w), "message": msg}
        log.append(f"attached wheel {w.name} unusable here: {msg}")
        _pip("uninstall", "-y", "llama-cpp-python")

    out = Path(wheel_out_dir)
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, CMAKE_ARGS=BUILD_CMAKE_ARGS, FORCE_CMAKE="1")
    with tempfile.TemporaryDirectory() as td:
        r = _pip("wheel", f"llama-cpp-python=={version}", "--no-deps", "--no-cache-dir", "-w", td, env=env)
        built = sorted(Path(td).glob("llama_cpp_python-*.whl"))
        if r.returncode != 0 or not built:
            print(r.stdout[-3000:], r.stderr[-3000:])
            raise RuntimeError(f"llama-cpp-python=={version} could not be built with CUDA on this image. "
                               "NOT substituting another version -- report this to the project owner. "
                               + " ".join(log))
        wheel = out / built[0].name
        shutil.copy2(built[0], wheel)
    if wheel_version(wheel.name) != version:
        raise RuntimeError(f"built wheel {wheel.name} is not version {version}")
    r = _pip("install", "--no-cache-dir", "--force-reinstall", str(wheel))
    ok, msg = verify_in_fresh_interpreter(version) if r.returncode == 0 else (False, r.stderr[-400:])
    if not ok:
        raise RuntimeError(f"built wheel does not verify: {msg}. NOT substituting another version.")
    try:
        nvcc = subprocess.run(["nvcc", "--version"], capture_output=True, text=True).stdout.strip().splitlines()
    except OSError:  # nvcc not on PATH: info only, must not lose the freshly built wheel
        nvcc = []
    (out / "WHEEL_INFO.json").write_text(json.dumps({
        "wheel": wheel.name, "sha256": _sha256(wheel), "size_bytes": wheel.stat().st_size, "version": version,
        "python": sys.version.split()[0], "cmake_args": BUILD_CMAKE_ARGS,
        "nvcc": nvcc[-1] if nvcc else None, "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")
    return {"how": "built from source", "wheel": str(wheel), "message": msg, "notes": log}
