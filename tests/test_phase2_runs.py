"""Phase 2 run tooling: manifests, config builder, cross-check with the analysis config, laptop orchestrator,
Kaggle worker/import, notebook, split test. No model, no GPU, no real results: fixtures and stubs only
(the committed manifests in configs/phase2 are read as data)."""

import copy
import json
import os
import sys
import types
import zipfile
from datetime import date
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "kaggle"))
sys.path.insert(0, str(REPO_ROOT / "kaggle" / "phase2"))

from scripts.phase2 import plan  # noqa: E402
from scripts.phase2.build import ManifestError, apply_trials, build_run_config, diff_against_phase1  # noqa: E402
from scripts.phase2.check_configs import check_against_analysis, check_all  # noqa: E402
from vdanalysis.phase2.config import load_phase2_config  # noqa: E402

WORKSTREAMS = plan.WORKSTREAMS


@pytest.fixture(scope="module")
def manifests():
    return {n: plan.load_manifest(n) for n in WORKSTREAMS}


def entry(manifests, id_):
    for m in manifests.values():
        for e in m["runs"]:
            if e["id"] == id_:
                return e
    raise KeyError(id_)


# =============================================================================== manifests (committed)
def test_run_counts_and_hours_match_the_plan(manifests):
    n = {k: m["n_runs"] for k, m in manifests.items()}
    assert n == {"W1_laptop": 252, "W1_kaggle": 81, "W2_R": 48, "W2_D": 48, "W2b": 24, "W3": 64}
    h = {k: m["estimated_hours"] for k, m in manifests.items()}
    assert h["W1_laptop"] == pytest.approx(195.64, abs=0.05)       # PLAN_PHASE2.md section 6 (322.4 total with W2b)
    assert h["W1_kaggle"] == pytest.approx(136.77, abs=0.05)
    assert h["W2_R"] == pytest.approx(70.18, abs=0.05) and h["W2_D"] == pytest.approx(38.37, abs=0.05)
    assert h["W2b"] == pytest.approx(18.16, abs=0.05) and h["W3"] == pytest.approx(34.53, abs=0.05)   # bfcl only
    assert sum(h[k] for k in ("W1_laptop", "W2_R", "W2_D", "W2b")) == pytest.approx(322.4, abs=0.1)
    assert manifests["W1_laptop"]["runs_by_folder"] == {"D": 48, "R": 48, "F1": 48, "F2": 3, "F3": 24, "F4_json": 48,
                                                          "F5": 15, "F6": 18}
    assert manifests["W1_kaggle"]["runs_by_folder"] == {"F5": 33, "D_KAGGLE": 33, "R_KAGGLE": 15}


def test_every_run_has_the_required_fields(manifests):
    need = {"protocol": "folder", "model": "model", "suite": "suite", "hardware": "hardware", "run_seed": "run_seed",
            "trial seeds": "trial_seeds", "temperatures": "temperatures", "output folder": "output_dir",
            "estimated hours": "estimated_hours"}
    ids = set()
    for m in manifests.values():
        for e in m["runs"]:
            assert all(k in e for k in need.values()), e["id"]
            assert e["output_dir"] == f"results_v3/{e['folder']}/{e['model']}/{e['suite']}"
            assert e["run_seed"] == 1234 and e["estimated_hours"] > 0
            assert e["id"] not in ids
            ids.add(e["id"])
            assert len(e["trial_seeds"]) == len(e["temperatures"]) == e["n_trials"]


def test_laptop_runs_only_add_trials_4_to_10_and_kaggle_runs_all_ten(manifests):
    for ws in ("W1_laptop", "W2b"):
        for e in manifests[ws]["runs"]:
            assert e["hardware"] == "laptop" and e["trial_first_index"] == 3 and e["n_trials"] == 7
            assert e["trial_seeds"] == list(range(1237, 1244)) and 0.0 not in e["temperatures"]
    for e in manifests["W1_kaggle"]["runs"]:
        assert e["hardware"] == "kaggle" and e["trial_first_index"] == 0 and e["n_trials"] == 10
        assert e["trial_seeds"] == list(range(1234, 1244)) and e["temperatures"] == [0.0] + [0.7] * 9
    for ws in ("W2_R", "W2_D"):
        for e in manifests[ws]["runs"]:
            assert e["hardware"] == "laptop" and e["trial_seeds"] == list(range(5678, 5688)) and e["run_seed"] == 1234
            assert e["temperatures"] == [0.0] + [0.7] * 9


def test_f6_sampled_trials_use_each_models_own_preset_temperature(manifests):
    assert entry(manifests, "F6/qwen3/synthetic")["temperatures"] == [0.6] * 7
    assert entry(manifests, "F6/llama31/synthetic")["temperatures"] == [0.6] * 7
    assert entry(manifests, "F6/qwen25/synthetic")["temperatures"] == [0.7] * 7
    assert {e["model"] for e in manifests["W1_laptop"]["runs"] if e["folder"] == "F6"} == set(plan.F6_CHANGED)


def test_scope_follows_phase1(manifests):
    by = lambda ws, f: {e["model"] for e in manifests[ws]["runs"] if e["folder"] == f}
    assert by("W1_laptop", "F2") == {"qwen3"} and len(by("W1_laptop", "F3")) == 8
    assert by("W1_laptop", "F5") == {"gemma2_2b", "gemma3_4b", "phi3_mini", "phi35_mini", "phi4_mini"}
    assert by("W1_kaggle", "F5") == by("W1_kaggle", "D_KAGGLE") == set(plan.KAGGLE_D_MODELS)
    assert by("W1_kaggle", "R_KAGGLE") == set(plan.KAGGLE_R_MODELS)
    assert by("W2b", "R_PC_Q2K") == by("W2b", "R_PC_NODESC") == set(plan.CONTROL_MODELS)
    assert len(by("W2_R", "R_AA2")) == len(by("W2_D", "D_AA2")) == 16


