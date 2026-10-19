"""W3 added-task files: the original 100-task files must be unchanged, the added BFCL tasks must be exactly the
remaining eligible items with no overlap, no duplicate ids or prompts. No model is run."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts.phase2 import plan, w3_tasks
from scripts.phase2.check_configs import check_all, check_task_files
from upgradecanary.tasks import load_tasks

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

# SHA-256 of each original file with CRLF folded to LF (the same normalization the Kaggle manifests use).
# base_tasks.jsonl's hash is the one recorded in every Phase 1 Kaggle run_manifest.json.
ORIGINALS = {
    "base_tasks.jsonl": "41dc0a2054a1e942fa9428729e919fef9a6952da6d719e93f10ee940fe4f6037",
    "bfcl_tasks.jsonl": "18d74074d4eca9c33b1ade514aa146980f85ac6d2d74654f1ba710d95ccb19e7",
    "bfcl_tasks_provenance.jsonl": "cd48ba80cf3c3d665fdcfa226173f07ff6193796e6fe6c3c96602f8c54d67a87",
    "bfcl_multiple_tasks.jsonl": "0884a359ce7cd3ed0bbaaa42a34fbfa13f8aca65c9e8c40b4f7eb1a946e0c570",
    "bfcl_multiple_tasks_provenance.jsonl": "0071cbc588c875e31a2034ec462f87bf3ca7ad1a34e83b50bc81ac5b132d1e91",
}
HAVE_SOURCE = (ROOT / "external" / "gorilla").exists()
needs_source = pytest.mark.skipif(not HAVE_SOURCE, reason="BFCL source data (external/gorilla) not present")


def lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rows(path: Path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.mark.parametrize("name,sha", sorted(ORIGINALS.items()))
def test_original_task_files_are_unchanged(name, sha):
    assert lf_sha(DATA / name) == sha


def test_originals_still_hold_100_tasks_each():
    for name in ("base_tasks.jsonl", "bfcl_tasks.jsonl", "bfcl_multiple_tasks.jsonl"):
        assert len(rows(DATA / name)) == 100 and len(load_tasks(DATA / name)) == 100


@pytest.mark.parametrize("kind,n_added", [("simple", 91), ("multiple", 9)])
def test_added_bfcl_files_have_the_expected_counts_and_no_problems(kind, n_added):
    new = rows(w3_tasks.path_for(kind))
    assert len(new) == n_added == len(rows(w3_tasks.path_for(kind, provenance=True)))
    assert w3_tasks.check_added(kind) == []
    assert len(load_tasks(w3_tasks.path_for(kind))) == n_added            # they load as ordinary tasks


@pytest.mark.parametrize("kind", ["simple", "multiple"])
def test_no_overlap_unique_ids_no_duplicate_prompts(kind):
    old = rows(DATA / f"{w3_tasks.KINDS[kind]['original']}.jsonl")
    new = rows(w3_tasks.path_for(kind))
    ids = [t["task_id"] for t in old + new]
    assert len(set(ids)) == len(ids)                                       # unique across the merged set
    assert not {t["source_id"] for t in new} & {t["source_id"] for t in old}
    assert not {t["prompt"] for t in new} & {t["prompt"] for t in old}
    assert len({t["prompt"] for t in new}) == len(new)
    assert len({t["prompt"] for t in old + new}) == len(old + new)         # no duplicate prompt in the whole BFCL suite
    assert set(new[0]) == set(old[0])
    for t in new:
        assert t["task_id"] == sorted(t["task_id"] for t in new)[new.index(t)]      # sorted like the originals
        assert t["suite"] == "bfcl"


@needs_source
@pytest.mark.parametrize("kind,eligible", [("simple", 191), ("multiple", 109)])
def test_original_plus_added_is_exactly_the_eligible_set(kind, eligible):
    items = w3_tasks.eligible_items(kind)
    assert len(items) == eligible
    old = {t["task_id"] for t in rows(DATA / f"{w3_tasks.KINDS[kind]['original']}.jsonl")}
    new = {t["task_id"] for t in rows(w3_tasks.path_for(kind))}
    assert old | new == {it["task"]["task_id"] for it in items} and not old & new
    # every added task is eligible under the unchanged filters, and the one-per-function rule holds across the union
    names = [it["function"] for it in items]
    assert len(set(names)) == len(names)


@needs_source
@pytest.mark.parametrize("kind", ["simple", "multiple"])
def test_generation_reproduces_the_original_selection_and_the_added_files(kind, tmp_path):
    eligible, rest = w3_tasks.remaining_items(kind)                        # raises unless the original selection is reproduced
    counts = w3_tasks.write_added(kind, out_dir=tmp_path)
    assert counts["added"] == len(rest)
    for prov in (False, True):
        assert w3_tasks.path_for(kind, prov, tmp_path).read_bytes() == w3_tasks.path_for(kind, prov).read_bytes()


@needs_source
def test_generation_refuses_when_the_original_selection_cannot_be_reproduced(tmp_path):
    (tmp_path / "data").mkdir()
    for kind in w3_tasks.KINDS:
        name = w3_tasks.KINDS[kind]["original"]
        lines = (DATA / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
        (tmp_path / "data" / f"{name}.jsonl").write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")   # one task missing
    # eligible_items reads the BFCL sources from the repo root, the originals from the (altered) root
    import scripts.phase2.w3_tasks as w
    real = w.eligible_items
    w.eligible_items = lambda kind, root=ROOT: real(kind, ROOT)
    try:
        with pytest.raises(RuntimeError, match="not byte-identical"):
            w.remaining_items("simple", root=tmp_path)
    finally:
        w.eligible_items = real


def test_check_added_catches_overlaps_and_duplicates(tmp_path):
    kind = "simple"
    new = rows(w3_tasks.path_for(kind))
    prov = rows(w3_tasks.path_for(kind, provenance=True))
    old = rows(DATA / "bfcl_tasks.jsonl")

    def write(rows_new, rows_prov=None):
        w3_tasks.path_for(kind, False, tmp_path).write_text("".join(json.dumps(r) + "\n" for r in rows_new), encoding="utf-8")
        w3_tasks.path_for(kind, True, tmp_path).write_text("".join(json.dumps(r) + "\n" for r in (rows_prov or prov)), encoding="utf-8")
        return w3_tasks.check_added(kind, out_dir=tmp_path)
    assert write(new) == []
    assert any("overlap the original" in p for p in write([old[0]] + new[1:]))
    assert any("duplicate task ids" in p for p in write([new[0]] + new[:-1]))
    dup = [dict(new[1], prompt=new[0]["prompt"])] + [new[0]] + new[2:]
    assert any("duplicate prompts" in p for p in write(dup))
    same_prompt = [dict(new[0], prompt=old[0]["prompt"])] + new[1:]
    assert any("equals an original prompt" in p for p in write(same_prompt))
    assert any("share a source" in p for p in write([dict(new[0], source_id=old[0]["source_id"])] + new[1:]))
    assert any("provenance" in p for p in write(new, prov[:-1]))
    assert w3_tasks.check_added("multiple", out_dir=tmp_path / "nowhere")[0].endswith("does not exist")


# ---- manifest ----
def test_w3_manifest_points_at_the_new_files():
    m = plan.load_manifest("W3")
    by_suite = {}
    for e in m["runs"]:
        by_suite.setdefault(e["suite"], set()).add((e["data"], e["data_status"], e["n_tasks"]))
    assert by_suite["bfcl_simple"] == {("data/phase2/w3_added_bfcl_simple.jsonl", "ok", 91)}
    assert by_suite["bfcl_multiple"] == {("data/phase2/w3_added_bfcl_multiple.jsonl", "ok", 9)}
    assert set(by_suite) == {"bfcl_simple", "bfcl_multiple"}                                  # synthetic is not extended
    assert m["n_runs"] == 64 and m["estimated_hours"] == pytest.approx(34.53, abs=0.05)
    for e in m["runs"]:
        assert e["expected_records"] == e["n_tasks"] * 3 * 10 and (ROOT / e["data"]).exists()


def test_check_configs_is_clean_with_the_new_files():
    r = check_all()
    assert r["problems"] == [] and r["pending_task_files"] == [] and r["n_runs"] == 517


def test_task_file_check_catches_wrong_counts_missing_files_and_stale_pending(tmp_path):
    (tmp_path / "data").mkdir()
    f = tmp_path / "data" / "x.jsonl"
    f.write_text(json.dumps({"task_id": "a"}) + "\n" + json.dumps({"task_id": "a"}) + "\n", encoding="utf-8")
    e = {"id": "i", "data": "data/x.jsonl", "data_status": "ok", "n_tasks": 2}
    problems: list[str] = []
    check_task_files({"W3": {"runs": [e]}}, problems, tmp_path)
    assert any("1 distinct" in p for p in problems)
    problems = []
    check_task_files({"W3": {"runs": [dict(e, data="data/none.jsonl")]}}, problems, tmp_path)
    assert any("missing" in p for p in problems)
    problems = []
    assert check_task_files({"W3": {"runs": [dict(e, data_status="pending")]}}, problems, tmp_path) == ["data/x.jsonl"]
    assert any("still says pending" in p for p in problems)
