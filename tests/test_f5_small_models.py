"""F5 / R_F5 protocol entries and the small-model orchestrator, on fake data
only: no model is loaded, no subprocess is really launched, no GPU."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

# real_run_one calls _dll_preload.preload() at import (Windows DLL loading);
# stub it so importing never touches CUDA/llama.
_stub = types.ModuleType("_dll_preload")
_stub.preload = lambda: None
sys.modules.setdefault("_dll_preload", _stub)

from scripts import real_run_f5_small_orchestrator as orch  # noqa: E402
from scripts import real_run_one as r1  # noqa: E402

SMALL = ["gemma2_2b", "gemma3_4b", "phi3_mini", "phi35_mini", "phi4_mini"]


def _flat(d, pre=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flat(v, pre + k + "."))
        else:
            out[pre + k] = json.dumps(v)
    return out


@pytest.mark.parametrize("model", SMALL)
@pytest.mark.parametrize("proto,base", [("F5", "D"), ("R_F5", "R")])
def test_q8_config_differs_from_base_only_in_file_and_label(model, proto, base):
    from scripts.real_run_models import MODEL_ORDER, SUITES

    q4_path = dict(MODEL_ORDER)[model]
    a = r1.build_config(model, r1.Q8_0_MODEL_PATHS[model], "synthetic", SUITES["synthetic"], protocol=proto)
    b = r1.build_config(model, q4_path, "synthetic", SUITES["synthetic"], protocol=base)
    fa, fb = _flat(a), _flat(b)
    diff = {k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k)}
    # experiment/output_dir carry the protocol name; model.path is the file; quant_level is the label
    assert diff == {"experiment", "output_dir", "model.path", "model.quant_level"}, diff
    assert a["model"]["quant_level"] == "Q8_0"
    assert a["output_dir"] == f"results_v2/{proto}/{model}/synthetic"
    assert a["model"]["path"].endswith("Q8_0.gguf")


def test_q8_paths_cover_exactly_the_small_models_and_sit_beside_q4():
    from scripts.real_run_models import MODEL_ORDER

    assert sorted(r1.Q8_0_MODEL_PATHS) == sorted(SMALL)
    q4 = dict(MODEL_ORDER)
    for m, p in r1.Q8_0_MODEL_PATHS.items():
        assert Path(p).parent == Path(q4[m]).parent  # same models/<family>/ dir


def test_8b_model_has_no_local_q8_path():
    assert "llama31" not in r1.Q8_0_MODEL_PATHS  # runs on Kaggle; KeyError rather than a silent Q4 fallback


def test_orchestrator_plan_is_30_runs_f5_then_r_f5():
    runs = orch.all_runs()
    assert len(runs) == 30 and len(set(runs)) == 30
    assert [r[0] for r in runs[:15]] == ["F5"] * 15 and [r[0] for r in runs[15:]] == ["R_F5"] * 15
    assert {m for _, m, _ in runs} == set(SMALL)
    assert orch.EXPECTED_SIZES.keys() == set(SMALL)


def test_preflight_reports_missing_and_wrong_size(tmp_path, monkeypatch):
    monkeypatch.setattr(orch, "REPO_ROOT", tmp_path)
    probs = orch.preflight()
    assert len(probs) == 5 and all("missing" in p for p in probs)
    for m in SMALL:
        f = tmp_path / r1.Q8_0_MODEL_PATHS[m]
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
    assert len(orch.preflight()) == 5 and all("expected" in p for p in orch.preflight())


def test_main_refuses_without_files_and_launches_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(orch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(orch, "LOG_PATH", tmp_path / "log.txt")
    called = []
    monkeypatch.setattr(orch.subprocess, "run", lambda *a, **k: called.append(a))
    assert orch.main() == 2
    assert called == []


def test_main_runs_pending_skips_done_and_is_resumable(tmp_path, monkeypatch):
    monkeypatch.setattr(orch, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(orch, "LOG_PATH", tmp_path / "log.txt")
    monkeypatch.setattr(orch, "REPORT_PATH", tmp_path / "report.md")
    monkeypatch.setattr(orch, "BACKUP_EVERY", 10 ** 6)
    monkeypatch.setattr(orch, "preflight", lambda: [])
    # one run already done
    d = tmp_path / "results_v2" / "F5" / "gemma2_2b" / "synthetic"
    d.mkdir(parents=True)
    (d / "_status.json").write_text(json.dumps({"completed": True}))
    launched = []

    def fake_run(cmd, cwd=None):
        model, suite, proto = cmd[-3:]
        launched.append((proto, model, suite))
        sd = tmp_path / "results_v2" / proto / model / suite
        sd.mkdir(parents=True, exist_ok=True)
        (sd / "_status.json").write_text(json.dumps({"completed": False, "error": "boom"}) if
                                         (proto, model, suite) == ("R_F5", "phi4_mini", "bfcl_simple") else
                                         json.dumps({"completed": True, "num_records": 900, "elapsed_seconds": 1.0,
                                                     "run_dir": str(sd)}))
        return types.SimpleNamespace(returncode=1 if (proto, model, suite) == ("R_F5", "phi4_mini", "bfcl_simple") else 0)

    monkeypatch.setattr(orch.subprocess, "run", fake_run)
    rc = orch.main()
    assert rc == 1  # one failure left pending, no report written
    assert len(launched) == 29 and ("F5", "gemma2_2b", "synthetic") not in launched
    assert not (tmp_path / "report.md").exists()
    # second launch: only the failed one is retried
    launched.clear()
    monkeypatch.setattr(orch, "write_final_report", lambda runs: None)

    def ok_run(cmd, cwd=None):
        model, suite, proto = cmd[-3:]
        launched.append((proto, model, suite))
        sd = tmp_path / "results_v2" / proto / model / suite
        (sd / "_status.json").write_text(json.dumps({"completed": True, "num_records": 900}))
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(orch.subprocess, "run", ok_run)
    assert orch.main() == 0
    assert launched == [("R_F5", "phi4_mini", "bfcl_simple")]