def test_w3_runs_the_added_tasks_only_and_is_conditional(manifests):
    m = manifests["W3"]
    assert "20 Nov" in m["conditional"] or "2026-11-20" in m["conditional"]
    for e in m["runs"]:
        assert e["suite"] in ("bfcl_simple", "bfcl_multiple")           # synthetic is not extended
        assert e["n_tasks"] == plan.ADDED_TASKS[e["suite"]] and e["data_status"] == "ok"
        assert e["expected_records"] == e["n_tasks"] * 3 * 10 and e["folder"] in ("W3_D", "W3_R")


def test_kaggle_batches_respect_the_lane_cap_and_cover_every_run_once(manifests):
    m = manifests["W1_kaggle"]
    seen = [r for b in m["batches"] for lane in b["lanes"] for r in lane["runs"]]
    assert sorted(seen) == sorted(e["id"] for e in m["runs"])
    by_id = {e["id"]: e for e in m["runs"]}
    for b in m["batches"]:
        assert 1 <= len(b["lanes"]) <= 2                          # two jobs in parallel, one per T4
        for lane in b["lanes"]:
            assert not lane["oversize"]
            assert lane["estimated_hours"] <= plan.LANE_CAP_HOURS + plan.OVERSIZE_TOLERANCE
            assert lane["estimated_hours"] >= sum(by_id[r]["estimated_hours"] for r in lane["runs"])
            for bundle in lane["bundles"]:                        # one model file per bundle
                assert {(by_id[r]["model"], by_id[r]["quant"]) for r in bundle["runs"]} == {(bundle["model"], bundle["quant"])}
    assert all(b["wall_hours"] <= 9.6 for b in m["batches"])


def test_every_kaggle_model_file_has_a_verified_source(manifests):
    from p2_sources import files_for
    for e in manifests["W1_kaggle"]["runs"]:
        files = files_for(e["model"], e["quant"])
        assert files and all(len(f.sha256) == 64 for f in files) and sum(f.size for f in files) > 3e9


# =============================================================================== config builder
def test_every_config_builds_and_matches_phase1_outside_the_trial_keys(manifests):
    for m in manifests.values():
        for e in m["runs"]:
            cfg = build_run_config(e, gguf="/kaggle/temp/models/m.gguf" if e["hardware"] == "kaggle" else None)
            assert cfg["output_dir"] == e["output_dir"] and cfg["seed"] == 1234 and cfg["model"]["seed"] == 1234
            assert cfg["trials"] == e["n_trials"] == len(cfg["trial_seeds"]) == len(cfg["trial_temperatures"])
            assert cfg["model"]["n_ctx"] == 4096 and cfg["model"]["n_gpu_layers"] == -1
            for k in ("trial_top_p", "trial_top_k", "trial_min_p", "trial_repeat_penalty"):
                if k in cfg:
                    assert len(cfg[k]) == e["n_trials"]


def test_f6_per_trial_lists_are_cut_to_the_trials_that_run(manifests):
    cfg = build_run_config(entry(manifests, "F6/qwen2/synthetic"))
    assert cfg["trial_temperatures"] == [0.7] * 7
    assert cfg["trial_top_p"] == [0.8] * 7 and cfg["trial_top_k"] == [20] * 7 and cfg["trial_repeat_penalty"] == [1.05] * 7
    assert cfg["model"]["sampling_preset"] == "recommended"
    cfg = build_run_config(entry(manifests, "F6/qwen3/bfcl_simple"))
    assert cfg["trial_min_p"] == [0.0] * 7 and cfg["trial_temperatures"] == [0.6] * 7


def test_controls_and_arms_use_the_right_phase1_protocol(manifests):
    q = build_run_config(entry(manifests, "R_PC_Q2K/llama31/synthetic"))
    assert q["model"]["quant_level"] == "Q2_K" and "q2_k" in q["model"]["path"].lower()
    assert q["constrained_decoding"] == "generic_json" and q["model"]["max_tokens"] == 1024
    n = build_run_config(entry(manifests, "R_PC_NODESC/llama31/synthetic"))
    assert n["prompt_format"] == "no_description"
    a = build_run_config(entry(manifests, "R_AA2/llama31/synthetic"))
    assert a["seed"] == 1234 and a["trial_seeds"][0] == 5678 and a["constrained_decoding"] == "generic_json"
    f5 = build_run_config(entry(manifests, "F5/llama31/synthetic"), gguf="/x.gguf")
    assert f5["model"]["quant_level"] == "Q8_0" and f5["model"]["path"] == "/x.gguf"
    d = build_run_config(entry(manifests, "D_KAGGLE/llama31/synthetic"), gguf="/x.gguf")
    assert "quant_level" not in d["model"] and d["constrained_decoding"] == "off"


def test_builder_refuses_inconsistent_manifest_entries(manifests):
    e = copy.deepcopy(entry(manifests, "D/gemma2_2b/synthetic"))
    for field, value, msg in (("temperatures", [0.5] * 7, "disagree"), ("run_seed", 99, "run seed"),
                              ("output_dir", "results_v2/D/x", "results_v3"), ("n_trials", 5, "n_trials")):
        bad = dict(e, **{field: value})
        with pytest.raises(ManifestError, match=msg):
            build_run_config(bad)
    with pytest.raises(ManifestError, match="no GGUF"):
        build_run_config(dict(entry(manifests, "F5/llama31/synthetic")))
    with pytest.raises(ManifestError):
        apply_trials({}, [1, 2], [0.0])


