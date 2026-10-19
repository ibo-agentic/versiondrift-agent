"""F8/F10 rescoring of the new D parts and merging them with Phase 1's rescored part. FAKE data only
(the fake rows carry no parsed call, so F8 changes nothing and the rescored data must equal D)."""

import copy
from pathlib import Path

import pytest

from tests.fake_phase2 import build_phase2_world
from vdanalysis.config import Config
from vdanalysis.phase2.analysis import Phase2Analysis
from vdanalysis.phase2.config import Phase2Config
from vdanalysis.phase2.rescore_v3 import rescore_v3_parts
from vdanalysis.rescore import rescore_tree


def test_rescored_new_parts_merge_with_phase1_rescored_part(tmp_path):
    raw, paths = build_phase2_world(tmp_path)
    raw = copy.deepcopy(raw)
    raw["protocols"]["F8"] = {"folder": "F8", "root": "rescored"}
    raw["phase2"]["protocols"]["F8"] = {"parts": raw["phase2"]["protocols"]["F7"]["parts"]}
    cfg = Phase2Config(raw, base_dir=tmp_path)
    no_tasks = lambda suite: {}
    # Phase 1's part, rescored by Phase 1's own tool (single run dir under results_v2/D)
    rescore_tree(Config(copy.deepcopy(raw)), "F8", "D", paths["rescored"], models=["a_new"], suites=["s1"], tasks_loader=no_tasks)
    log = rescore_v3_parts(cfg, "F8", paths["rescored_v3"], models=["a_new"], suites=["s1"], tasks_loader=no_tasks)
    assert len(log) == 1 and log[0]["records"] == 20 * 3 * 7 and log[0]["diffs"] == 0
    an = Phase2Analysis(cfg)
    f8, d = an.run_for("F8", "a_new", "s1"), an.run_for("D", "a_new", "s1")
    assert f8.trials == list(range(10)) and f8.keys == d.keys
    # the Phase 1 part came from results_root, so it was not rescored a second time
    assert [Path(p).parts[-4] for p in f8.parts] == ["F8", "F8"]


def test_rescoring_never_writes_into_protected_folders(tmp_path):
    raw, paths = build_phase2_world(tmp_path)
    cfg = Phase2Config(raw, base_dir=tmp_path)
    for bad in ("results_v3", "results_v2"):
        with pytest.raises(ValueError, match="protected"):
            rescore_v3_parts(cfg, "F8", tmp_path / bad / "x", models=["a_new"], suites=["s1"], tasks_loader=lambda s: {})
