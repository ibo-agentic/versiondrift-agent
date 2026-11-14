"""W6 sampling (scripts/phase2/w6_sample.py). FAKE data only; the real frame is never read here."""

from collections import Counter

import pytest

from scripts.phase2.w6_sample import Cand, allocate, build_frame, draw
from tests.fake_phase2 import MODELS, N_TASKS, SUITES, build_phase2_world
from vdanalysis.phase2.config import Phase2Config

SIX = [(su, v) for su in ("bfcl_multiple", "bfcl_simple", "synthetic") for v in ("fail", "pass")]


def test_allocation_33_33_33_33_34_34_and_the_two_largest_get_34():
    sizes = dict(zip(SIX, [900, 5000, 700, 8000, 3000, 6000]))
    counts, log = allocate(sizes)
    assert sum(counts.values()) == 200
    assert sorted(counts.values()) == [33, 33, 33, 33, 34, 34]
    assert {s for s, n in counts.items() if n == 34} == {SIX[3], SIX[5]}       # 8000 and 6000 are the largest
    assert not any("top-up" in line for line in log)


def test_ties_for_the_extra_records_go_by_stratum_name():
    counts, _ = allocate({s: 1000 for s in SIX})
    assert {s for s, n in counts.items() if n == 34} == {SIX[0], SIX[1]}


def test_short_stratum_is_taken_whole_and_topped_up_from_the_largest():
    sizes = dict(zip(SIX, [10, 5000, 700, 8000, 3000, 6000]))
    counts, log = allocate(sizes)
    assert counts[SIX[0]] == 10 and sum(counts.values()) == 200
    assert counts[SIX[3]] == 34 + 23 and counts[SIX[5]] == 34            # 33 - 10 = 23 extra, all to the largest
    assert any("top-up: 23 more from" in line for line in log)
    assert any("shortfall of 23" in line for line in log)


def test_top_up_moves_to_the_next_largest_when_the_largest_is_exhausted():
    sizes = dict(zip(SIX, [0, 40, 40, 40, 1000, 36]))
    counts, _ = allocate(sizes)
    assert sum(counts.values()) == 200 and all(counts[s] <= sizes[s] for s in SIX)
    assert counts[SIX[0]] == 0 and counts[SIX[4]] == 34 + 33                  # its own 34 plus the 33 shortfall


def test_frame_too_small_is_an_error():
    with pytest.raises(ValueError, match="fewer than 200"):
        allocate({s: 10 for s in SIX})


@pytest.fixture(scope="module")
def fake_cands(tmp_path_factory):
    root = tmp_path_factory.mktemp("w6_world")
    raw, _ = build_phase2_world(root)
    cfg = Phase2Config(raw, base_dir=root)
    cands, notes = build_frame(cfg)
    return cfg, cands, notes


def test_frame_is_d_and_r_main_runs_stress_conditions_all_ten_trials(fake_cands):
    cfg, cands, notes = fake_cands
    assert {c.protocol for c in cands} == {"D", "R"}
    assert {c.condition for c in cands} == set(cfg.stress)                      # no baseline records
    assert {c.trial for c in cands} == set(range(10))                           # 0-2 from the v2 part, 3-9 from v3
    n = len(MODELS) * len(SUITES) * 2 * N_TASKS * len(cfg.stress) * 10
    assert len(cands) == n
    assert len({(c.protocol, c.model, c.suite, c.condition, c.task_id, c.trial) for c in cands}) == n
    assert any("runs read" in x for x in notes)


def test_trials_come_from_the_right_root(fake_cands):
    _, cands, _ = fake_cands
    for c in cands:
        assert ("results_v2" in c.part) == (c.trial < 3) and ("results_v3" in c.part) == (c.trial >= 3)


def test_draw_is_stratified_deterministic_and_has_no_duplicates(fake_cands):
    _, cands, _ = fake_cands
    a, info = draw(cands, seed=20261020, total=40)
    b, _ = draw(list(reversed(cands)), seed=20261020, total=40)               # file order must not matter
    assert a == b and len(a) == 40 and len(set(a)) == 40
    c, _ = draw(cands, seed=1, total=40)
    assert c != a
    per = Counter(x.stratum for x in a)
    assert all(row["drawn"] == per[(row["suite"], row["verdict"])] for row in info["strata"])
    assert info["seed"] == 20261020 and info["total"] == 40


def test_verdict_is_the_studys_record_score(tmp_path):
    """pass = record_score 1.0: schema_drift needs every component true, fault_reporting uses its score."""
    import json
    raw, paths = build_phase2_world(tmp_path)
    cfg = Phase2Config(raw, base_dir=tmp_path)
    f = next((paths["v2"] / "D" / "a_old" / "s1").glob("*/parsed_results.jsonl"))
    rows = [json.loads(l) for l in open(f, encoding="utf-8")]
    want = {}
    for i, r in enumerate(rows):
        if r["condition"] == "schema_drift" and r["task_id"] == "t000":
            r["metrics"]["tool_name_ok"] = False                 # one component false -> fail, whatever "score" says
            r["metrics"]["score"] = 1.0
            want[i] = "fail"
        if r["condition"] == "fault_reporting" and r["task_id"] == "t001":
            r["metrics"]["score"] = 0.0
            want[i] = "fail"
    f.write_text("".join(json.dumps(r) + chr(10) for r in rows), encoding="utf-8")
    cands, _ = build_frame(cfg, protocols=("D",))
    got = {c.line: c.verdict for c in cands if c.model == "a_old" and c.suite == "s1" and "results_v2" in c.part}
    assert {i: v for i, v in got.items() if i in want} == want
    assert Counter(got.values()) == Counter({"fail": len(want), "pass": len(got) - len(want)})