def test_diff_against_phase1_flags_an_unexpected_change(manifests, tmp_path):
    e = entry(manifests, "D/gemma2_2b/synthetic")
    cfg = build_run_config(e)
    gen = tmp_path / "_generated_configs"
    gen.mkdir()
    old = copy.deepcopy(cfg)
    old.update(trials=3, trial_seeds=[1234, 1235, 1236], trial_temperatures=[0.0, 0.7, 0.7], experiment="x", output_dir="y")
    (gen / "gemma2_2b__synthetic.yaml").write_text(yaml.safe_dump(old), encoding="utf-8")
    assert diff_against_phase1(e, cfg, tmp_path) == []
    old["model"]["max_tokens"] = 1024
    (gen / "gemma2_2b__synthetic.yaml").write_text(yaml.safe_dump(old), encoding="utf-8")
    assert diff_against_phase1(e, cfg, tmp_path) == ["model: max_tokens"]
    assert diff_against_phase1(entry(manifests, "R/gemma2_2b/synthetic"), build_run_config(entry(manifests, "R/gemma2_2b/synthetic")),
                               tmp_path) is None


# =============================================================================== against the analysis config
def test_manifests_match_the_analysis_config(manifests):
    cfg = load_phase2_config("configs/analysis_phase2.yaml")
    assert check_against_analysis(manifests, cfg) == []
    assert check_all()["problems"] == []


@pytest.mark.parametrize("mutate,expect", [
    (lambda m: m["W1_laptop"].update(runs=[e for e in m["W1_laptop"]["runs"] if e["folder"] != "F2"]), "no manifest has runs"),
    (lambda m: m["W1_laptop"]["runs"].pop(), "expected all of"),
    (lambda m: m["W2b"]["runs"][0].update(trial_first_index=0), "analysis trial_offset"),
    (lambda m: m["W2_R"]["runs"][0].update(trial_seeds=list(range(1234, 1244))), "analysis seed_base"),
    (lambda m: m["W1_kaggle"]["runs"][0].update(n_trials=7), "analysis n_trials"),
    (lambda m: m["W1_laptop"]["runs"][0].update(folder="D_typo", id="D_typo/x/y", output_dir="results_v3/D_typo/x/y"),
     "never reads"),
    (lambda m: m["W1_laptop"]["runs"][0].update(output_dir="results_v3/D/elsewhere"), "output_dir"),
])
def test_cross_check_catches_mismatches(manifests, mutate, expect):
    cfg = load_phase2_config("configs/analysis_phase2.yaml")
    bad = copy.deepcopy(manifests)
    mutate(bad)
    problems = check_against_analysis(bad, cfg)
    assert any(expect in p for p in problems), problems


def test_analysis_needs_exactly_the_v3_folders_the_manifests_list(manifests):
    from scripts.phase2.check_configs import analysis_needs
    cfg = load_phase2_config("configs/analysis_phase2.yaml")
    need = analysis_needs(cfg)
    have = {(e["folder"], e["model"]) for m in manifests.values() for e in m["runs"]}
    assert set(need) == have
    assert ("F6", "mistral_v01") not in need and ("F6", "qwen3") in need         # F6 trimming
    assert need[("D_AA2", "qwen3")]["seed_base"] == 5678 and need[("D", "qwen3")]["offset"] == 3
    assert need[("F5", "qwen3")]["offset"] == 0 and need[("F5", "phi3_mini")]["offset"] == 3     # Kaggle fresh / laptop add-on


# =============================================================================== plan builder on fixture timings
@pytest.fixture()
def fake_phase1(tmp_path):
    root = tmp_path / "results_v2"
    models = plan.MODEL_KEYS

    def put(folder, ms, secs=3600.0):
        for m in ms:
            for s in plan.SUITE_ORDER:
                d = root / folder / m / s
                d.mkdir(parents=True)
                (d / "_status.json").write_text(json.dumps({"completed": True, "elapsed_seconds": secs}), encoding="utf-8")
    for f in ("D", "R", "F1", "F4_json", "F6"):
        put(f, models)
    put("F2", ["qwen3"])
    put("F3", [m for m in models if m in ("llama31", "qwen25", "mistral_v03", "granite31", "granite32", "qwen3", "phi4_mini", "granite30")])
    put("F3_rerun", ["granite30"], 7200.0)
    put("F5", models)
    put("R_F5", plan.KAGGLE_R_MODELS + ["gemma2_2b"])
    put("R_PC_Q2K", plan.CONTROL_MODELS)
    put("R_PC_NODESC", plan.CONTROL_MODELS)
    kag = [f"F5/{m}/{s}" for m in plan.KAGGLE_D_MODELS for s in plan.SUITE_ORDER]
    kag += [f"R_F5/{m}/{s}" for m in plan.KAGGLE_R_MODELS for s in plan.SUITE_ORDER]
    (root / "_kaggle_import_log.jsonl").write_text("".join(json.dumps({"run": r}) + "\n" for r in kag), encoding="utf-8")
    return plan.Phase1Timing(root)


