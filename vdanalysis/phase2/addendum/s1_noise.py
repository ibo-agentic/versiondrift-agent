"""S1: noise floor. Factor flips versus rerun flips.

Rerun flip (decision i): the point-gate label of the main arm differs from the label of the rerun arm (same run
seed, same prompts, other trial seeds). Rerun flip rate r = share of decisions with a rerun flip. Factor flip rate
f_F = share of the decisions where factor F was run whose label differs from the factor's baseline label. Excess
e_F = f_F - r on the same decisions. Intervals come from a hierarchical bootstrap (pairs, then tasks within each
pair-suite; all trials and conditions of a task stay together); f_F and r are recomputed in every replicate.

Everything here uses per-task arrays (``data.TaskArrays``), so the whole bootstrap is a few matrix products.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..stats2 import clopper_pearson
from . import BOOT_REPS, BOOT_SEED, DELTA
from .data import TaskArrays, boot_diff, draw_counts, point_code


@dataclass
class S1Input:
    pairs: list[str]
    suites: list[str]
    arrays: dict[tuple[str, str, str], TaskArrays]                 # (pair, suite, protocol) -> arrays
    rerun: tuple[str, str]                                         # (main-arm protocol, rerun-arm protocol)
    factor_cells: dict[str, list[tuple[str, str, str, str]]]       # factor -> [(pair, suite, factor protocol, baseline protocol)]
    delta: float = DELTA
    notes: list[str] = field(default_factory=list)

    def has_rerun(self, pair: str, suite: str) -> bool:
        return all((pair, suite, p) in self.arrays for p in self.rerun)

    def usable_cells(self, factor: str) -> list[tuple[str, str, str, str]]:
        """Cells where the factor was run and a rerun comparison exists (the decisions e_F is computed on)."""
        return [c for c in self.factor_cells[factor]
                if self.has_rerun(c[0], c[1]) and (c[0], c[1], c[2]) in self.arrays and (c[0], c[1], c[3]) in self.arrays]


def holm(pvals: dict[str, float]) -> dict[str, float]:
    """Holm step-down adjusted p-values."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out, running = {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def observed(inp: S1Input, pairs: list[str] | None = None) -> dict:
    """Point estimates on the observed labels (no resampling). ``pairs`` limits them to those upgrade pairs
    (default: all), so that a bootstrap that leaves a pair out is reported next to point estimates that leave it out too."""
    keep = set(inp.pairs if pairs is None else pairs)
    one = {}

    def lab(pair, suite, proto):
        a = inp.arrays[(pair, suite, proto)]
        return int(point_code(np.array([a.diff()]), inp.delta)[0])

    rerun_cells = [(p, s) for p in inp.pairs if p in keep for s in inp.suites if inp.has_rerun(p, s)]
    rerun_flip = {(p, s): lab(p, s, inp.rerun[0]) != lab(p, s, inp.rerun[1]) for p, s in rerun_cells}
    one["rerun"] = {"n": len(rerun_cells), "k": sum(rerun_flip.values()), "cells": rerun_flip}
    fac = {}
    for f in inp.factor_cells:
        cells = [c for c in inp.usable_cells(f) if c[0] in keep]
        fl = [lab(p, s, fp) != lab(p, s, bp) for p, s, fp, bp in cells]
        rr = [rerun_flip[(p, s)] for p, s, _, _ in cells]
        fac[f] = {"n": len(cells), "k_factor": sum(fl), "k_rerun": sum(rr)}
    one["factors"] = fac
    return one


