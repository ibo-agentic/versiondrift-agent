"""Build the Kaggle run environment so it matches the laptop's, instead of
using whatever Python/packages Kaggle's image ships.

What "matches the laptop" means here (all read from the laptop's .venv):
  * Python 3.12.12 (kaggle_plan.LAPTOP_PYTHON). Kaggle's own default may be
    3.13, so a dedicated uv-managed venv with exactly that interpreter is
    created; the notebook's own Python is never modified.
  * llama-cpp-python 0.3.35 as the laptop's actual build: abetlen's
    **v0.3.35-cu125** release wheel (the laptop's DLLs are byte-identical to
    that release's Windows wheel). The Linux wheel of the same release is
    downloaded, size + SHA-256 checked against GitHub's asset digest, and
    installed. No compilation. The wheel is py3-none, so it does not depend
    on the Python minor version.
  * jinja2, numpy, ... pinned to the laptop's versions (kaggle_plan.LAPTOP_PINS)
    and the laptop's pip CUDA runtime libs (12.9), falling back to Kaggle's
    system CUDA libs only if those do not verify. Which one was used is
    recorded in every run manifest.

The pinned llama-cpp-python version is never changed: any failure stops with
an error. Source: (1) an attached wheel dataset, (2) the release wheel above,
(3) last resort, build 0.3.35 from source with the release workflow's flags.
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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import kaggle_plan as plan

# Mirrors abetlen's build-wheels-cuda.yaml flags (arch list reduced to the T4;
# the architecture list does not change what an sm_75 device executes).
BUILD_CMAKE_ARGS = (
    "-DGGML_CUDA_FORCE_MMQ=ON -DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=75-real "
    "-DCMAKE_CUDA_FLAGS=-allow-unsupported-compiler -DCMAKE_CUDA_FLAGS_INIT=-allow-unsupported-compiler "
    "-DGGML_AVX2=off -DGGML_FMA=off -DGGML_F16C=off -DGGML_OPENMP=OFF"
)
_WHEEL_RE = re.compile(r"^llama_cpp_python-([^-]+)-([^-]+)-([^-]+)-([^-]+)\.whl$")


@dataclass
class Env:
    python: str
    env: dict = field(default_factory=dict)     # extra environment for worker processes
    info: dict = field(default_factory=dict)


# ----------------------------------------------------------------- helpers
def _run(cmd, env=None, timeout=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)


def wheel_version(filename: str) -> str | None:
    m = _WHEEL_RE.match(Path(filename).name)
    return m.group(1) if m else None


def find_wheels(input_root, version: str) -> list[Path]:
    """Wheels of exactly ``version`` under input_root."""
    root = Path(input_root)
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("llama_cpp_python-*.whl") if wheel_version(p.name) == version)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_python(actual: str, expected: str, allow_mismatch: bool = False) -> str | None:
    """None if actual == expected (full version). Otherwise raise with a clear
    message, or (allow_mismatch) return a warning string that the caller records."""
    if actual == expected:
        return None
    msg = (f"Python in the run environment is {actual}, but the laptop runs {expected}. "
           f"Results must be produced on the laptop's interpreter. "
           + ("Continuing because ALLOW_PYTHON_MISMATCH=True; this is recorded in every manifest."
              if allow_mismatch else
              "Stopping. (The notebook normally creates a uv venv with exactly that version; if that failed, "
              "see kaggle/README.md. Set ALLOW_PYTHON_MISMATCH=True only to knowingly accept the difference.)"))
    if allow_mismatch:
        return msg
    raise RuntimeError(msg)


def nvidia_lib_dirs(python: str) -> list[str]:
    site = subprocess.run([python, "-c", "import sysconfig;print(sysconfig.get_paths()['purelib'])"],
                          capture_output=True, text=True).stdout.strip()
    base = Path(site) / "nvidia"
    return sorted(str(p) for p in base.glob("*/lib") if p.is_dir()) if site else []


def verify(python: str, version: str, extra_env: dict | None = None) -> tuple[bool, str, dict]:
    """Fresh-interpreter check: python version, llama_cpp version, GPU offload."""
    code = ("import sys, llama_cpp, jinja2, numpy; "
            "print(sys.version.split()[0], llama_cpp.__version__, llama_cpp.llama_supports_gpu_offload(), "
            "jinja2.__version__, numpy.__version__)")
    env = dict(os.environ, **(extra_env or {}))
    r = _run([python, "-c", code], env=env)
    parts = r.stdout.split()
    if r.returncode != 0 or len(parts) < 5:
        return False, f"import failed: {(r.stderr or r.stdout)[-700:]}", {}
    py, ver, gpu, jj, npv = parts[:5]
    info = {"python": py, "llama_cpp_python": ver, "gpu_offload": gpu, "jinja2": jj, "numpy": npv}
    if ver != version:
        return False, f"installed llama-cpp-python {ver}, need {version}", info
    if gpu != "True":
        return False, "llama-cpp-python has no GPU offload here (CUDA libs not found?); refusing to run on CPU", info
    return True, f"python {py}, llama-cpp-python {ver} with GPU offload, jinja2 {jj}, numpy {npv}", info


def download_wheel(spec: dict, dest_dir: Path, log=print) -> Path:
    """curl the release wheel and verify size + SHA-256 (GitHub's asset digest)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / spec["filename"]
    for attempt in (1, 2):
        if not dest.exists():
            log(f"downloading {spec['url']} ({spec['size'] / 1e9:.2f} GB)")
            for _ in range(5):
                rc = subprocess.run(["curl", "-L", "--fail", "-C", "-", "--retry", "5", "--retry-delay", "5",
                                     "-sS", "-o", str(dest), spec["url"]]).returncode
                if rc == 0:
                    break
            else:
                raise RuntimeError(f"could not download {spec['url']}")
        if dest.stat().st_size == spec["size"] and sha256_file(dest) == spec["sha256"]:
            return dest
        log(f"wheel size/sha256 mismatch on attempt {attempt}; deleting")
        dest.unlink(missing_ok=True)
    raise RuntimeError(f"{spec['filename']}: SHA-256 does not match the published release digest")


# --------------------------------------------------------------- the build
def build_env(version: str, venv_dir="/kaggle/temp/venv", work_dir="/kaggle/temp/wheels_dl",
              input_root="/kaggle/input", wheel_out_dir="/kaggle/working/wheels",
              expected_python: str = plan.LAPTOP_PYTHON, allow_python_mismatch: bool = False,
              log=print) -> Env:
    notes: list[str] = []
    # 1. uv (installer + Python manager); only touches the notebook kernel to add `uv`
    if not shutil.which("uv"):
        r = _run([sys.executable, "-m", "pip", "install", "-q", "uv"])
        if r.returncode != 0 or not shutil.which("uv"):
            raise RuntimeError(f"could not install uv: {r.stderr[-400:]}")

    # 2. dedicated venv with the laptop's exact interpreter
    venv = Path(venv_dir)
    shutil.rmtree(venv, ignore_errors=True)
    r = _run(["uv", "venv", "--seed", "--python", expected_python, str(venv)])
    py = str(venv / "bin" / "python")
    if r.returncode != 0 or not Path(py).exists():
        raise RuntimeError(f"could not create a Python {expected_python} venv with uv: {(r.stderr or r.stdout)[-600:]}. "
                           "Kaggle's own Python is not used silently; see kaggle/README.md.")
    actual = _run([py, "-c", "import sys;print(sys.version.split()[0])"]).stdout.strip()
    warn = check_python(actual, expected_python, allow_python_mismatch)
    if warn:
        notes.append(warn)

    # 3. pinned pure-python deps (+ the laptop's pip CUDA runtime libs)
    pins = list(plan.LAPTOP_PINS)
    cuda_pins = list(plan.LAPTOP_CUDA_PINS)
    r = _run(["uv", "pip", "install", "--python", py, *pins, *cuda_pins])
    have_pip_cuda = r.returncode == 0
    if not have_pip_cuda:
        notes.append(f"pip CUDA runtime pins not installable ({r.stderr[-200:]}); will use system CUDA libs")
        r = _run(["uv", "pip", "install", "--python", py, *pins])
        if r.returncode != 0:
            raise RuntimeError(f"could not install pinned packages: {r.stderr[-600:]}")

    # 4. llama-cpp-python wheel: attached dataset -> release wheel -> source build
    wheel: Path | None = None
    how = ""
    attached = find_wheels(input_root, version)
    if attached:
        wheel, how = attached[0], "attached wheel dataset"
    else:
        try:
            wheel, how = download_wheel(plan.LLAMA_WHEEL, Path(work_dir), log), "release wheel v0.3.35-cu125"
        except RuntimeError as exc:
            notes.append(f"release wheel unavailable: {exc}")
    if wheel is not None:
        r = _run(["uv", "pip", "install", "--python", py, "--no-deps", "--reinstall", str(wheel)])
        if r.returncode != 0:
            notes.append(f"{how} did not install: {r.stderr[-300:]}")
            wheel = None
    if wheel is None:
        out = Path(wheel_out_dir)
        out.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, CMAKE_ARGS=BUILD_CMAKE_ARGS, FORCE_CMAKE="1")
        with tempfile.TemporaryDirectory() as td:
            r = _run([py, "-m", "pip", "wheel", f"llama-cpp-python=={version}", "--no-deps", "--no-cache-dir",
                      "-w", td], env=env)
            built = sorted(Path(td).glob("llama_cpp_python-*.whl"))
            if r.returncode != 0 or not built:
                raise RuntimeError(f"llama-cpp-python=={version} is not obtainable here (attached wheel, release "
                                   f"wheel and source build all failed). NOT substituting another version. "
                                   f"Notes: {' | '.join(notes)} | build: {r.stderr[-800:]}")
            wheel = out / built[0].name
            shutil.copy2(built[0], wheel)
        (out / "WHEEL_INFO.json").write_text(json.dumps({
            "wheel": wheel.name, "sha256": sha256_file(wheel), "version": version, "python": actual,
            "cmake_args": BUILD_CMAKE_ARGS,
            "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}, indent=2), encoding="utf-8")
        r = _run(["uv", "pip", "install", "--python", py, "--no-deps", "--reinstall", str(wheel)])
        if r.returncode != 0:
            raise RuntimeError(f"built wheel did not install: {r.stderr[-400:]}")
        how = "built from source (fallback)"
    if wheel_version(wheel.name) != version:
        raise RuntimeError(f"wheel {wheel.name} is not version {version}")

    # 5. verify, preferring the laptop's CUDA runtime libs, then the system's
    attempts = []
    if have_pip_cuda:
        dirs = nvidia_lib_dirs(py)
        ld = ":".join(dirs + [os.environ.get("LD_LIBRARY_PATH", "")]).strip(":")
        attempts.append(({"LD_LIBRARY_PATH": ld, "KAGGLE_CUDA_RUNTIME_SOURCE": "pip nvidia-*-cu12 (laptop pins)"}))
    attempts.append({"KAGGLE_CUDA_RUNTIME_SOURCE": "system CUDA libraries of the Kaggle image"})
    last = ""
    for extra in attempts:
        ok, msg, info = verify(py, version, extra)
        if ok:
            return Env(python=py, env=extra, info={
                "how": how, "wheel": str(wheel), "message": msg, "notes": notes, "python": actual,
                "cuda_runtime_source": extra["KAGGLE_CUDA_RUNTIME_SOURCE"], **info})
        last = msg
        notes.append(f"verify with [{extra['KAGGLE_CUDA_RUNTIME_SOURCE']}] failed: {msg}")
    raise RuntimeError(f"llama-cpp-python {version} does not work in the Python {actual} venv: {last}. "
                       "NOT substituting another version. " + " | ".join(notes))
