"""Hermetic tests for the Kaggle tooling (no model, no GPU, fake records):
plan consistency, run-zip verification, the laptop import script's refusal
rules, and the hardware-check comparison."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "kaggle"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import compare_kaggle_hwcheck as cmp  # noqa: E402
import import_kaggle_results as imp  # noqa: E402
import kaggle_plan as plan  # noqa: E402
import kaggle_verify as ver  # noqa: E402

N = 12  # records per fake run (4 tasks x 3 conditions x 1 trial... see make_run)


def make_run(root: Path, protocol="KAGGLE_HWCHECK", model="llama31", suite="synthetic",
             run_id="upgradecanary-real-KAGGLE_HWCHECK-llama31-synthetic_seed1234_20261014T000000Z",
             n_tasks=100, outputs=None) -> Path:
    """Write results_v2/<protocol>/<model>/<suite>/ under root with N fake records."""
    suite_dir = root / "results_v2" / protocol / model / suite
    run_dir = suite_dir / run_id
    run_dir.mkdir(parents=True)
    conds = ["baseline", "schema_drift", "fault_reporting"]
    parsed, raw = [], []
    for i in range(N):
        cond = conds[i % 3]
        trial = i // 6  # 0 or 1
        tid = f"task-{(i % 6) // 3:03d}"
        out = (outputs or {}).get((tid, cond, trial), f'{{"name": "f", "arguments": {{"i": {i % 6}}}}}')
        raw.append({"task_id": tid, "condition": cond, "trial_index": trial, "raw_output": out,
                    "prompt_sha256": f"p-{tid}-{cond}", "retry_raw_output": None})
        parsed.append({"task_id": tid, "condition": cond, "trial_index": trial, "drift": None, "fault": None,
                       "parsed_call": {"name": "f", "arguments": {"i": i % 6}} if out.startswith("{") else None,
                       "metrics": {"score": 1.0 if out.startswith("{") else 0.0}})
    (run_dir / "parsed_results.jsonl").write_text("\n".join(json.dumps(r) for r in parsed) + "\n")
    (run_dir / "raw_outputs.jsonl").write_text("\n".join(json.dumps(r) for r in raw) + "\n")
    (run_dir / "summary.json").write_text("{}")
    srcs = plan.Q4_SOURCES[model] if protocol == "KAGGLE_HWCHECK" else plan.Q8_SOURCES[model]
    manifest = {
        "run_id": run_id, "seed": 1234, "num_tasks": n_tasks, "num_trials": 3, "num_records": N,
        "model_backend": {"llama_cpp_python_version": plan.LLAMA_CPP_PYTHON_VERSION},
        "run_factors": {**plan.EXPECTED_FACTORS[protocol], "n_ctx": 4096},
        "hardware": {"gpu": {"name": "Tesla T4"}},
        "kaggle": {"model_files": [{"filename": f.filename, "sha256_actual": f.sha256} for f in srcs],
                   "task_file": {"path": "data/base_tasks.jsonl", "sha256_lf_normalized": "x"}},
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest))
    (suite_dir / "_status.json").write_text(json.dumps(
        {"completed": True, "record_count_ok": True, "run_id": run_id, "elapsed_seconds": 1.0}))
    return suite_dir


def zip_run(root: Path, suite_dir: Path, dest: Path) -> Path:
    with zipfile.ZipFile(dest, "w") as zf:
        for p in suite_dir.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(root).as_posix())
    return dest


# ------------------------------------------------------------------ plan
def test_plan_counts_and_scope():
    jobs = plan.all_jobs()
    by = {}
    for p, m, s in jobs:
        by.setdefault(p, set()).add((m, s))
    assert len(by["KAGGLE_HWCHECK"]) == 6
    assert len(by["F5"]) == 33
    assert len(by["R_F5"]) == 15
    assert {m for m, _ in by["R_F5"]} == set(plan.HELD_OUT_8B)
    assert {m for m, _ in by["KAGGLE_HWCHECK"]} == {"llama31", "mistral_v02"}
    assert len(jobs) == len(set(jobs))


def test_plan_hashes_are_sha256_hex_and_every_model_has_a_source():
    for srcs in list(plan.Q8_SOURCES.values()) + list(plan.Q4_SOURCES.values()):
        for f in srcs:
            assert len(f.sha256) == 64 and int(f.sha256, 16) >= 0
            assert f.url.startswith("https://huggingface.co/") and f.url.endswith(f.filename)
    for m in plan.ALL_Q8_MODELS:
        assert m in plan.Q8_SOURCES


def test_hwcheck_files_match_laptop_manifest_hashes():
    # sha256 values from docs/model_manifest.md (sections 2 and 5)
    assert plan.Q4_SOURCES["llama31"][0].sha256 == "7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c"
    assert plan.Q4_SOURCES["mistral_v02"][0].sha256 == "aaae8abe274e1521d5aa80bf32cf18b408fc44b9d6869acbdc815440296d275e"


# ---------------------------------------------------------------- verify
def test_verify_accepts_good_zip(tmp_path):
    sd = make_run(tmp_path / "src")
    z = zip_run(tmp_path / "src", sd, tmp_path / "ok.zip")
    r = ver.verify_run_zip(z, expected_records=N)
    assert r.ok, r.problems
    assert r.info["n_parsed"] == N and r.info["gpu"] == "Tesla T4"


def test_verify_rejects_wrong_count_and_wrong_hash(tmp_path):
    sd = make_run(tmp_path / "src")
    z = zip_run(tmp_path / "src", sd, tmp_path / "x.zip")
    assert not ver.verify_run_zip(z, expected_records=N + 1).ok
    # tamper: wrong model hash
    sd2 = make_run(tmp_path / "src2", model="llama31")
    mp = next(sd2.rglob("run_manifest.json"))
    m = json.loads(mp.read_text())
    m["kaggle"]["model_files"][0]["sha256_actual"] = "0" * 64
    mp.write_text(json.dumps(m))
    r = ver.verify_run_zip(zip_run(tmp_path / "src2", sd2, tmp_path / "y.zip"), expected_records=N)
    assert not r.ok and any("hashes" in p for p in r.problems)


def test_verify_rejects_wrong_factors_for_protocol(tmp_path):
    sd = make_run(tmp_path / "src", protocol="F5", model="llama31",
                  run_id="upgradecanary-real-F5-llama31-synthetic_seed1234_x")
    mp = next(sd.rglob("run_manifest.json"))
    m = json.loads(mp.read_text())
    m["run_factors"]["F5_quant_level"] = "unspecified"
    mp.write_text(json.dumps(m))
    r = ver.verify_run_zip(zip_run(tmp_path / "src", sd, tmp_path / "f5.zip"), expected_records=N)
    assert not r.ok and any("F5_quant_level" in p for p in r.problems)


# ---------------------------------------------------------------- import
def _repo_with_task_file(tmp_path: Path) -> Path:
    r = tmp_path / "fakerepo"
    (r / "data").mkdir(parents=True)
    (r / "data" / "base_tasks.jsonl").write_bytes(b'{"a": 1}\r\n')
    return r


def _good_zip(tmp_path: Path, repo: Path, **kw) -> Path:
    sd = make_run(tmp_path / "src", **kw)
    mp = next(sd.rglob("run_manifest.json"))
    m = json.loads(mp.read_text())
    m["kaggle"]["task_file"]["sha256_lf_normalized"] = plan.lf_normalized_sha256(repo / "data" / "base_tasks.jsonl")
    mp.write_text(json.dumps(m))
    return zip_run(tmp_path / "src", sd, tmp_path / "in" / "kaggle__KAGGLE_HWCHECK__llama31__synthetic.zip") \
        if (tmp_path / "in").mkdir(exist_ok=True) is None else None


def test_import_imports_then_refuses_overwrite(tmp_path):
    repo = _repo_with_task_file(tmp_path)
    z = _good_zip(tmp_path, repo)
    root = tmp_path / "results_v2"
    rep = imp.import_zips([z], root, expected_records=N, repo_root=repo)
    assert rep[0]["status"] == "IMPORTED", rep
    target = root / "KAGGLE_HWCHECK" / "llama31" / "synthetic"
    assert (target / "_status.json").exists()
    assert len(list(target.glob("*/parsed_results.jsonl"))) == 1
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    rep2 = imp.import_zips([z], root, expected_records=N, repo_root=repo)
    assert rep2[0]["status"] == "REFUSED"
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_import_dry_run_writes_nothing_and_rejects_bad_task_hash(tmp_path):
    repo = _repo_with_task_file(tmp_path)
    z = _good_zip(tmp_path, repo)
    root = tmp_path / "results_v2"
    assert imp.import_zips([z], root, N, dry_run=True, repo_root=repo)[0]["status"] == "WOULD-IMPORT"
    assert not root.exists()
    (repo / "data" / "base_tasks.jsonl").write_bytes(b'{"a": 2}\n')  # tasks changed locally
    assert imp.import_zips([z], root, N, repo_root=repo)[0]["status"] == "REJECTED"
    assert not root.exists()


def test_import_rejects_short_run(tmp_path):
    repo = _repo_with_task_file(tmp_path)
    z = _good_zip(tmp_path, repo)
    rep = imp.import_zips([z], tmp_path / "results_v2", expected_records=N + 5, repo_root=repo)
    assert rep[0]["status"] == "REJECTED"


# --------------------------------------------------------------- compare
def test_compare_counts_matches_and_mismatches(tmp_path):
    k = make_run(tmp_path / "k")
    l = make_run(tmp_path / "l", protocol="KAGGLE_HWCHECK",
                 run_id="upgradecanary-real-D-llama31-synthetic_seed1234_old",
                 outputs={("task-000", "baseline", 0): "oops"})
    r = cmp.compare_run(cmp.find_run_dir(k), cmp.find_run_dir(l))
    greedy = r["n_matched_keys"]
    assert greedy == 6 and r["only_kaggle"] == 0 and r["only_laptop"] == 0
    assert r["raw_equal"] == greedy - 1
    assert r["prompt_equal"] == greedy
    assert r["raw_match_rate"] == pytest.approx((greedy - 1) / greedy)
    assert len(r["mismatches"]) == 1 and r["mismatches"][0]["laptop_raw"] == "oops"


def test_compare_identical_is_100_percent(tmp_path):
    k = make_run(tmp_path / "k")
    l = make_run(tmp_path / "l", run_id="other-run-id")
    r = cmp.compare_run(cmp.find_run_dir(k), cmp.find_run_dir(l))
    assert r["raw_match_rate"] == 1.0 and r["score_match_rate"] == 1.0
