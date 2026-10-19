"""Merging the parts of a run (PLAN_PHASE2.md section 2): every refusal and every
size, on small fake runs. No real data."""

import json

import pytest

from tests.fake_phase2 import write_part
from vdanalysis.loader import MissingRun
from vdanalysis.phase2.config import PartSpec
from vdanalysis.phase2.merge import MergeError, merge_parts

TASKS = range(4)


def parts_of(*items):
    return [(d, PartSpec(root="x", trial_offset=off), True) for d, off in items]


def make(tmp_path, name, trials, offset, **kw):
    return write_part(tmp_path, name, "D", "m", "s", trials, offset, tasks=kw.pop("tasks", TASKS), **kw)


def test_two_parts_merge_onto_one_trial_axis(tmp_path):
    a = make(tmp_path, "a", range(0, 3), 0)
    b = make(tmp_path, "b", range(3, 10), 3)
    run = merge_parts("D", "m", "s", parts_of((a, 0), (b, 3)), seed_base=1234, expected_trials=10)
    assert run.trials == list(range(10))
    assert len(run) == 4 * 3 * 10
    assert run.warnings == []
    assert run.greedy_trials() == {0}
    assert run.trial_info[3] == (0.7, 1237)
    assert len(run.prompts) == 4 * 3                       # one prompt per (task, condition)


@pytest.mark.parametrize("n_tasks,n_trials", [(1, 1), (2, 2), (3, 7), (7, 4), (50, 3)])
def test_no_fixed_record_count(tmp_path, n_tasks, n_trials):
    d = make(tmp_path, "a", range(n_trials), 0, tasks=range(n_tasks))
    run = merge_parts("D", "m", "s", parts_of((d, 0)), seed_base=1234, expected_trials=n_trials)
    assert len(run) == n_tasks * 3 * n_trials              # 900 is just one of many valid sizes
    assert run.warnings == []


def test_incomplete_grid_is_a_warning_not_an_error(tmp_path):
    d = make(tmp_path, "a", range(0, 3), 0)
    run = merge_parts("D", "m", "s", parts_of((d, 0)), seed_base=1234, expected_trials=10)
    assert len(run) == 4 * 3 * 3
    assert any("miss trials" in w for w in run.warnings)


def test_trials_beyond_expected_warn(tmp_path):
    d = make(tmp_path, "a", range(0, 5), 0)
    run = merge_parts("D", "m", "s", parts_of((d, 0)), seed_base=1234, expected_trials=3)
    assert any("beyond the expected" in w for w in run.warnings)


def test_duplicate_task_condition_trial_is_refused(tmp_path):
    a = make(tmp_path, "a", range(0, 4), 0)
    b = make(tmp_path, "b", range(3, 6), 3)               # trial 3 stored twice
    with pytest.raises(MergeError, match="duplicate record"):
        merge_parts("D", "m", "s", parts_of((a, 0), (b, 3)), seed_base=1234, expected_trials=6)


def test_prompts_must_be_byte_identical_across_parts(tmp_path):
    a = make(tmp_path, "a", range(0, 3), 0)
    b = make(tmp_path, "b", range(3, 6), 3, run_seed=9999)   # different run seed -> different prompts
    with pytest.raises(MergeError, match="not byte-identical"):
        merge_parts("D", "m", "s", parts_of((a, 0), (b, 3)), seed_base=1234, expected_trials=6)


def test_prompts_must_be_identical_across_trials_of_one_part(tmp_path):
    a = make(tmp_path, "a", range(0, 3), 0)
    lines = [json.loads(l) for l in (a / "raw_outputs.jsonl").read_text().splitlines()]
    lines[-1]["prompt_sha256"] = "0" * 64                 # last record: a different prompt
    (a / "raw_outputs.jsonl").write_text("".join(json.dumps(l) + "\n" for l in lines))
    with pytest.raises(MergeError, match="not byte-identical"):
        merge_parts("D", "m", "s", parts_of((a, 0)), seed_base=1234, expected_trials=3)


def test_wrong_trial_offset_is_caught_by_the_seed_check(tmp_path):
    a = make(tmp_path, "a", range(0, 3), 0)
    b = make(tmp_path, "b", range(3, 6), 3)
    with pytest.raises(MergeError, match="expected 1238"):
        merge_parts("D", "m", "s", parts_of((a, 0), (b, 4)), seed_base=1234, expected_trials=6)


def test_missing_raw_outputs_refused_unless_allowed(tmp_path):
    a = make(tmp_path, "a", range(0, 3), 0, raw=False)
    with pytest.raises(MergeError, match="cannot verify prompts"):
        merge_parts("D", "m", "s", [(a, PartSpec(root="x"), True)], seed_base=1234, expected_trials=3)
    run = merge_parts("D", "m", "s", [(a, PartSpec(root="x"), False)], seed_base=1234, expected_trials=3)
    assert len(run) == 4 * 3 * 3 and run.prompts == {}


def test_drift_type_must_agree_across_parts(tmp_path):
    a = make(tmp_path, "a", range(0, 3), 0)
    b = make(tmp_path, "b", range(3, 6), 3)
    rows = [json.loads(l) for l in (b / "parsed_results.jsonl").read_text().splitlines()]
    for r in rows:
        if r["condition"] == "schema_drift" and r["task_id"] == "t000":
            r["drift"]["type"] = "field_drop"
    (b / "parsed_results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(MergeError, match="drift/fault type"):
        merge_parts("D", "m", "s", parts_of((a, 0), (b, 3)), seed_base=1234, expected_trials=6)


def test_temperature_must_agree_for_a_trial(tmp_path):
    a = make(tmp_path, "a", range(0, 3), 0)
    rows = [json.loads(l) for l in (a / "parsed_results.jsonl").read_text().splitlines()]
    rows[-1]["temperature"] = 1.5
    (a / "parsed_results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(MergeError, match="several temperatures"):
        merge_parts("D", "m", "s", parts_of((a, 0)), seed_base=1234, expected_trials=3)


def test_disjoint_task_sets_merge(tmp_path):
    """W3: original tasks (trials 0-9) and added tasks (trials 0-9) are separate runs."""
    a = make(tmp_path, "a", range(10), 0, tasks=range(0, 4))
    b = make(tmp_path, "b", range(10), 0, tasks=range(4, 7))
    run = merge_parts("D", "m", "s", parts_of((a, 0), (b, 0)), seed_base=1234, expected_trials=10)
    assert run.tasks == {f"t{i:03d}" for i in range(7)} and len(run) == 7 * 3 * 10


def test_same_tasks_twice_is_a_duplicate(tmp_path):
    a = make(tmp_path, "a", range(3), 0, tasks=range(0, 4))
    b = make(tmp_path, "b", range(3), 0, tasks=range(2, 6))
    with pytest.raises(MergeError, match="duplicate record"):
        merge_parts("D", "m", "s", parts_of((a, 0), (b, 0)), seed_base=1234, expected_trials=3)


def test_views(tmp_path):
    a = make(tmp_path, "a", range(0, 4), 0)
    run = merge_parts("D", "m", "s", parts_of((a, 0)), seed_base=1234, expected_trials=4)
    g, s = run.view("greedy"), run.view("sampled")
    assert g.trials == [0] and s.trials == [1, 2, 3]
    assert len(g) + len(s) == len(run)
    sub = run.view("all", tasks={"t000", "t001"})
    assert sub.tasks == {"t000", "t001"} and len(sub) == 2 * 3 * 4
    assert run.view("all") is run
    with pytest.raises(ValueError):
        run.view("bogus")
    assert set(g.prompts) <= set(run.prompts)
