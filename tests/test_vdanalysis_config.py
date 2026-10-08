"""The real config file: DEVIATIONS.md rules live in it, and it loads."""

from pathlib import Path

import pytest

from vdanalysis.config import load_config
from vdanalysis.loader import Store

CFG = Path(__file__).resolve().parent.parent / "configs" / "analysis_official_folders.yaml"


@pytest.fixture(scope="module")
def cfg():
    return load_config(CFG)


def test_study_shape(cfg):
    assert len(cfg.models) == 16 and len(cfg.pairs) == 10
    assert sum(1 for p in cfg.pairs if p["split"] == "design") == 4
    assert sum(1 for p in cfg.pairs if p["split"] == "held-out") == 6
    assert {cfg.pair_name(p) for p in cfg.pairs if p.get("size_changing")} == {
        "qwen25->qwen3", "gemma2_2b->gemma3_4b"}
    assert (cfg.threshold, cfg.reps, cfg.seed) == (0.05, 10000, 1234)


def test_f6_main_pairs_are_the_four_touching_changed_models(cfg):
    assert cfg.sampling_changed == {"qwen2", "qwen25", "qwen3", "llama3", "llama31", "gemma3_4b"}
    assert [cfg.pair_name(p) for p in cfg.pairs if cfg.f6_changed(p)] == [
        "qwen2->qwen25", "qwen25->qwen3", "llama3->llama31", "gemma2_2b->gemma3_4b"]


def test_official_folders_f3_granite30_rerun_and_audit_only_original(cfg):
    store = Store(cfg)
    assert store.folder_name("F3", "granite30") == "F3_rerun"
    assert store.folder_name("F3", "granite31") == "F3"
    assert store.folder_name("F3", "phi4_mini") == "F3"  # rescored in place, same folder
    assert any(o["model"] == "phi4_mini" and o.get("rescored_in_place") for o in cfg.overrides)
    assert store.suite_dir("F3", "granite30", "synthetic").parts[-3:] == ("F3_rerun", "granite30", "synthetic")
    # the pre-fix original is refused outright (granite30 resolves to F3_rerun, so go via a no-override store)
    import copy
    from vdanalysis.config import Config
    raw = copy.deepcopy(cfg.raw)
    raw["overrides"] = []
    with pytest.raises(ValueError, match="audit-only"):
        Store(Config(raw)).suite_dir("F3", "granite30", "synthetic")


def test_f4_is_generic_json_only_and_qwen3_is_labeled(cfg):
    assert cfg.protocols["F4_json"]["confounded_models"] == {"qwen3": "grammar+thinking_blocked"}
    assert cfg.protocols["R"]["confounded_models"] == {"qwen3": "grammar+thinking_blocked"}
    assert not any("full_schema" in str(v) for v in cfg.protocols.values())
    assert cfg.raw["qwen3_study"]["thinking_off"] == "F2"


def test_rescore_factors_write_outside_results_folders(cfg):
    for f in ("F7", "F8", "F10"):
        assert cfg.protocols[f]["root"] == "rescored"
    assert Path(cfg.raw["rescored_root"]).name not in {"results", "results_smoke", "results_v2"}
