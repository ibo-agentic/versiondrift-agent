"""Read-only sanity check of finished Phase 2 runs, on the FAKE world (tests/fake_phase2.py)."""

import json

import pytest

from scripts.phase2.sanity_check import check_run, report
from tests.fake_phase2 import N_TASKS
from tests.phase2_fixtures import world  # noqa: F401  (fixture)


def entry_for(model="a_new", suite="s1"):
    return {"id": f"D/{model}/{suite}", "folder": "D", "model": model, "suite": suite,
            "output_dir": f"results_v3/D/{model}/{suite}", "expected_records": N_TASKS * 3 * 7,
            "trial_seeds": list(range(1237, 1244)), "temperatures": [0.7] * 7}


def write_status(root, e, **kw):
    st = {"completed": True, "num_records": e["expected_records"], "expected_records": e["expected_records"],
          "record_count_ok": True, "elapsed_seconds": 3600.0}
    st.update(kw)
    (root / e["output_dir"] / "_status.json").write_text(json.dumps(st), encoding="utf-8")


def test_good_run_passes_and_reports_rates(world):
    cfg, _, _, root = world
    e = entry_for()
    write_status(root, e)
    r = check_run("W1_laptop", e, cfg, root)
    assert r["problems"] == [] and r["merge"]["ok"] and r["merge"]["trials"] == list(range(10))
    assert r["records_per_trial"] == {i: N_TASKS * 3 for i in range(7)}
    assert r["trial_seeds_in_records"] == list(range(1237, 1244))
    assert r["new_trials"]["n_records"] == N_TASKS * 3 * 7 and r["phase1_trials_all"]["n_records"] == N_TASKS * 3 * 3
    assert r["phase1_trials_sampled"]["n_records"] == N_TASKS * 3 * 2
    assert r["new_trials"]["truncation_rate"] == 0 and r["new_trials"]["parse_rate_tool_call"] == 1.0
    assert "merge with Phase 1: PASS" in report([r])


def test_problems_are_reported(world):
    cfg, _, _, root = world
    e = entry_for("b_new", "s2")
    write_status(root, e, completed=False, error="boom")
    r = check_run("W1_laptop", e, cfg, root)
    assert any("boom" in p for p in r["problems"]) and any("not complete" in p for p in r["problems"])
    e2 = dict(entry_for("c_new", "s1"), expected_records=999)
    write_status(root, e2, num_records=420)
    assert any("manifest expects 999" in p for p in check_run("W1_laptop", e2, cfg, root)["problems"])
    e3 = dict(entry_for("d_new", "s1"), trial_seeds=list(range(1300, 1307)))
    write_status(root, e3)
    assert any("trial seeds" in p for p in check_run("W1_laptop", e3, cfg, root)["problems"])
    missing = entry_for("a_old", "s2")
    assert any("_status.json" in p for p in check_run("W1_laptop", missing, cfg, root)["problems"])


def test_a_run_that_does_not_merge_is_flagged(world):
    cfg, _, _, root = world
    e = entry_for("a_old", "s1")
    write_status(root, e)
    rd = next((root / e["output_dir"]).iterdir())
    rows = [json.loads(l) for l in (rd / "parsed_results.jsonl").read_text().splitlines()]
    rows[0]["trial_index"] = 0                        # collides with Phase 1's trial 0 of the same task and condition
    rows[0]["seed"] = 1234
    (rd / "parsed_results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    r = check_run("W1_laptop", e, cfg, root)
    assert not r["merge"]["ok"] and any("merge with Phase 1 failed" in p for p in r["problems"])