def test_builder_scales_phase1_times(fake_phase1):
    ms = plan.build_all(fake_phase1)
    assert ms["W1_laptop"]["hours_by_folder"]["D"] == pytest.approx(48 * 7 / 3)
    assert ms["W1_laptop"]["hours_by_folder"]["F3"] == pytest.approx((21 + 3 * 2) * 7 / 3)    # granite30 from F3_rerun (2 h)
    assert ms["W2_R"]["estimated_hours"] == pytest.approx(48 * 10 / 3)
    assert ms["W2b"]["estimated_hours"] == pytest.approx(24 * 7 / 3)
    assert ms["W1_kaggle"]["estimated_hours"] == pytest.approx((33 + 33 + 15) * 10 / 3)
    e = next(e for e in ms["W3"]["runs"] if e["suite"] == "bfcl_simple")
    assert e["estimated_hours"] == pytest.approx(0.91 * 10 / 3, abs=1e-3)                       # 91 added tasks
    assert {e["suite"] for e in ms["W3"]["runs"]} == {"bfcl_simple", "bfcl_multiple"}
    assert [e["order"] for e in ms["W1_laptop"]["runs"]] == list(range(ms["W1_laptop"]["n_runs"]))
    folders = [e["folder"] for e in ms["W1_laptop"]["runs"]]
    assert folders.index("D") < folders.index("R") < folders.index("F1") and folders[0] == "D"
    assert ms["W1_laptop"]["runs"][0]["model"] == "gemma2_2b"                                    # fast models first


