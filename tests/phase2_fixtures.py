"""Shared fixtures for the Phase 2 tests: the fake Phase 1 + Phase 2 world (tests/fake_phase2.py)."""

import pytest

from tests.fake_phase2 import build_phase2_world
from vdanalysis.phase2.analysis import Phase2Analysis
from vdanalysis.phase2.config import Phase2Config
from vdanalysis.phase2.controls2 import control_rows2


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = tmp_path_factory.mktemp("phase2_world")
    raw, paths = build_phase2_world(root)
    cfg = Phase2Config(raw, base_dir=root)
    return cfg, paths, Phase2Analysis(cfg), root




def row(an, proto, pair, suite):
    return an.rows(proto)[(pair, suite)]


# ---- merged runs ----


@pytest.fixture(scope="module")
def controls(world):
    _, _, an, _ = world
    return control_rows2(an, secondary=True)




def by(rows, name, model=None, suite=None):
    return [r for r in rows if r["control"] == name and (model is None or r["old"] == model)
            and (suite is None or r["suite"] == suite)]
