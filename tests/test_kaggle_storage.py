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


# ---------------------------------------------------------------- wheels
def test_wheel_version_parsing():
    assert ki.wheel_version("llama_cpp_python-0.3.35-cp312-cp312-linux_x86_64.whl") == "0.3.35"
    assert ki.wheel_python_tag("llama_cpp_python-0.3.35-cp312-cp312-linux_x86_64.whl") == "cp312"
    assert ki.wheel_version("numpy-1.0-py3-none-any.whl") is None


def test_find_wheels_exact_version_only_and_python_tag_first(tmp_path):
    d = tmp_path / "input" / "llama-cpp-wheel"
    d.mkdir(parents=True)
    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    for name in (f"llama_cpp_python-0.3.35-cp39-cp39-linux_x86_64.whl",
                 f"llama_cpp_python-0.3.35-{tag}-{tag}-linux_x86_64.whl",
                 f"llama_cpp_python-0.3.36-{tag}-{tag}-linux_x86_64.whl",
                 "llama_cpp_python-0.3.3-cp312-cp312-linux_x86_64.whl"):
        (d / name).write_bytes(b"x")
    found = ki.find_wheels(tmp_path / "input", "0.3.35")
    assert [p.name for p in found] == [f"llama_cpp_python-0.3.35-{tag}-{tag}-linux_x86_64.whl",
                                       "llama_cpp_python-0.3.35-cp39-cp39-linux_x86_64.whl"] or tag == "cp39"
    assert all(ki.wheel_version(p.name) == "0.3.35" for p in found)
    assert ki.find_wheels(tmp_path / "nowhere", "0.3.35") == []


def test_attached_wheel_is_installed_and_nothing_is_built(tmp_path, monkeypatch):
    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    w = tmp_path / "in" / f"llama_cpp_python-0.3.35-{tag}-{tag}-linux_x86_64.whl"
    w.parent.mkdir()
    w.write_bytes(b"x")
    calls = []

    def fake_pip(*args, env=None):
        calls.append(args)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ki, "_pip", fake_pip)
    monkeypatch.setattr(ki, "verify_in_fresh_interpreter", lambda v: (True, f"llama-cpp-python {v} with GPU offload"))
    res = ki.ensure_llama_cpp("0.3.35", input_root=tmp_path / "in", wheel_out_dir=tmp_path / "out")
    assert res["how"] == "installed from attached wheel"
    assert [c[0] for c in calls] == ["install"]          # no `pip wheel` build
    assert not (tmp_path / "out").exists()


def test_unusable_wheel_falls_back_to_building_same_version_only(tmp_path, monkeypatch):
    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    w = tmp_path / "in" / f"llama_cpp_python-0.3.35-{tag}-{tag}-linux_x86_64.whl"
    w.parent.mkdir()
    w.write_bytes(b"x")
    seen = []

    def fake_pip(*args, env=None):
        seen.append(args)
        if args[0] == "wheel":
            outdir = Path(args[args.index("-w") + 1])
            assert args[1] == "llama-cpp-python==0.3.35" and env["CMAKE_ARGS"] == ki.BUILD_CMAKE_ARGS
            (outdir / f"llama_cpp_python-0.3.35-{tag}-{tag}-linux_x86_64.whl").write_bytes(b"built")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    results = iter([(False, "bad abi"), (True, "ok")])  # attached wheel fails verify, built wheel passes
    monkeypatch.setattr(ki, "_pip", fake_pip)
    monkeypatch.setattr(ki, "verify_in_fresh_interpreter", lambda v: next(results))
    res = ki.ensure_llama_cpp("0.3.35", input_root=tmp_path / "in", wheel_out_dir=tmp_path / "out")
    assert res["how"] == "built from source"
    assert Path(res["wheel"]).parent == tmp_path / "out" and Path(res["wheel"]).exists()
    info = json.loads((tmp_path / "out" / "WHEEL_INFO.json").read_text())
    assert info["version"] == "0.3.35" and len(info["sha256"]) == 64


def test_failure_never_substitutes_a_version(tmp_path, monkeypatch):
    import pytest

    monkeypatch.setattr(ki, "_pip", lambda *a, env=None: types.SimpleNamespace(returncode=1, stdout="", stderr="boom"))
    with pytest.raises(RuntimeError, match="NOT substituting"):
        ki.ensure_llama_cpp("0.3.35", input_root=tmp_path / "in", wheel_out_dir=tmp_path / "out")


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