def test_incomplete_phase1_run_is_refused(fake_phase1):
    p = fake_phase1.root / "D" / "qwen3" / "synthetic" / "_status.json"
    p.write_text(json.dumps({"completed": False, "elapsed_seconds": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="not complete"):
        plan.build_all(fake_phase1)


def test_kaggle_lane_packing_with_small_cap():
    entries = [{"id": f"F5/m{i}/s", "model": f"m{i}", "quant": "Q8_0", "folder": "F5", "suite": "synthetic",
                "estimated_hours": 3.0} for i in range(5)]
    entries += [{"id": f"F5/big/{s}", "model": "big", "quant": "Q8_0", "folder": "F5", "suite": s, "estimated_hours": 4.0}
                for s in plan.SUITE_ORDER]
    batches = plan.kaggle_batches(entries, cap=9.0)
    ids = sorted(r for b in batches for l in b["lanes"] for r in l["runs"])
    assert ids == sorted(e["id"] for e in entries)
    assert all(l["estimated_hours"] <= 9.0 + 1e-9 for b in batches for l in b["lanes"])
    assert all(len(b["lanes"]) <= 2 for b in batches)
    big = [bd for b in batches for l in b["lanes"] for bd in l["bundles"] if bd["model"] == "big"]
    assert len(big) == 2                                      # 3 x 4 h does not fit one 9 h lane: split in two chunks


# =============================================================================== laptop run_one / orchestrator
@pytest.fixture()
def stub_world(tmp_path, monkeypatch):
    """A repo root with a tiny manifest and a stub runner; nothing real is touched."""
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    (root / "data" / "base_tasks.jsonl").write_text('{"task_id": "t"}\n', encoding="utf-8")
    mdir = root / "configs" / "phase2"
    mdir.mkdir(parents=True)

    def mk(folder, ws, order, hours):
        e = plan.make_entry(ws, folder, "gemma2_2b", "synthetic", "laptop", "addon", hours, hours, "Q4_K_M",
                            "models/gemma/gemma-2-2b-it-Q4_K_M.gguf", n_tasks=1)
        e["order"] = order
        e["data"] = "data/base_tasks.jsonl"
        return e
    spec = {"W1_laptop": [mk("D", "W1_laptop", 0, 1), mk("R", "W1_laptop", 1, 2)], "W2_R": [mk("R_AA2", "W2_R", 0, 3)],
            "W2b": [mk("R_PC_Q2K", "W2b", 0, 1)], "W2_D": [mk("D_AA2", "W2_D", 0, 1)], "W1_kaggle": [], "W3": []}
    for name, runs in spec.items():
        (mdir / f"{name}.json").write_text(json.dumps({"manifest": name, "runs": runs}), encoding="utf-8")
    monkeypatch.setitem(sys.modules, "_dll_preload", types.SimpleNamespace(preload=lambda: None))
    monkeypatch.chdir(root)
    return root, mdir, spec


def fake_runner_factory(n_records_for=lambda cfg: None):
    def run(cfg_path):
        cfg = yaml.safe_load(Path(cfg_path).read_text(encoding="utf-8"))
        d = Path(cfg["output_dir"]) / "fake-run-id"
        d.mkdir(parents=True, exist_ok=True)
        n = n_records_for(cfg)
        n = n if n is not None else 1 * 3 * cfg["trials"]
        (d / "run_manifest.json").write_text(json.dumps({"run_id": "fake-run-id"}), encoding="utf-8")
        return {"run_id": "fake-run-id", "num_records": n}
    return run


def test_run_one_completes_skips_and_quarantines(stub_world, monkeypatch):
    from scripts.phase2 import run_one
    root, mdir, spec = stub_world
    e = spec["W1_laptop"][0]
    monkeypatch.setattr("upgradecanary.runner.run", fake_runner_factory())
    assert run_one.run_entry("W1_laptop", e, root) == 0
    st = json.loads((root / e["output_dir"] / "_status.json").read_text())
    assert st["completed"] and st["record_count_ok"] and st["num_records"] == st["expected_records"] == 21
    man = json.loads((root / e["output_dir"] / "fake-run-id" / "run_manifest.json").read_text())
    assert man["phase2"]["id"] == e["id"] and man["phase2"]["trial_first_index"] == 3
    cfg = yaml.safe_load((root / "results_v3" / "_generated_configs" / "D__gemma2_2b__synthetic.yaml").read_text())
    assert cfg["trial_seeds"] == list(range(1237, 1244)) and cfg["output_dir"] == e["output_dir"]
    assert run_one.run_entry("W1_laptop", e, root) == 0                               # already complete: skipped
    # an interrupted attempt is moved aside, not left next to the redo
    (root / e["output_dir"] / "_status.json").write_text(json.dumps({"completed": False}), encoding="utf-8")
    (root / e["output_dir"] / "leftover").mkdir()
    assert run_one.run_entry("W1_laptop", e, root) == 0
    assert len(list((root / "results_v3" / "_failed_attempts").iterdir())) == 1
    assert [p.name for p in (root / e["output_dir"]).iterdir() if p.is_dir()] == ["fake-run-id"]


def test_run_one_wrong_record_count_is_not_complete(stub_world, monkeypatch):
    from scripts.phase2 import run_one
    root, mdir, spec = stub_world
    e = spec["W1_laptop"][1]
    monkeypatch.setattr("upgradecanary.runner.run", fake_runner_factory(lambda cfg: 5))
    assert run_one.run_entry("W1_laptop", e, root) == 1
    assert not run_one.is_done(e, root)


def test_run_one_refuses_pending_task_files(stub_world):
    from scripts.phase2 import run_one
    root, mdir, spec = stub_world
    e = dict(spec["W1_laptop"][0], data_status="pending")
    assert run_one.run_entry("W1_laptop", e, root) == 1


def test_orchestrator_order_is_the_priority_order(manifests):
    from scripts.phase2.run_laptop import build_queue
    q = build_queue(list(plan.LAPTOP_PRIORITY[:4]))
    ws = [n for n, _ in q]
    assert ws == sorted(ws, key=plan.LAPTOP_PRIORITY.index)                    # W1 > W2 (R) > W2b > W2 (D)
    firsts = {}
    for i, (n, e) in enumerate(q):
        firsts.setdefault((n, e["folder"]), i)
    assert firsts[("W1_laptop", "D")] < firsts[("W1_laptop", "R")] < firsts[("W1_laptop", "F1")] < firsts[("W2_R", "R_AA2")]
    assert firsts[("W2_R", "R_AA2")] < firsts[("W2b", "R_PC_Q2K")] < firsts[("W2_D", "D_AA2")]
    assert len(q) == 252 + 48 + 24 + 48 and all(e["hardware"] == "laptop" for _, e in q)


def test_orchestrator_dry_run_resumes_and_skips_completed(stub_world, capsys, monkeypatch):
    from scripts.phase2 import run_laptop, run_one
    root, mdir, spec = stub_world
    monkeypatch.setattr("upgradecanary.runner.run", fake_runner_factory())
    run_one.run_entry("W1_laptop", spec["W1_laptop"][0], root)                   # D already done
    capsys.readouterr()
    rc = run_laptop.main(["--dry-run", "--root", str(root), "--manifests", str(mdir)])
    out = capsys.readouterr().out
    assert rc == 0 and "D/gemma2_2b/synthetic" not in out
    order = [l.split()[2] for l in out.splitlines() if "gemma2_2b" in l]
    assert order == ["R/gemma2_2b/synthetic", "R_AA2/gemma2_2b/synthetic", "R_PC_Q2K/gemma2_2b/synthetic",
                     "D_AA2/gemma2_2b/synthetic"]
    # nothing was run by the dry run
    assert not (root / "results_v3" / "R").exists()


def test_orchestrator_runs_queue_backs_up_and_stops_at_the_gpu_deadline(stub_world, monkeypatch, tmp_path):
    from scripts.phase2 import run_laptop
    root, mdir, spec = stub_world
    launched = []

    def fake_subprocess_run(cmd, cwd=None, **kw):
        manifest, run_id = cmd[-2], cmd[-1]
        e = next(x for x in spec[manifest] if x["id"] == run_id)
        out = root / e["output_dir"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "_status.json").write_text(json.dumps({"completed": True, "record_count_ok": True,
                                                       "expected_records": e["expected_records"]}), encoding="utf-8")
        launched.append(run_id)
        return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(run_laptop.subprocess, "run", fake_subprocess_run)
    bdir = tmp_path / "backups"
    assert run_laptop.main(["--root", str(root), "--manifests", str(mdir), "--backup-dir", str(bdir), "--backup-every", "2",
                            "--today", "2026-11-01"]) == 0
    assert launched == ["D/gemma2_2b/synthetic", "R/gemma2_2b/synthetic", "R_AA2/gemma2_2b/synthetic",
                        "R_PC_Q2K/gemma2_2b/synthetic", "D_AA2/gemma2_2b/synthetic"]
    zips = sorted(p.name for p in bdir.glob("*.zip"))
    assert len(zips) >= 2 and all(z.startswith("results_v3_backup_") for z in zips)
    assert not list((root / "results_v3").rglob("*.zip"))                          # zips are staged outside results folders
    # resumable: everything is done now, a second launch runs nothing
    launched.clear()
    run_laptop.main(["--root", str(root), "--manifests", str(mdir), "--backup-dir", str(bdir), "--today", "2026-11-01"])
    assert launched == []
    # after the GPU deadline nothing new starts
    for e in spec["W2b"]:
        import shutil
        shutil.rmtree(root / e["output_dir"])
    run_laptop.main(["--root", str(root), "--manifests", str(mdir), "--backup-dir", str(bdir), "--today", "2026-12-11"])
    assert launched == []


def test_w3_gate(stub_world, tmp_path):
    from scripts.phase2 import run_laptop
    root, mdir, spec = stub_world
    ok, why = run_laptop.w3_gate(date(2026, 11, 21), mdir, root)
    assert not ok and "skipped" in why                                              # calendar only
    ok, why = run_laptop.w3_gate(date(2026, 11, 1), mdir, root)
    assert not ok and "not complete" in why
    for ws in ("W1_laptop", "W2_R", "W2_D", "W2b"):
        for e in spec[ws]:
            d = root / e["output_dir"]
            d.mkdir(parents=True, exist_ok=True)
            (d / "_status.json").write_text(json.dumps({"completed": True, "record_count_ok": True,
                                                         "expected_records": e["expected_records"]}), encoding="utf-8")
    ok, why = run_laptop.w3_gate(date(2026, 11, 1), mdir, root)
    assert not ok and "split-equivalence" in why
    chk = root / run_laptop.SPLIT_CHECK_R
    chk.parent.mkdir(parents=True, exist_ok=True)
    chk.write_text(json.dumps({"all_identical": False}), encoding="utf-8")
    assert not run_laptop.w3_gate(date(2026, 11, 1), mdir, root)[0]
    chk.write_text(json.dumps({"all_identical": True}), encoding="utf-8")
    assert run_laptop.w3_gate(date(2026, 11, 1), mdir, root) == (True, "ok")
    w3 = {"manifest": "W3", "runs": [dict(spec["W1_laptop"][0], data="data/phase2/missing.jsonl")]}
    (mdir / "W3.json").write_text(json.dumps(w3), encoding="utf-8")
    ok, why = run_laptop.w3_gate(date(2026, 11, 1), mdir, root)
    assert not ok and "missing" in why


# =============================================================================== Kaggle worker / import / notebook
@pytest.fixture()
def kaggle_repo(tmp_path):
    repo = tmp_path / "krepo"
    (repo / "configs" / "phase2").mkdir(parents=True)
    src = json.loads((REPO_ROOT / "configs" / "phase2" / "W1_kaggle.json").read_text())
    # shrink every run to 2 tasks so fake runs are tiny; ids/batches stay the real ones
    for e in src["runs"]:
        e["n_tasks"] = 2
        e["expected_records"] = 2 * 3 * e["n_trials"]
    (repo / "configs" / "phase2" / "W1_kaggle.json").write_text(json.dumps(src), encoding="utf-8")
    return repo, src


def fake_kaggle_run(repo: Path, e: dict, gpu_name="Tesla T4", n_records=None, complete=True) -> Path:
    out = repo / e["output_dir"]
    rd = out / "upgradecanary-real-run"
    rd.mkdir(parents=True, exist_ok=True)
    n = e["expected_records"] if n_records is None else n_records
    (rd / "parsed_results.jsonl").write_text("".join(json.dumps({"i": i}) + "\n" for i in range(n)), encoding="utf-8")
    (rd / "raw_outputs.jsonl").write_text("{}\n", encoding="utf-8")
    (rd / "summary.json").write_text("{}", encoding="utf-8")
    (rd / "run_manifest.json").write_text(json.dumps({"hardware": {"gpu": {"name": gpu_name}},
                                                      "phase2": {"id": e["id"]}}), encoding="utf-8")
    (out / "_status.json").write_text(json.dumps({"completed": complete, "record_count_ok": complete,
                                                   "expected_records": e["expected_records"]}), encoding="utf-8")
    cfg = repo / "results_v3" / "_generated_configs" / f"{e['folder']}__{e['model']}__{e['suite']}.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("a: 1\n", encoding="utf-8")
    return out


def test_worker_lane_runs_zips_deletes_models_and_resumes(kaggle_repo, tmp_path):
    import p2_worker
    repo, src = kaggle_repo
    by_id = {e["id"]: e for e in src["runs"]}
    batch = src["batches"][1]
    models, state, export = tmp_path / "models", tmp_path / "state", tmp_path / "export"
    downloads, launched = [], []

    def downloader(f, models_dir, log):
        models_dir.mkdir(parents=True, exist_ok=True)
        (models_dir / f.filename).write_bytes(b"x")
        downloads.append(f.filename)
        return {"filename": f.filename, "sha256_actual": f.sha256}

    def runner(cmd):
        rid = cmd[cmd.index("--run-id") + 1]
        assert (models / Path(cmd[cmd.index("--gguf") + 1]).name).exists()          # the GGUF is there while the run is
        fake_kaggle_run(repo, by_id[rid])
        launched.append(rid)
        return 0
    res = p2_worker.run_lane(repo, models, state, export, batch["id"], "0", downloader=downloader, runner=runner)
    lane0 = batch["lanes"][0]["runs"]
    assert res["ok"] == lane0 == launched and not res["failed"]
    assert sorted(p.name for p in export.glob("p2__*.zip")) == sorted(
        f"p2__{by_id[r]['folder']}__{by_id[r]['model']}__{by_id[r]['suite']}.zip" for r in lane0)
    assert not [p for p in models.iterdir()]                                       # models deleted after use
    # lane 1 belongs to the other GPU
    res1 = p2_worker.run_lane(repo, models, state, export, batch["id"], "1", downloader=downloader, runner=runner)
    assert set(res1["ok"]) == set(batch["lanes"][1]["runs"])
    # resumable: a second launch does nothing and downloads nothing
    downloads.clear()
    res2 = p2_worker.run_lane(repo, models, state, export, batch["id"], "0", downloader=downloader, runner=runner)
    assert res2["ok"] == [] and sorted(res2["skipped_done"]) == sorted(lane0) and downloads == []


def test_worker_failure_time_budget_and_missing_lane(kaggle_repo, tmp_path):
    import p2_worker
    repo, src = kaggle_repo
    by_id = {e["id"]: e for e in src["runs"]}
    last = src["batches"][-1]                                                      # a one-lane batch
    assert len(last["lanes"]) == 1
    models, state, export = tmp_path / "m", tmp_path / "s", tmp_path / "e"
    dl = lambda f, d, log: (d.mkdir(parents=True, exist_ok=True), (d / f.filename).write_bytes(b"x"), {"filename": f.filename})[2]
    assert p2_worker.run_lane(repo, models, state, export, last["id"], "1", downloader=dl, runner=lambda c: 0)["ok"] == []
    res = p2_worker.run_lane(repo, models, state, export, last["id"], "0", downloader=dl, runner=lambda c: 1)
    assert res["failed"] == last["lanes"][0]["runs"] and not list(export.glob("p2__*.zip"))
    assert not list(models.iterdir())
    res = p2_worker.run_lane(repo, models, state, export, last["id"], "0", downloader=dl, runner=lambda c: 0,
                             deadline=0.0)                                         # time budget already used up
    assert res["skipped_time"] == last["lanes"][0]["runs"] and res["ok"] == []
    res = p2_worker.run_lane(repo, models, state, export, last["id"], "0", downloader=dl, runner=lambda c: 0,
                             hard_limit=1.0)                                       # would end after the hard limit
    assert res["skipped_time"] == last["lanes"][0]["runs"]
    bad_dl = lambda f, d, log: (_ for _ in ()).throw(RuntimeError("hash mismatch"))
    res = p2_worker.run_lane(repo, models, state, export, last["id"], "0", downloader=bad_dl, runner=lambda c: 0)
    assert res["failed"] == last["lanes"][0]["runs"]                               # an unverifiable model is never used


def test_import_accepts_good_zips_and_refuses_bad_ones(kaggle_repo, tmp_path):
    import p2_worker
    from scripts.phase2 import import_kaggle as imp
    repo, src = kaggle_repo
    mdir = repo / "configs" / "phase2"
    e = src["runs"][0]
    fake_kaggle_run(repo, e)
    zdir = tmp_path / "zips"
    z = p2_worker.make_run_zip(repo, e, zdir)
    entries = {x["id"]: x for x in src["runs"]}
    entry, problems = imp.verify_run_zip(z, entries)
    assert problems == [] and entry["id"] == e["id"]
    dest = tmp_path / "laptop"
    res = imp.import_zips(zdir, dest, apply=False, manifest_dir=mdir)
    assert res[0]["status"] == "ok" and not (dest / e["output_dir"]).exists()
    assert imp.import_zips(zdir, dest, apply=True, manifest_dir=mdir)[0]["status"] == "imported"
    assert (dest / e["output_dir"] / "_status.json").exists()
    again = imp.import_zips(zdir, dest, apply=True, manifest_dir=mdir)
    assert again[0]["status"] == "REFUSED" and "already exists" in again[0]["problems"][-1]    # never overwritten

    def zip_of(e2, **kw):
        shutil_rm(repo / e2["output_dir"])
        fake_kaggle_run(repo, e2, **kw)
        return p2_worker.make_run_zip(repo, e2, tmp_path / "bad")
    e2 = src["runs"][1]
    for kw, msg in (({"gpu_name": "NVIDIA GeForce RTX 4060"}, "not run on a T4"), ({"n_records": 5}, "parsed records"),
                    ({"complete": False}, "_status.json")):
        _, probs = imp.verify_run_zip(zip_of(e2, **kw), entries)
        assert any(msg in p for p in probs), (kw, probs)
    # a zip that writes outside results_v3 is refused
    evil = tmp_path / "evil" / "p2__x.zip"
    evil.parent.mkdir()
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../escape.txt", "x")
    assert imp.verify_run_zip(evil, entries)[0] is None
    notzip = tmp_path / "evil" / "p2__y.zip"
    notzip.write_text("not a zip")
    assert "not a readable zip" in imp.verify_run_zip(notzip, entries)[1][0]
    # a run that is not in the manifest is refused
    other = dict(e2, id="F5/nobody/synthetic", folder="F5", model="nobody", output_dir="results_v3/F5/nobody/synthetic")
    fake_kaggle_run(repo, other)
    assert "not in the W1_kaggle manifest" in imp.verify_run_zip(p2_worker.make_run_zip(repo, other, tmp_path / "bad"), entries)[1][0]


def shutil_rm(p):
    import shutil
    shutil.rmtree(p, ignore_errors=True)


def test_session_picks_next_incomplete_batch_and_restores(kaggle_repo, tmp_path):
    import p2_session
    import p2_worker
    repo, src = kaggle_repo
    assert p2_session.pick_batch(repo, "next")["id"] == src["batches"][0]["id"]
    assert p2_session.pick_batch(repo, "K03")["id"] == "K03"
    by_id = {e["id"]: e for e in src["runs"]}
    for lane in src["batches"][0]["lanes"]:
        for r in lane["runs"]:
            fake_kaggle_run(repo, by_id[r])
    assert p2_session.pick_batch(repo, "next")["id"] == src["batches"][1]["id"]
    assert "complete" in p2_session.status_table(repo, src["batches"][0]).splitlines()[0]
    # restore: a zip from an earlier session is extracted into a clean repo, once
    zdir = tmp_path / "input" / "earlier"
    e = by_id[src["batches"][0]["lanes"][0]["runs"][0]]
    p2_worker.make_run_zip(repo, e, zdir)
    shutil_rm(repo / e["output_dir"])
    out = p2_session.restore_from_inputs(repo, tmp_path / "export", tmp_path / "input")
    assert out == [f"RESTORED {e['id']} from p2__{e['folder']}__{e['model']}__{e['suite']}.zip"]
    assert p2_worker.is_done(repo, e)
    assert p2_session.restore_from_inputs(repo, tmp_path / "export", tmp_path / "input")[0].startswith("already have")


def test_notebook_pins_phase1_environment_and_checks_for_t4():
    nb = json.loads((REPO_ROOT / "kaggle" / "phase2" / "p2_runner.ipynb").read_text(encoding="utf-8"))
    code = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    import ast
    for c in nb["cells"]:
        if c["cell_type"] == "code":
            ast.parse("".join(c["source"]))
    assert 'PINNED_LLAMA_CPP = "0.3.35"' in code and "ki.build_env(PINNED_LLAMA_CPP" in code
    assert "LLAMA_CPP_PYTHON_VERSION == PINNED_LLAMA_CPP" in code
    assert "T4" in code and "len(lines) == 2" in code
    assert "p2.launch_workers" in code and "p2.pick_batch" in code and "W1_kaggle.json" in code
    from kaggle_plan import LAPTOP_PYTHON, LLAMA_CPP_PYTHON_VERSION
    assert LLAMA_CPP_PYTHON_VERSION == "0.3.35" and LAPTOP_PYTHON == "3.12.12"
    # the committed notebook is what the builder makes
    import subprocess
    before = (REPO_ROOT / "kaggle" / "phase2" / "p2_runner.ipynb").read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(REPO_ROOT / "kaggle" / "phase2" / "make_p2_notebook.py")], check=True, capture_output=True)
    assert (REPO_ROOT / "kaggle" / "phase2" / "p2_runner.ipynb").read_text(encoding="utf-8") == before


