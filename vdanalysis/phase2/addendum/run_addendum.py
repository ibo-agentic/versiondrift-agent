"""Runs the addendum analyses (S1-S9) from a Phase 2 config.

    # dry run in Phase 1 mode, on results_v2 only (rerun arm = R vs R_AA, see notes in the output):
    python -m vdanalysis.phase2.addendum.run_addendum --config configs/analysis_phase1_regression.yaml \
        --out analysis/addendum_dryrun_phase1 --rerun R:R_AA

    # the single Phase 2 run (only after the code and tests are final):
    python -m vdanalysis.phase2.addendum.run_addendum --config configs/analysis_phase2.yaml \
        --out analysis_out_v3/addendum --rerun D:D_AA2 --rerun R:R_AA2

Reads run records only. Refuses to write inside results/, results_smoke/, results_v2/ or results_v3/.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np

from ...aggregate import _variant_filters
from ...loader import MissingRun
from ...run_analysis import _md_table, write_csv
from ..analysis import Phase2Analysis
from ..config import load_phase2_config
from ..run_phase2 import assert_safe_output_dir_p2, decision_protocols
from . import BOOT_REPS, BOOT_SEED, DELTA
from .data import boot_diff, cluster_arrays, draw_counts, item_outcomes, make_arrays, point_code, trial_matrix, NAME
from .s1_noise import (S1Input, expected_noise_share, hier_bootstrap, observed, per_decision_flip_prob, rerun_rate,
                       summarize)
from .s2_types import BOUNDARY, SIGN, flip_type, split_rows
from .s3_fourclass import CLASSES, class_share, classify, interval
from .s4_classes import FACTOR_CLASS, GENERATION_FACTORS, headline_flip_rate, reasonable_set
from .s5_failures import CATEGORIES, flip_changes, read_records, shares_from_records, stress_share
from .s6_power import mde, power_at, project_table, variance_components
from .s7_mcnemar import mcnemar_decision
from .s8_reference import SMALL_PAIRS, agreement
from .s9_hierarchical import run_s9

SEPARATE_PAIR = "qwen25->qwen3"


class Ctx:
    """Caches arrays and rows for one analysis object."""

    def __init__(self, an: Phase2Analysis):
        self.an = an
        self.cfg = an.cfg
        self.pairs = {self.cfg.pair_name(p): p for p in self.cfg.pairs}
        self._arr: dict[tuple, Any] = {}
        self._tasks: dict[tuple, list[str]] = {}
        self._rows: dict[str, dict] = {}

    def tasks(self, pair: str, suite: str) -> list[str] | None:
        k = (pair, suite)
        if k not in self._tasks:
            p = self.pairs[pair]
            try:
                run = self.an.run_for(self.cfg.base_protocol, p["old"], suite)
            except MissingRun:
                run = None
            self._tasks[k] = sorted({x[0] for x in run.keys}) if run is not None else None
        return self._tasks[k]

    def runs(self, proto: str, pair: str, suite: str):
        p = self.pairs[pair]
        try:
            old = self.an.run_for(proto, p["old"], suite)
            new = self.an.run_for(proto, p["new"], suite)
        except MissingRun:
            return None, None
        return old, new

    def arrays(self, proto: str, pair: str, suite: str):
        k = (proto, pair, suite)
        if k not in self._arr:
            old, new = self.runs(proto, pair, suite)
            tl = self.tasks(pair, suite)
            self._arr[k] = (make_arrays(old, new, self.cfg.stress, tl) if old is not None and new is not None and tl else None)
        return self._arr[k]

    def rows(self, proto: str) -> dict:
        if proto not in self._rows:
            try:
                self._rows[proto] = self.an.rows(proto)
            except MissingRun:
                self._rows[proto] = {}
        return self._rows[proto]


def label_of(row: dict | None, key: str = "label_point") -> str | None:
    return None if row is None else row[key]


# ---------------------------------------------------------------------------------------------- S1, S2, S3
def build_s1_input(cx: Ctx, flips: list[dict], rerun: tuple[str, str], factors: list[str]) -> S1Input:
    cfg = cx.cfg
    suites = list(cfg.suites)
    pairs = [cfg.pair_name(p) for p in cfg.pairs]
    arrays, fcells = {}, {}
    protos = {rerun[0], rerun[1], cfg.base_protocol}
    for f in factors:
        rows_f = [r for r in flips if r["factor"] == f]
        keep = _variant_filters(cfg, f, rows_f)["main"] if rows_f else (lambda r: False)
        fp = cfg.factors[f].get("protocol")
        cells = []
        for r in rows_f:
            if not keep(r):
                continue
            bp = r.get("baseline_protocol") or cfg.base_protocol
            cells.append((r["pair"], r["suite"], fp, bp))
            protos.update({fp, bp})
        fcells[f] = cells
    for pair in pairs:
        for suite in suites:
            for pr in protos:
                a = cx.arrays(pr, pair, suite)
                if a is not None:
                    arrays[(pair, suite, pr)] = a
    return S1Input(pairs, suites, arrays, rerun, fcells, DELTA)


def s1_s2(cx: Ctx, flips: list[dict], reruns: list[tuple[str, str]], reps: int, seed: int, out: dict, notes: list[str]) -> None:
    cfg = cx.cfg
    gen = [f for f in GENERATION_FACTORS if f in cfg.factors and cfg.factors[f].get("kind", "run") == "run"]
    inp = build_s1_input(cx, flips, reruns[0], gen)
    out["s1_rerun_rates"] = [rerun_rate(build_s1_input(cx, flips, rr, []), f"{rr[0]} vs {rr[1]}") for rr in reruns]
    if not inp.arrays:
        notes.append("S1: no arrays (no runs found)")
        return
    boot = hier_bootstrap(inp, reps, seed)
    out["s1_factors"] = summarize(inp, boot)
    boot_x = hier_bootstrap(inp, reps, seed, exclude_pairs=(SEPARATE_PAIR,))
    out["s1_factors_excl_qwen25_qwen3"] = summarize(inp, boot_x)
    # S1.4 expected share of decisions with >=1 noise flip next to the observed value
    p_i, k_i, ids = [], [], []
    for pair in inp.pairs:
        for suite in inp.suites:
            if not inp.has_rerun(pair, suite):
                continue
            k = sum(1 for f in gen for c in inp.usable_cells(f) if c[0] == pair and c[1] == suite)
            p_i.append(per_decision_flip_prob(inp.arrays[(pair, suite, inp.rerun[0])], inp.arrays[(pair, suite, inp.rerun[1])], reps, seed))
            k_i.append(k)
            ids.append(f"{pair}/{suite}")
    out["s1_per_decision"] = [{"decision": d, "p_rerun_flip": p, "k_generation_factors": k, "p_at_least_one_noise_flip": 1 - (1 - p) ** k}
                              for d, p, k in zip(ids, p_i, k_i)]
    flipped = {(r["pair"], r["suite"]) for r in flips if r["flipped"] and r["factor"] in gen
               and _variant_filters(cfg, r["factor"], [r])["main"](r)}
    decided = {(r["pair"], r["suite"]) for r in flips if r["factor"] in gen}
    out["s1_headline"] = [{"expected_share_with_noise_flip": expected_noise_share(p_i, k_i), "n_decisions_with_rerun": len(p_i),
                           "observed_share_with_generation_flip_all_decisions": (len(flipped) / len(decided)) if decided else float("nan"),
                           "n_decisions_observed": len(decided),
                           "observed_share_on_rerun_decisions": (sum(1 for d in ids if tuple(d.split("/")) in flipped) / len(ids)) if ids else float("nan")}]
    # S2 on observed labels: factor flips and rerun flips
    ob = observed(inp)
    rr_rows = []
    for (pair, suite), fl in ob["rerun"]["cells"].items():
        a = NAME[int(point_code(np.array([inp.arrays[(pair, suite, inp.rerun[0])].diff()]), DELTA)[0])]
        b = NAME[int(point_code(np.array([inp.arrays[(pair, suite, inp.rerun[1])].diff()]), DELTA)[0])]
        rr_rows.append({"pair": pair, "suite": suite, "label_main": a, "label_rerun": b})
    out["s2_rerun_flips"] = split_rows(rr_rows, "label_main", "label_rerun", (), SEPARATE_PAIR) if rr_rows else []
    fac_rows = [r for r in flips if r["factor"] in gen and _variant_filters(cfg, r["factor"], [r])["main"](r)]
    out["s2_factor_flips"] = split_rows(fac_rows, "d_label", "factor_label", ("factor",), SEPARATE_PAIR)
    out["_s1_input"] = inp


def s3(cx: Ctx, protos: list[str], reps: int, seed: int, out: dict) -> dict[tuple, str]:
    """Class of every (protocol, pair, suite) cell with rows. Returns {(proto, pair, suite): class}."""
    classes: dict[tuple, str] = {}
    rows_out = []
    for pr in protos:
        for (pair, suite), row in cx.rows(pr).items():
            a = cx.arrays(pr, pair, suite)
            if a is None:
                continue
            lo90, hi90 = interval(a, 0.90, reps, seed)
            c = classify(row["stress_diff"], lo90, hi90, row["label_ci"])
            classes[(pr, pair, suite)] = c
            rows_out.append({"protocol": pr, "pair": pair, "suite": suite, "stress_diff": row["stress_diff"],
                             "ci95_lo": row["ci_lo"], "ci95_hi": row["ci_hi"], "ci90_lo": lo90, "ci90_hi": hi90,
                             "label_point": row["label_point"], "label_ci": row["label_ci"], "class4": c})
    out["s3_classes"] = rows_out
    shares = []
    for pr in protos:
        cl = [c for (p, _, _), c in classes.items() if p == pr]
        if cl:
            shares.append({"protocol": pr, "n_decisions": len(cl), **class_share(cl)})
    out["s3_shares"] = shares
    return classes


def s3_cluster(cx: Ctx, protos: list[str], classes: dict, reps: int, seed: int, out: dict) -> None:
    """DESCRIPTIVE sensitivity row (advisor decision 2026-11-08): the S3 four-class verdict on synthetic when tasks that
    share a baseline prompt form one resampling cluster (the plan's cluster bootstrap). Same rules as S3 with the
    cluster bootstrap for both intervals: harmful/beneficial = the CI-gate rule on the 95% cluster interval, neutral =
    90% cluster interval inside +/-delta. Gates and S3 itself are unchanged."""
    from upgradecanary.gates import ci_gate

    rows = []
    for pr in protos:
        for (pair, suite), row in cx.rows(pr).items():
            if suite != "synthetic":
                continue
            a = cx.arrays(pr, pair, suite)
            old, _ = cx.runs(pr, pair, suite)
            if a is None or old is None:
                continue
            ca = cluster_arrays(a, baseline_clusters(old))
            lo95, hi95 = interval(ca, 0.95, reps, seed)
            lo90, hi90 = interval(ca, 0.90, reps, seed)
            c = classify(row["stress_diff"], lo90, hi90, ci_gate(row["stress_diff"], lo95, hi95))
            rows.append({"protocol": pr, "pair": pair, "suite": suite, "n_tasks": a.n_tasks, "n_clusters": ca.n_tasks,
                         "stress_diff": row["stress_diff"], "task_ci95_lo": row["ci_lo"], "task_ci95_hi": row["ci_hi"],
                         "cluster_ci95_lo": lo95, "cluster_ci95_hi": hi95, "cluster_ci90_lo": lo90, "cluster_ci90_hi": hi90,
                         "class4_task": classes.get((pr, pair, suite)), "class4_cluster": c})
    out["s3_cluster_synthetic"] = rows
    summ = []
    for pr in protos:
        rs = [r for r in rows if r["protocol"] == pr]
        if rs:
            summ.append({"protocol": pr, "suite": "synthetic", "n_decisions": len(rs),
                         "n_same_class": sum(r["class4_task"] == r["class4_cluster"] for r in rs),
                         **{f"task_{k}": sum(r["class4_task"] == k for r in rs) for k in CLASSES},
                         **{f"cluster_{k}": sum(r["class4_cluster"] == k for r in rs) for k in CLASSES}})
    out["s3_cluster_synthetic_summary"] = summ


def s3_flips(cx: Ctx, classes: dict, flips: list[dict], reruns: list[tuple[str, str]], gen: list[str], out: dict) -> None:
    """S1/S2 repeated with the four-class gate (point rates and types; the hierarchical interval for e_F is not
    recomputed, see the questions in the report)."""
    cfg = cx.cfg
    rr_rows = []
    for main, rerun in reruns:
        for (pr, pair, suite), c in classes.items():
            if pr == main and (rerun, pair, suite) in classes:
                rr_rows.append({"arm": f"{main} vs {rerun}", "pair": pair, "suite": suite, "a": c, "b": classes[(rerun, pair, suite)]})
    out["s3_rerun_flips"] = split_rows(rr_rows, "a", "b", ("arm",), SEPARATE_PAIR) if rr_rows else []
    fac = []
    for r in flips:
        if r["factor"] not in gen or not _variant_filters(cfg, r["factor"], [r])["main"](r):
            continue
        fp = cfg.factors[r["factor"]].get("protocol")
        bp = r.get("baseline_protocol") or cfg.base_protocol
        ka, kb = (bp, r["pair"], r["suite"]), (fp, r["pair"], r["suite"])
        if ka in classes and kb in classes:
            fac.append({"factor": r["factor"], "pair": r["pair"], "suite": r["suite"], "a": classes[ka], "b": classes[kb]})
    out["s3_factor_flips"] = split_rows(fac, "a", "b", ("factor",), SEPARATE_PAIR) if fac else []


# ---------------------------------------------------------------------------------------------- S4
def s4(cx: Ctx, flips: list[dict], out: dict) -> None:
    cfg = cx.cfg
    h1 = list(cfg.groups.get("h1", []))

    def main_rows(factors):
        sel = []
        for f in factors:
            rows_f = [r for r in flips if r["factor"] == f]
            if rows_f:
                keep = _variant_filters(cfg, f, rows_f)["main"]
                sel += [r for r in rows_f if keep(r)]
        return sel

    out["s4_classes"] = [{"factor": f, "class": FACTOR_CLASS.get(f, "not classified")} for f in cfg.factors]
    allf = [f for f in cfg.factors]
    out["s4_headline"] = [
        {"set": "reasonable only (headline)", **headline_flip_rate(main_rows(reasonable_set(allf)), reasonable_set(allf))},
        {"set": "all factors incl. misconfiguration/compound", **headline_flip_rate(main_rows(allf), allf)},
        {"set": "P1 set (config group h1)", **headline_flip_rate(main_rows(h1), h1)},
    ]


# ---------------------------------------------------------------------------------------------- S5
def s5(cx: Ctx, flips: list[dict], protos: list[str], gen: list[str], out: dict) -> None:
    cfg = cx.cfg
    cache: dict[tuple, dict] = {}

    def per_cond(proto, model, suite):
        k = (proto, model, suite)
        if k not in cache:
            try:
                run = cx.an.run_for(proto, model, suite)
            except MissingRun:
                run = None
            cache[k] = shares_from_records(read_records(run)) if run is not None else None
        return cache[k]

    rows = []
    for pr in protos:
        for m in cfg.models:
            for suite in cfg.suites:
                pc = per_cond(pr, m, suite)
                if pc is None:
                    continue
                for cond, v in pc.items():
                    rows.append({"protocol": pr, "model": m, "suite": suite, "condition": cond, **v})
    out["s5_shares"] = rows
    ch = []
    for r in flips:
        if r["factor"] not in gen or not _variant_filters(cfg, r["factor"], [r])["main"](r):
            continue
        p = cx.pairs[r["pair"]]
        fp = cfg.factors[r["factor"]].get("protocol")
        bp = r.get("baseline_protocol") or cfg.base_protocol
        parts = [per_cond(bp, p["old"], r["suite"]), per_cond(bp, p["new"], r["suite"]),
                 per_cond(fp, p["old"], r["suite"]), per_cond(fp, p["new"], r["suite"])]
        if any(x is None for x in parts):
            continue
        s = [stress_share(x) for x in parts]
        d = flip_changes(s[0], s[1], s[2], s[3])
        ch.append({"factor": r["factor"], "pair": r["pair"], "suite": r["suite"], "flipped": r["flipped"],
                   "d_label": r["d_label"], "factor_label": r["factor_label"], **{f"d_share_{k}": v for k, v in d.items()}})
    out["s5_flip_changes"] = ch


# ---------------------------------------------------------------------------------------------- S6
def baseline_clusters(run) -> dict[str, str]:
    """task -> baseline prompt hash, read from the run's raw outputs (trial 0 of the baseline condition)."""
    out: dict[str, str] = {}
    for part in run.parts:
        with open(Path(part) / "raw_outputs.jsonl", encoding="utf-8") as fh:
            for line in fh:
                if '"baseline"' not in line:
                    continue
                r = json.loads(line)
                if r.get("condition") == "baseline" and int(r.get("trial_index", 0)) == 0:
                    out.setdefault(r["task_id"], r.get("prompt_sha256"))
    return out


def s6(cx: Ctx, protocol: str, n_trials: int, w3_counts: dict[str, int], out: dict, delta: float = DELTA) -> None:
    cfg = cx.cfg
    by_suite: dict[str, list[np.ndarray]] = {}
    clus: dict[str, list[np.ndarray]] = {}
    sd_rows = []
    for pair in cx.pairs:
        for suite in cfg.suites:
            old, new = cx.runs(protocol, pair, suite)
            if old is None or new is None:
                continue
            tl, trials, y = trial_matrix(old, new, cfg.stress, cx.tasks(pair, suite))
            y = y - np.nanmean(y)                      # centre each decision: pooled variances are within-decision
            by_suite.setdefault(suite, []).append(y)
            tm = np.nanmean(y, axis=1)
            sd_rows.append({"pair": pair, "suite": suite, "n_tasks": len(tl), "sd_task_mean_diff": float(np.nanstd(tm, ddof=1)),
                            "mde_80": mde(float(np.nanstd(tm, ddof=1)), len(tl))})
            if suite == "synthetic":
                cl = baseline_clusters(old)
                keys = sorted(set(cl.values()))
                if keys:
                    idx = {k: i for i, k in enumerate(keys)}
                    cy = np.full((len(keys), y.shape[1]), np.nan)
                    for j in range(y.shape[1]):
                        for k, i in idx.items():
                            members = [ti for ti, t in enumerate(tl) if cl.get(t) == k]
                            vals = y[members, j]
                            vals = vals[np.isfinite(vals)]
                            if len(vals):
                                cy[i, j] = vals.mean()
                    clus.setdefault(suite, []).append(cy)
    out["s6_decisions"] = sd_rows
    comp_rows, proj_rows = [], []
    for suite, ys in by_suite.items():
        y = np.vstack(ys)
        n_task = ys[0].shape[0]
        comp = variance_components(y, greedy_col=0)
        comp_rows.append({"suite": suite, "unit": "task", "n_units_pooled_rows": y.shape[0], **comp})
        scen = [{"name": f"Phase 1 layout ({y.shape[1]} trials), {n_task} tasks", "n_trials": y.shape[1], "n_units": n_task},
                {"name": f"{n_trials} trials, {n_task} tasks", "n_trials": n_trials, "n_units": n_task}]
        if suite in w3_counts:
            scen.append({"name": f"{n_trials} trials, W3 task count {w3_counts[suite]}", "n_trials": n_trials, "n_units": w3_counts[suite]})
        proj_rows += project_table(comp, suite, scen, delta)
        if suite in clus:
            cy = np.vstack(clus[suite])
            ccomp = variance_components(cy, greedy_col=0)
            comp_rows.append({"suite": suite + " (clusters = tasks sharing a baseline prompt)", "unit": "cluster",
                              "n_units_pooled_rows": cy.shape[0], **ccomp})
            nclu = clus[suite][0].shape[0]
            proj_rows += project_table(ccomp, suite + " clusters", [
                {"name": f"Phase 1 layout ({cy.shape[1]} trials), {nclu} clusters", "n_trials": cy.shape[1], "n_units": nclu},
                {"name": f"{n_trials} trials, {nclu} clusters", "n_trials": n_trials, "n_units": nclu}], delta)
    out["s6_components"] = comp_rows
    out["s6_projection"] = proj_rows


# ---------------------------------------------------------------------------------------------- S7, S8
def s7(cx: Ctx, protos: list[str], classes: dict, out: dict) -> None:
    rows = []
    for pr in protos:
        for (pair, suite), row in cx.rows(pr).items():
            old, new = cx.runs(pr, pair, suite)
            if old is None or new is None:
                continue
            res = mcnemar_decision(item_outcomes(old, new, cx.cfg.stress), row["stress_diff"])
            rows.append({"protocol": pr, "pair": pair, "suite": suite, "stress_diff": row["stress_diff"],
                         "label_point": row["label_point"], "label_ci": row["label_ci"], "class4": classes.get((pr, pair, suite)), **res})
    out["s7_decisions"] = rows
    ag = []
    for pr in protos:
        rs = [r for r in rows if r["protocol"] == pr]
        if not rs:
            continue
        n = len(rs)
        ag.append({"protocol": pr, "n_decisions": n,
                   "agree_with_point_gate": sum(r["label"] == r["label_point"] for r in rs) / n,
                   "agree_with_ci_gate": sum(r["label"] == r["label_ci"] for r in rs) / n,
                   "agree_with_class4_neutral_and_inconclusive_merged": (
                       sum(r["label"] == ("neutral" if r["class4"] == "inconclusive" else r["class4"]) for r in rs if r["class4"])
                       / max(1, sum(1 for r in rs if r["class4"]))),
                   "share_harmful": sum(r["label"] == "harmful" for r in rs) / n, "share_beneficial": sum(r["label"] == "beneficial" for r in rs) / n})
    out["s7_agreement"] = ag


def s8(cx: Ctx, protos: list[str], out: dict) -> None:
    ref_rows = cx.rows("F5") if "F5" in cx.cfg.protocols else {}
    reference = {(p, s): r["label_point"] for (p, s), r in ref_rows.items() if p in SMALL_PAIRS}
    others = {}
    for pr in protos:
        if pr == "F5":
            continue
        labels = {k: r["label_point"] for k, r in cx.rows(pr).items() if k[0] in SMALL_PAIRS}
        if labels:
            others[pr] = labels
    out["s8_reference"] = [{"n_reference_decisions": len(reference)}]
    out["s8_agreement"] = agreement(reference, others)


# ---------------------------------------------------------------------------------------------- driver
def run_addendum(cfg, out_dir: Path, reruns: list[tuple[str, str]], reps: int = BOOT_REPS, seed: int = BOOT_SEED,
                 sections: tuple[str, ...] = ("s1", "s3", "s4", "s5", "s6", "s7", "s8", "s9"), n_trials_phase2: int = 10,
                 w3_counts: dict[str, int] | None = None, notes: list[str] | None = None) -> dict:
    out_dir = assert_safe_output_dir_p2(out_dir)
    t0 = time.time()
    an = Phase2Analysis(cfg, with_ci=True, allow_missing=True)
    cx = Ctx(an)
    notes = list(notes or [])
    out: dict[str, Any] = {}
    flips = an.flip_table()
    gen = [f for f in GENERATION_FACTORS if f in cfg.factors and cfg.factors[f].get("kind", "run") == "run"]
    protos = [p for p in decision_protocols(cfg) if p in cfg.protocols]
    base = cfg.base_protocol
    classes: dict[tuple, str] = {}
    if "s1" in sections and not reruns:
        notes.append("S1 skipped: no rerun arm given (--rerun MAIN:RERUN)")
    elif "s1" in sections:
        s1_s2(cx, flips, reruns, reps, seed, out, notes)
    if "s3" in sections:
        p3 = sorted({base, *(rr[0] for rr in reruns), *(rr[1] for rr in reruns), *(cfg.factors[f].get("protocol") for f in gen),
                     *(r.get("baseline_protocol") or base for r in flips if r["factor"] in gen)} - {None})
        classes = s3(cx, p3, reps, seed, out)
        s3_flips(cx, classes, flips, reruns, gen, out)
        s3_cluster(cx, p3, classes, reps, seed, out)
    if "s4" in sections:
        s4(cx, flips, out)
    if "s5" in sections:
        p5 = sorted({base, *(rr[1] for rr in reruns), *(cfg.factors[f].get("protocol") for f in gen)} - {None})
        s5(cx, flips, p5, gen, out)
    if "s6" in sections:
        s6(cx, base, n_trials_phase2, w3_counts or {}, out)
    if "s7" in sections:
        s7(cx, [p for p in {base, *(rr[0] for rr in reruns)} if p in cfg.protocols], classes, out)
    if "s8" in sections:
        s8(cx, protos, out)
    if "s9" in sections:
        out["s9_interaction"], out["s9_skipped"] = run_s9(cx, seed=seed)
    out.pop("_s1_input", None)
    out["_meta"] = [{"mode": cfg.mode, "reps": reps, "seed": seed, "reruns": [list(r) for r in reruns], "seconds": round(time.time() - t0, 1),
                     "sections": ",".join(sections), "notes": " | ".join(notes)}]
    for name, rows in out.items():
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            write_csv(out_dir / f"{name}.csv", rows)
    (out_dir / "meta.json").write_text(json.dumps(out["_meta"][0], indent=1), encoding="utf-8")
    return out


def parse_rerun(s: str) -> tuple[str, str]:
    a, b = s.split(":")
    return a, b


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rerun", action="append", default=[], help="MAIN:RERUN protocol pair, e.g. D:D_AA2 (first one drives S1.2)")
    ap.add_argument("--reps", type=int, default=BOOT_REPS)
    ap.add_argument("--seed", type=int, default=BOOT_SEED)
    ap.add_argument("--sections", default="s1,s3,s4,s5,s6,s7,s8,s9")
    ap.add_argument("--note", action="append", default=[])
    args = ap.parse_args(argv)
    cfg = load_phase2_config(args.config)
    reruns = [parse_rerun(r) for r in args.rerun]
    run_addendum(cfg, Path(args.out), reruns, args.reps, args.seed, tuple(args.sections.split(",")),
                 w3_counts={"bfcl_simple": 191, "bfcl_multiple": 109}, notes=args.note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
