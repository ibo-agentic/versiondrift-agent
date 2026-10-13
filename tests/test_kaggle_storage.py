"""Kaggle storage rules (GGUFs on temp disk, deleted after use) and wheel
lookup. Fake files / monkeypatched subprocess only; no model, no GPU."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "kaggle"))

import kaggle_install as ki  # noqa: E402
import kaggle_plan as plan  # noqa: E402
import kaggle_worker as kw  # noqa: E402


# ------------------------------------------------- environment / wheel
def test_plan_wheel_is_the_laptops_build():
    w = plan.LLAMA_WHEEL
    assert plan.LAPTOP_PYTHON == "3.12.12"
    assert "v0.3.35-cu125" in w["url"] and w["url"].endswith(w["filename"])
    assert "manylinux" in w["filename"] and "0.3.35" in w["filename"]
    assert len(w["sha256"]) == 64 and int(w["sha256"], 16) >= 0 and w["size"] > 1_000_000_000
    assert "numpy==2.5.3" in plan.LAPTOP_PINS and "jinja2==3.1.6" in plan.LAPTOP_PINS


def test_check_python():
    import pytest

    assert ki.check_python("3.12.12", "3.12.12") is None
    with pytest.raises(RuntimeError, match="laptop runs 3.12.12"):
        ki.check_python("3.13.15", "3.12.12")
    warn = ki.check_python("3.13.15", "3.12.12", allow_mismatch=True)
    assert "ALLOW_PYTHON_MISMATCH" in warn


def test_find_wheels_exact_version_only(tmp_path):
    d = tmp_path / "input" / "llama-cpp-wheel"
    d.mkdir(parents=True)
    for name in ("llama_cpp_python-0.3.35-py3-none-manylinux_2_35_x86_64.whl",
                 "llama_cpp_python-0.3.36-py3-none-manylinux_2_35_x86_64.whl",
                 "llama_cpp_python-0.3.3-py3-none-manylinux_2_35_x86_64.whl"):
        (d / name).write_bytes(b"x")
    found = ki.find_wheels(tmp_path / "input", "0.3.35")
    assert [p.name for p in found] == ["llama_cpp_python-0.3.35-py3-none-manylinux_2_35_x86_64.whl"]
    assert ki.find_wheels(tmp_path / "nowhere", "0.3.35") == []


class FakeToolchain:
    """Stands in for uv/pip/the venv interpreter; records every command."""

    def __init__(self, tmp_path, python_version="3.12.12", pip_wheel_works=True, venv_works=True):
        self.cmds, self.tmp = [], tmp_path
        self.python_version, self.pip_wheel_works, self.venv_works = python_version, pip_wheel_works, venv_works

    def run(self, cmd, env=None, timeout=None):
        self.cmds.append((list(cmd), env))
        ok = types.SimpleNamespace(returncode=0, stdout="", stderr="")
        if cmd[:2] == ["uv", "venv"]:
            if not self.venv_works:
                return types.SimpleNamespace(returncode=1, stdout="", stderr="no python")
            py = Path(cmd[-1]) / "bin" / "python"
            py.parent.mkdir(parents=True, exist_ok=True)
            py.write_bytes(b"")
            return ok
        if len(cmd) >= 3 and cmd[1] == "-c" and "sys.version" in cmd[2]:
            return types.SimpleNamespace(returncode=0, stdout=self.python_version + "\n", stderr="")
        if cmd[1:3] == ["-m", "pip"] and cmd[3] == "wheel":
            if not self.pip_wheel_works:
                return types.SimpleNamespace(returncode=1, stdout="", stderr="nvcc: unsupported GNU version")
            out = Path(cmd[cmd.index("-w") + 1])
            (out / "llama_cpp_python-0.3.35-py3-none-linux_x86_64.whl").write_bytes(b"built")
        return ok

    def kinds(self):
        out = []
        for c, _ in self.cmds:
            if c[:2] == ["uv", "venv"]:
                out.append("venv")
            elif c[:3] == ["uv", "pip", "install"]:
                out.append("uv-install")
            elif c[1:3] == ["-m", "pip"] and c[3] == "wheel":
                out.append("source-build")
        return out


def _patch_env(monkeypatch, tc, wheel_ok=True, verify_results=None):
    monkeypatch.setattr(ki, "_run", tc.run)
    monkeypatch.setattr(ki.shutil, "which", lambda name: "uv")
    monkeypatch.setattr(ki, "nvidia_lib_dirs", lambda py: ["/venv/site-packages/nvidia/cublas/lib"])
    calls = {"download": 0}

    def fake_download(spec, dest, log=print):
        calls["download"] += 1
        if not wheel_ok:
            raise RuntimeError("github unreachable")
        dest.mkdir(parents=True, exist_ok=True)
        p = dest / spec["filename"]
        p.write_bytes(b"w")
        return p

    monkeypatch.setattr(ki, "download_wheel", fake_download)
    results = iter(verify_results or [(True, "python 3.12.12, llama-cpp-python 0.3.35 with GPU offload", {})])
    monkeypatch.setattr(ki, "verify", lambda py, v, extra=None: next(results))
    return calls


def _build(tmp_path, **kw):
    return ki.build_env("0.3.35", venv_dir=str(tmp_path / "venv"), work_dir=str(tmp_path / "dl"),
                        input_root=str(tmp_path / "in"), wheel_out_dir=str(tmp_path / "out"),
                        log=lambda *_: None, **kw)


def test_release_wheel_path_creates_laptop_python_venv_and_never_compiles(tmp_path, monkeypatch):
    tc = FakeToolchain(tmp_path)
    calls = _patch_env(monkeypatch, tc)
    env = _build(tmp_path)
    assert tc.kinds() == ["venv", "uv-install", "uv-install"]   # pins, then the wheel; no source build
    venv_cmd = tc.cmds[0][0]
    assert venv_cmd[:2] == ["uv", "venv"] and venv_cmd[venv_cmd.index("--python") + 1] == "3.12.12"
    pins_cmd = next(c for c, _ in tc.cmds if c[:3] == ["uv", "pip", "install"])
    assert "numpy==2.5.3" in pins_cmd and "nvidia-cublas-cu12==12.9.2.10" in pins_cmd
    wheel_cmd = [c for c, _ in tc.cmds if c[:3] == ["uv", "pip", "install"]][1]
    assert "--no-deps" in wheel_cmd and wheel_cmd[-1].endswith("manylinux_2_35_x86_64.whl")
    assert calls["download"] == 1
    assert "pip nvidia" in env.env["KAGGLE_CUDA_RUNTIME_SOURCE"] and "cublas/lib" in env.env["LD_LIBRARY_PATH"]
    assert env.info["how"].startswith("release wheel")


def test_falls_back_to_system_cuda_libs_when_pip_libs_do_not_verify(tmp_path, monkeypatch):
    tc = FakeToolchain(tmp_path)
    _patch_env(monkeypatch, tc, verify_results=[(False, "libcublas not found", {}), (True, "ok", {})])
    env = _build(tmp_path)
    assert env.env["KAGGLE_CUDA_RUNTIME_SOURCE"].startswith("system CUDA")
    assert any("failed" in n for n in env.info["notes"])


def test_wrong_python_stops_with_clear_message(tmp_path, monkeypatch):
    import pytest

    tc = FakeToolchain(tmp_path, python_version="3.13.15")
    _patch_env(monkeypatch, tc)
    with pytest.raises(RuntimeError, match="laptop runs 3.12.12"):
        _build(tmp_path)
    assert "uv-install" not in tc.kinds()    # stopped before installing anything


def test_python_mismatch_can_be_accepted_explicitly(tmp_path, monkeypatch):
    tc = FakeToolchain(tmp_path, python_version="3.13.15")
    _patch_env(monkeypatch, tc)
    env = _build(tmp_path, allow_python_mismatch=True)
    assert any("ALLOW_PYTHON_MISMATCH" in n for n in env.info["notes"])


def test_venv_creation_failure_does_not_fall_back_to_kaggle_python(tmp_path, monkeypatch):
    import pytest

    tc = FakeToolchain(tmp_path, venv_works=False)
    _patch_env(monkeypatch, tc)
    with pytest.raises(RuntimeError, match="not used silently"):
        _build(tmp_path)


def test_unreachable_release_wheel_builds_same_version_with_workflow_flags(tmp_path, monkeypatch):
    tc = FakeToolchain(tmp_path)
    _patch_env(monkeypatch, tc, wheel_ok=False)
    env = _build(tmp_path)
    assert env.info["how"].startswith("built from source")
    cmd, e = next((c, e) for c, e in tc.cmds if c[1:3] == ["-m", "pip"] and c[3] == "wheel")
    assert "llama-cpp-python==0.3.35" in cmd
    assert "-DGGML_CUDA_FORCE_MMQ=ON" in e["CMAKE_ARGS"] and "-allow-unsupported-compiler" in e["CMAKE_ARGS"]
    assert (tmp_path / "out" / "WHEEL_INFO.json").exists()


def test_everything_failing_raises_without_substituting_a_version(tmp_path, monkeypatch):
    import pytest

    tc = FakeToolchain(tmp_path, pip_wheel_works=False)
    _patch_env(monkeypatch, tc, wheel_ok=False)
    with pytest.raises(RuntimeError, match="NOT substituting"):
        _build(tmp_path)


def test_attached_wheel_dataset_is_preferred_over_download(tmp_path, monkeypatch):
    d = tmp_path / "in" / "wheel-ds"
    d.mkdir(parents=True)
    (d / "llama_cpp_python-0.3.35-py3-none-manylinux_2_35_x86_64.whl").write_bytes(b"x")
    tc = FakeToolchain(tmp_path)
    calls = _patch_env(monkeypatch, tc)
    env = _build(tmp_path)
    assert calls["download"] == 0 and env.info["how"] == "attached wheel dataset"


# ----------------------------------------------------- GGUF temp-disk rules
def test_worker_refuses_models_dir_inside_kaggle_working(tmp_path, monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    rc = kw.main(["--repo", str(tmp_path), "--models-dir", "/kaggle/working/models",
                  "--state-dir", str(tmp_path / "s"), "--export-dir", str(tmp_path / "e")])
    assert rc == 2


def _run_worker_with_fakes(tmp_path, monkeypatch, run_ok: bool, download_fails_after_first: bool = False):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    models = tmp_path / "models"
    seen_during_run = []

    def fake_download(f, models_dir, log):
        if download_fails_after_first and f.filename != plan.build_bundles(("hwcheck",))[0].files[0].filename:
            raise RuntimeError("network")
        models_dir.mkdir(parents=True, exist_ok=True)
        (models_dir / f.filename).write_bytes(b"gguf")
        (models_dir / (f.filename + ".part")).write_bytes(b"half")
        return {"filename": f.filename, "sha256_actual": f.sha256}

    def fake_run(cmd, cwd=None, env=None):
        seen_during_run.append(sorted(p.name for p in models.iterdir()))
        return types.SimpleNamespace(returncode=1)  # runs "fail": nothing becomes done

    monkeypatch.setattr(kw, "download_and_verify", fake_download)
    monkeypatch.setattr(kw.subprocess, "run", fake_run)
    kw.main(["--repo", str(tmp_path / "repo"), "--models-dir", str(models), "--state-dir", str(tmp_path / "state"),
             "--export-dir", str(tmp_path / "export"), "--phases", "hwcheck"])
    return models, seen_during_run


def test_models_downloaded_only_when_runs_pending_and_removed_after(tmp_path, monkeypatch):
    # every hwcheck run already complete -> nothing is downloaded at all
    repo = tmp_path / "repo"
    for p, m, s in plan.all_jobs(("hwcheck",)):
        d = repo / plan.run_rel_dir(p, m, s)
        d.mkdir(parents=True)
        (d / "_status.json").write_text(json.dumps({"completed": True, "record_count_ok": True}))
    downloads = []
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    monkeypatch.setattr(kw, "download_and_verify", lambda *a, **k: downloads.append(a))
    kw.main(["--repo", str(repo), "--models-dir", str(tmp_path / "models"), "--state-dir", str(tmp_path / "st"),
             "--export-dir", str(tmp_path / "ex"), "--phases", "hwcheck"])
    assert downloads == []


def test_gguf_and_part_files_deleted_even_when_runs_fail(tmp_path, monkeypatch):
    models, seen = _run_worker_with_fakes(tmp_path, monkeypatch, run_ok=False)
    assert seen and all(any(n.endswith(".gguf") for n in names) for names in seen)  # model present while running
    assert list(models.iterdir()) == []                                            # and gone afterwards


def test_partial_multi_file_download_is_cleaned_up(tmp_path, monkeypatch):
    # a split model (qwen25: 3 parts) whose 2nd part fails must not leave part 1 behind
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    models = tmp_path / "models"
    n = {"i": 0}

    def fake_download(f, models_dir, log):
        n["i"] += 1
        models_dir.mkdir(parents=True, exist_ok=True)
        if n["i"] == 2:
            (models_dir / (f.filename + ".part")).write_bytes(b"half")
            raise RuntimeError("network")
        (models_dir / f.filename).write_bytes(b"gguf")
        return {}

    monkeypatch.setattr(kw, "download_and_verify", fake_download)
    qwen = [b for b in plan.build_bundles(("F5",)) if b.model_key == "qwen25"]
    monkeypatch.setattr(kw.plan, "build_bundles", lambda phases: qwen)
    kw.main(["--repo", str(tmp_path / "repo"), "--models-dir", str(models), "--state-dir", str(tmp_path / "st"),
             "--export-dir", str(tmp_path / "ex"), "--phases", "F5"])
    assert n["i"] == 2 and list(models.iterdir()) == []


def test_only_zips_logs_and_results_go_to_working_not_models():
    # the notebook points models at temp disk, never at /kaggle/working
    nb = json.loads((REPO_ROOT / "kaggle" / "f5_runner.ipynb").read_text(encoding="utf-8"))
    src = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    assert 'MODELS = Path("/kaggle/temp/models")' in src
    assert 'MODELS = Path("/kaggle/working' not in src
