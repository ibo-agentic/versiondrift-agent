"""Do not even import tests that load llama_cpp's real llama.dll (CUDA
backend) unless explicitly requested -- another session may be using the
GPU. tests/test_native_tool_rendering.py runs ``_dll_preload.preload()`` at
import time, so it must be skipped at collection, not just at run time.
Opt in with ``pytest --run-llama-dll``.
"""

LLAMA_DLL_TEST_FILES = {"test_native_tool_rendering.py"}


def pytest_addoption(parser):
    parser.addoption("--run-llama-dll", action="store_true", default=False,
                     help="also collect/run tests that import llama_cpp (load llama.dll)")


def pytest_ignore_collect(collection_path, config):
    if collection_path.name in LLAMA_DLL_TEST_FILES and not config.getoption("--run-llama-dll"):
        return True
    return None
