"""P1-P7 on FAKE data with known answers (tests/fake_phase2.py).
"""

import csv
import json
from pathlib import Path

import pytest

from tests.fake_phase2 import KAGGLE, MODELS, N_TASKS, SUITES, TRIM
from tests.phase2_fixtures import by, controls, row, world  # noqa: F401  (fixtures)
from vdanalysis.phase2.analysis import Phase2Analysis, ViewSpec
from vdanalysis.phase2.config import Phase2Config
from vdanalysis.phase2.stats2 import clopper_pearson
from vdanalysis.phase2.descriptive import new_flips
from vdanalysis.phase2.hypotheses2 import (p1_rows, p2_p6_rows, p3_row, p4_row, p5_row, p7_rows, reference_flip_index,
                                           replication_variants)


def test_p1(world):
    cfg, _, an, _ = world
    flips = an.flip_table([f for f in cfg.groups["h1"]])
    flipped = {(r["factor"], r["pair"], r["suite"]) for r in flips if r["flipped"]}
    assert flipped == {(f, p, s) for f, p in (("F1", "a_old->a_new"), ("F5", "d_old->d_new"), ("F6", "c_old->c_new"))
                       for s in SUITES}
    r = {x["variant"]: x for x in p1_rows(an, flips)}["main/all_pairs"]
    assert (r["n_decisions"], r["n_flipped"], r["value"]) == (8, 6, 0.75)
    assert (r["ci95_lo"], r["ci95_hi"]) == clopper_pearson(6, 8) and r["supported"] is True
    assert {x["variant"]: x for x in p1_rows(an, flips)}["main/size_changing"]["value"] is None

def test_p2_p6_primary_reading_and_the_other_three_as_descriptive(world):
    cfg, _, an, _ = world
    ref = list(csv.DictReader(open(world[1]["reference"], encoding="utf-8")))
    flips = an.flip_table(list(cfg.groups["h1"]))
    idx = reference_flip_index(ref, cfg, cfg.groups["h1"])
    assert sorted(idx) == [("a_old->a_new", "s1"), ("a_old->a_new", "s2"), ("b_old->b_new", "s1"),
                           ("c_old->c_new", "s1"), ("d_old->d_new", "s2")]
    v = replication_variants(idx, flips)
    assert v == {"labels/any": 3, "labels/all": 2, "sign/any": 3, "sign/all": 2, "n_reference_decisions": 5}
    v6 = replication_variants(reference_flip_index(ref, cfg, ["F5"]), flips, factors=["F5"])
    assert v6["n_reference_decisions"] == 2 and {v6[k] for k in v6 if k != "n_reference_decisions"} == {1}
    rows, var_rows = p2_p6_rows(an, flips, ref)
    by_h = {r["hypothesis"]: r for r in rows}
    # section 5: primary = any originally flipping factor, same label change
    assert (by_h["P2"]["value"], by_h["P2"]["n_decisions"], by_h["P2"]["threshold"], by_h["P2"]["supported"]) == (3, 5, 7, False)
    assert (by_h["P6"]["value"], by_h["P6"]["n_decisions"], by_h["P6"]["threshold"], by_h["P6"]["supported"]) == (1, 2, 4, False)
    assert by_h["P2"]["variant"] == "labels/any"
    # all four readings are kept as descriptive outputs, the primary one marked
    assert len(var_rows) == 8 and all(r["n_replicated"] <= r["n_reference_decisions"] for r in var_rows)
    prim = [r for r in var_rows if r["primary"]]
    assert {(r["hypothesis"], r["direction_rule"], r["multi_factor_rule"]) for r in prim} ==         {("P2", "labels", "any"), ("P6", "labels", "any")}
    assert {(r["direction_rule"], r["multi_factor_rule"]): r["n_replicated"] for r in var_rows if r["hypothesis"] == "P2"} ==         {("labels", "any"): 3, ("labels", "all"): 2, ("sign", "any"): 3, ("sign", "all"): 2}


def _flip(factor, pair, suite, d, f):
    return {"factor": factor, "pair": pair, "suite": suite, "d_label": d, "factor_label": f, "flipped": d != f}