# =============================================================================== split test
def stub_split_runner(perturb=None):
    """Deterministic fake model: the output depends only on (task, condition, trial seed)."""
    def run(cfg_path):
        cfg = yaml.safe_load(Path(cfg_path).read_text(encoding="utf-8"))
        rid = "run-" + Path(cfg["output_dir"]).name
        d = Path(cfg["output_dir"]) / rid
        d.mkdir(parents=True, exist_ok=True)
        tasks = [json.loads(l)["task_id"] for l in Path(cfg["data"]).read_text(encoding="utf-8").splitlines() if l.strip()]
        raw, parsed = [], []
        for t in tasks:
            for cond in cfg["conditions"]:
                for i, (seed, temp) in enumerate(zip(cfg["trial_seeds"], cfg["trial_temperatures"])):
                    out = f'{{"name": "f", "arguments": {{"x": {hash((t, cond, seed if temp else 0)) % 7}}}}}'
                    if perturb and perturb(t, cond, seed):
                        out = out + " "
                    raw.append({"task_id": t, "condition": cond, "trial_index": i, "raw_output": out, "prompt_sha256": "p-" + t})
                    parsed.append({"task_id": t, "condition": cond, "trial_index": i, "temperature": temp, "seed": seed,
                                   "parsed_call": {"x": out.strip()}, "metrics": {"score": float(out.strip().endswith("3}}"))}})
        (d / "raw_outputs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in raw), encoding="utf-8")
        (d / "parsed_results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in parsed), encoding="utf-8")
        return {"run_id": rid, "num_records": len(parsed)}
    return run


def _tasks(tmp_path, n=6):
    (tmp_path / "data").mkdir(exist_ok=True)
    lines = [json.dumps({"task_id": f"t{i}"}) for i in range(n)]
    (tmp_path / "data" / "base_tasks.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_split_test_identical_when_the_split_is_harmless(tmp_path, monkeypatch):
    from scripts.phase2 import split_test
    monkeypatch.chdir(tmp_path)
    _tasks(tmp_path)
    res = split_test.run_split_test("gemma2_2b", "synthetic", "D", 4, Path("st"), root=tmp_path, runner=stub_split_runner())
    assert res["all_identical"] and res["n_matched"] == res["n_a"] == res["n_b"] == 4 * 3 * 10
    assert [res["runs"][k]["num_records"] for k in ("A", "B1", "B2")] == [120, 36, 84]
    assert res["groups"]["all"]["pct_raw_identical"] == 100 and set(res["groups"]) >= {f"trial_{i}" for i in range(10)}
    assert (tmp_path / "st" / "D_result.json").exists() and "all identical: True" in (tmp_path / "st" / "split_test_report.md").read_text()
    subset = (tmp_path / "st" / "tasks_first4.jsonl").read_text().splitlines()
    assert len(subset) == 4
    for k in ("A", "B1", "B2"):
        assert res["runs"][k]["wall_clock_seconds"] >= 0


def test_split_test_detects_a_difference_per_trial(tmp_path, monkeypatch):
    from scripts.phase2 import split_test
    monkeypatch.chdir(tmp_path)
    _tasks(tmp_path)
    calls = []

    def only_b(t, cond, seed):
        return seed == 1239 and cond == "baseline" and len(calls) > 0
    runner = stub_split_runner(only_b)

    def counting(cfg_path):
        r = runner(cfg_path)
        calls.append(cfg_path)
        return r
    res = split_test.run_split_test("gemma2_2b", "synthetic", "D", 4, Path("st2"), root=tmp_path, runner=counting)
    g = res["groups"]
    assert not res["all_identical"] and g["trial_5"]["pct_raw_identical"] == pytest.approx(100 * 8 / 12)
    assert g["trial_4"]["pct_raw_identical"] == 100 and g["trial_0"]["pct_raw_identical"] == 100
    assert res["examples"] and res["examples"][0]["key"][2] == 5


def test_compare_split_handles_unmatched_records():
    from scripts.phase2.split_test import compare_split
    rec = lambda raw, temp=0.7: {"raw_output": raw, "prompt_sha256": "p", "parsed_call": "c", "score": 1.0, "temperature": temp}
    a = {("t", "c", 0): rec("x", 0.0), ("t", "c", 1): rec("y")}
    b = {("t", "c", 0): rec("x", 0.0)}
    r = compare_split(a, b)
    assert not r["all_identical"] and r["n_matched"] == 1 and r["groups"]["greedy"]["pct_raw_identical"] == 100