def hier_bootstrap(inp: S1Input, reps: int = BOOT_REPS, seed: int = BOOT_SEED, exclude_pairs: tuple[str, ...] = ()) -> dict:
    """Replicates of f_F, r (on F's decisions) and e_F for every generation factor, plus r over all decisions."""
    pairs = [p for p in inp.pairs if p not in exclude_pairs]
    P = len(pairs)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, P, size=(reps, P))                 # which pair fills each of the P slots of a replicate
    facs = list(inp.factor_cells)
    f_num = {f: np.zeros(reps) for f in facs}
    f_den = {f: np.zeros(reps) for f in facs}
    r_num = {f: np.zeros(reps) for f in facs}
    all_num, all_den = np.zeros(reps), np.zeros(reps)
    for pi, pair in enumerate(pairs):
        b_idx = np.nonzero(draws == pi)[0]                     # replicate of every slot that drew this pair
        K = len(b_idx)
        if K == 0:
            continue
        for suite in inp.suites:
            T = next((a.n_tasks for (p, s, _), a in inp.arrays.items() if p == pair and s == suite), None)
            if T is None:
                continue
            M = draw_counts(rng, T, K)
            cache: dict[str, np.ndarray] = {}

            def code(proto):
                if proto not in cache:
                    cache[proto] = point_code(boot_diff(M, inp.arrays[(pair, suite, proto)]), inp.delta)
                return cache[proto]

            has_r = inp.has_rerun(pair, suite)
            rflip = (code(inp.rerun[0]) != code(inp.rerun[1])) if has_r else None
            if has_r:
                np.add.at(all_num, b_idx, rflip)
                np.add.at(all_den, b_idx, 1)
            for f in facs:
                for p, s, fp, bp in inp.factor_cells[f]:
                    if p != pair or s != suite or not has_r:
                        continue
                    if (pair, suite, fp) not in inp.arrays or (pair, suite, bp) not in inp.arrays:
                        continue
                    np.add.at(f_num[f], b_idx, code(fp) != code(bp))
                    np.add.at(f_den[f], b_idx, 1)
                    np.add.at(r_num[f], b_idx, rflip)
    out = {"reps": reps, "seed": seed, "pairs": pairs, "factors": {}}
    with np.errstate(invalid="ignore", divide="ignore"):
        out["r_all"] = np.where(all_den > 0, all_num / all_den, np.nan)
        for f in facs:
            fr = np.where(f_den[f] > 0, f_num[f] / f_den[f], np.nan)
            rr = np.where(f_den[f] > 0, r_num[f] / f_den[f], np.nan)
            out["factors"][f] = {"f": fr, "r": rr, "e": fr - rr}
    return out


def pct_ci(x: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan"), float("nan")
    a = (1 - level) / 2
    return float(np.quantile(x, a)), float(np.quantile(x, 1 - a))


def summarize(inp: S1Input, boot: dict) -> list[dict]:
    """One row per generation factor: f, r, e, bootstrap CI of e, one-sided p (e > 0), Holm-adjusted p."""
    obs = observed(inp, boot.get("pairs"))                      # the pairs the bootstrap actually resampled
    rows, pvals = [], {}
    for f, ob in obs["factors"].items():
        e_rep = boot["factors"][f]["e"]
        finite = e_rep[np.isfinite(e_rep)]
        p = (1 + float((finite <= 0).sum())) / (len(finite) + 1) if len(finite) else float("nan")
        n = ob["n"]
        fo = ob["k_factor"] / n if n else float("nan")
        ro = ob["k_rerun"] / n if n else float("nan")
        lo, hi = pct_ci(e_rep)
        rows.append({"factor": f, "n_decisions": n, "k_factor_flips": ob["k_factor"], "k_rerun_flips": ob["k_rerun"],
                     "f_F": fo, "r_on_same_decisions": ro, "e_F": fo - ro if n else float("nan"),
                     "e_F_ci95_lo": lo, "e_F_ci95_hi": hi, "p_one_sided_e_gt_0": p})
        if np.isfinite(p):
            pvals[f] = p
    adj = holm(pvals)
    for r in rows:
        r["p_holm"] = adj.get(r["factor"], float("nan"))
    return rows


def rerun_rate(inp: S1Input, label: str) -> dict:
    """r with an exact Clopper-Pearson 95% interval (S1.1)."""
    ob = observed(inp)["rerun"]
    n, k = ob["n"], ob["k"]
    lo, hi = clopper_pearson(k, n) if n else (float("nan"), float("nan"))
    return {"arm": label, "n_decisions": n, "n_rerun_flips": k, "rate": (k / n) if n else float("nan"),
            "cp95_lo": lo, "cp95_hi": hi}


def per_decision_flip_prob(a_main: TaskArrays, a_rerun: TaskArrays, reps: int = BOOT_REPS, seed: int = BOOT_SEED,
                           delta: float = DELTA) -> float:
    """S1.4: p_i = share of task-resamples in which the main arm's label differs from the rerun arm's label
    (labels recomputed on the same resampled tasks)."""
    rng = np.random.default_rng(seed)
    T = a_main.n_tasks
    M = draw_counts(rng, T, reps)
    return float((point_code(boot_diff(M, a_main), delta) != point_code(boot_diff(M, a_rerun), delta)).mean())


def expected_noise_share(p: list[float], k: list[int]) -> float:
    """S1.4: mean over decisions of 1 - (1 - p_i)^k_i."""
    if not p:
        return float("nan")
    return float(np.mean([1.0 - (1.0 - pi) ** ki for pi, ki in zip(p, k)]))