def test_replicate_needs_the_same_label_change_including_the_starting_label():
    ref = {("p", "s"): [{"factor": "F5", "d_label": "neutral", "factor_label": "harmful"}]}
    assert replication_variants(ref, [_flip("F5", "p", "s", "neutral", "harmful")])["labels/any"] == 1
    # D label at 10 trials differs from Phase 1's: the same end label is not enough
    assert replication_variants(ref, [_flip("F5", "p", "s", "beneficial", "harmful")])["labels/any"] == 0
    # but the same sign of the change counts under the descriptive 'sign' reading
    assert replication_variants(ref, [_flip("F5", "p", "s", "beneficial", "harmful")])["sign/any"] == 1
    # no flip at 10 trials, or a flip under another factor: not a replication
    assert replication_variants(ref, [_flip("F5", "p", "s", "harmful", "harmful")])["labels/any"] == 0
    assert replication_variants(ref, [_flip("F1", "p", "s", "neutral", "harmful")])["labels/any"] == 0
    # any originally flipping factor suffices; 'all' needs every one of them
    ref2 = {("p", "s"): [{"factor": "F1", "d_label": "neutral", "factor_label": "harmful"},
                         {"factor": "F7", "d_label": "neutral", "factor_label": "harmful"}]}
    v = replication_variants(ref2, [_flip("F1", "p", "s", "neutral", "harmful")])
    assert (v["labels/any"], v["labels/all"]) == (1, 0)

def test_new_flips_are_those_phase1_did_not_see(world):
    cfg, _, an, _ = world
    ref = list(csv.DictReader(open(world[1]["reference"], encoding="utf-8")))
    nf = {(r["factor"], r["pair"], r["suite"]) for r in new_flips(an.flip_table(list(cfg.groups["h1"])), ref)}
    assert nf == {("F5", "d_old->d_new", "s1"), ("F6", "c_old->c_new", "s2")}


# ---- A/A (new design) ----

def test_p3_p4_p5(world, controls):
    cfg = world[0]
    p3 = p3_row(cfg, controls)
    assert (p3["n_decisions"], p3["n_flipped"], p3["value"], p3["supported"]) == (16, 2, 0.125, False)
    assert (p3["ci95_lo"], p3["ci95_hi"]) == clopper_pearson(2, 16)
    p4 = p4_row(cfg, controls)
    assert (p4["n_decisions"], p4["n_flipped"], p4["supported"]) == (8, 6, False)           # b_new's Q2_K not detected
    p5 = p5_row(cfg, controls)
    assert (p5["value"], p5["comparison_value"], p5["supported"]) == (4, 0, True)

def test_p7_needs_w3_and_compares_original_with_full_task_set(world):
    cfg, _, an, root = world
    ids = {s: {f"t{i:03d}" for i in range(N_TASKS)} for s in SUITES}
    rows = {(r["protocol"], r["suite"]): r for r in p7_rows(an, ids)}
    assert rows[("D", "s1")]["n_decisions"] == 4 and rows[("D", "s1")]["n_differ"] == 1
    assert rows[("D", "s1")]["share"] == 0.25 and "a_old->a_new:neutral->harmful" in rows[("D", "s1")]["differing"]
    assert rows[("R", "s1")]["n_differ"] == 0
    assert rows[("D", "all")]["n_differ"] == 2


def test_p7_only_covers_the_suites_w3_extends(world):
    cfg, _, an, _ = world
    cfg2 = type(cfg)({**cfg.raw, "phase2": {**cfg.p2, "w3": {**cfg.p2["w3"], "suites": ["s1"]}}}, base_dir=cfg.base_dir)
    an2 = Phase2Analysis(cfg2, an.store)
    ids = {"s1": {f"t{i:03d}" for i in range(N_TASKS)}}
    rows = p7_rows(an2, ids)
    assert {(r["protocol"], r["suite"]) for r in rows} == {("D", "s1"), ("D", "all"), ("R", "s1"), ("R", "all")}
    assert [r for r in rows if r["protocol"] == "D" and r["suite"] == "all"][0]["n_decisions"] == 4
