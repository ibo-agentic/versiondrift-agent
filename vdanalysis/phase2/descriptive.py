"""Descriptive outputs of PLAN_PHASE2.md section 4 (no thresholds, no verdicts).

* hardware noise: D on the laptop vs D on Kaggle, per model and per pair;
* size of F5's per-model score shift (same-hardware) next to the A/A noise;
* flips at 10 trials that Phase 1 did not see;
* W6 agreement numbers (kappa).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..stats import compare
from .analysis import Phase2Analysis, ViewSpec
from .stats2 import cohen_kappa


def _quantile(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    return s[max(0, min(len(s) - 1, round(q * (len(s) - 1))))]


def _paired(an: Phase2Analysis, old, new, conds) -> dict[str, Any]:
    c = an.cfg
    cmp = compare(old, new, conds, c.threshold, c.reps, c.seed, with_ci=False)
    return {"n": 0, "diff": None} if cmp is None else {"n": cmp.n_records, "diff": cmp.diff}


# ---- hardware noise ------------------------------------------------------------
def hw_noise_runs(an: Phase2Analysis) -> list[dict[str, Any]]:
    """Per model x suite: the same D configuration on the laptop and on Kaggle.
    ``*_diff`` = Kaggle minus laptop, paired on identical records."""
    spec = an.cfg.same_hardware_for("F5")
    if not spec:
        return []
    c = an.cfg
    greedy = an.with_view(ViewSpec(trials="greedy"))
    out = []
    for model in sorted(spec["models"]):
        for suite in c.suites:
            lap = an.run_for(c.base_protocol, model, suite)
            kag = an.run_for(spec["baseline"], model, suite)
            if lap is None or kag is None:
                continue
            same_prompts = None
            if getattr(lap, "prompts", None) and getattr(kag, "prompts", None):
                common = set(lap.prompts) & set(kag.prompts)
                same_prompts = all(lap.prompts[k] == kag.prompts[k] for k in common)
            lg, kg = greedy.run_for(c.base_protocol, model, suite), greedy.run_for(spec["baseline"], model, suite)
            st = _paired(an, lap, kag, c.stress)
            bl = _paired(an, lap, kag, [c.baseline_condition])
            gr = _paired(greedy, lg, kg, c.stress)
            out.append({"model": model, "suite": suite, "n_stress_records": st["n"],
                        "stress_diff": st["diff"], "baseline_diff": bl["diff"], "greedy_stress_diff": gr["diff"],
                        "prompts_identical": same_prompts})
    return out


def hw_noise_pairs(an: Phase2Analysis) -> list[dict[str, Any]]:
    """Per adjacent pair among the Kaggle models: the pair's stress diff on
    Kaggle minus the same pair's stress diff on the laptop, and whether the
    point label agrees."""
    spec = an.cfg.same_hardware_for("F5")
    if not spec:
        return []
    lap_rows = an.rows(an.cfg.base_protocol)
    kag_rows = an.rows(spec["baseline"])
    out = []
    for key, k in sorted(kag_rows.items()):
        lp = lap_rows.get(key)
        if lp is None or not (k["old"] in spec["models"] and k["new"] in spec["models"]):
            continue
        out.append({"pair": key[0], "suite": key[1], "laptop_diff": lp["stress_diff"], "kaggle_diff": k["stress_diff"],
                    "hardware_diff": k["stress_diff"] - lp["stress_diff"], "laptop_label": lp["label_point"],
                    "kaggle_label": k["label_point"], "labels_agree": lp["label_point"] == k["label_point"]})
    return out


# ---- F5 shift vs A/A noise -------------------------------------------------------
def f5_shift_vs_aa(an: Phase2Analysis, aa_rows: list[dict], aa_control: str) -> list[dict[str, Any]]:
    """Per model x suite: F5's paired stress-score shift against the baseline on
    the same hardware, next to the A/A noise of the same gate family (largest
    and 95th-percentile |stress diff| over the A/A control's decisions). Any
    number of A/A decisions is fine; with none, the bounds are empty."""
    c = an.cfg
    f = c.factors.get("F5")
    if not f:
        return []
    noise = [abs(r["stress_diff"]) for r in aa_rows if r["control"] == aa_control]
    bound_max, bound_p95 = (max(noise) if noise else None), _quantile(noise, 0.95)
    sh = c.same_hardware_for(f["protocol"])
    out = []
    for model in c.models:
        for suite in c.suites:
            if not an.store.applies(f["protocol"], model):
                continue
            base_proto = sh["baseline"] if sh and model in sh["models"] else c.base_protocol
            base, run = an.run_for(base_proto, model, suite), an.run_for(f["protocol"], model, suite)
            if base is None or run is None:
                continue
            r = _paired(an, base, run, c.stress)
            if r["diff"] is None:
                continue
            out.append({"model": model, "suite": suite, "baseline_protocol": base_proto, "n_stress_records": r["n"],
                        "f5_shift": r["diff"], "aa_control": aa_control, "n_aa_decisions": len(noise),
                        "aa_max_abs_diff": bound_max, "aa_p95_abs_diff": bound_p95,
                        "exceeds_aa_max": None if bound_max is None else abs(r["diff"]) > bound_max,
                        "exceeds_aa_p95": None if bound_p95 is None else abs(r["diff"]) > bound_p95})
    return out


# ---- R_F5 against the Kaggle R baseline ---------------------------------------------
def r_f5_same_hardware(an: Phase2Analysis) -> list[dict[str, Any]]:
    """Pair-level R_F5 effect against the same-hardware R baseline (CI gate)."""
    c = an.cfg
    robust = c.raw.get("robust") or {}
    proto = (robust.get("nuisance") or {}).get("F5")
    if not proto or not robust.get("base"):
        return []
    out = []
    for key, frow in an.rows(proto).items():
        pair = next(x for x in c.pairs if c.pair_name(x) == key[0])
        bproto = an.baseline_protocol_for(proto, pair, default=robust["base"])
        b = an.rows(bproto).get(key)
        if b is None:
            continue
        out.append({"pair": key[0], "suite": key[1], "baseline_protocol": bproto, "baseline_label_ci": b["label_ci"],
                    "r_f5_label_ci": frow["label_ci"], "flipped": b["label_ci"] != frow["label_ci"],
                    "baseline_diff": b["stress_diff"], "r_f5_diff": frow["stress_diff"]})
    return out


# ---- new flips ------------------------------------------------------------------------
def new_flips(flips: list[dict], ref_rows: list[dict]) -> list[dict[str, Any]]:
    """Flips at 10 trials whose (factor, pair, suite) did not flip in Phase 1."""
    seen = {(r["factor"], r["pair"], r["suite"]) for r in ref_rows
            if str(r["flipped"]).lower() == "true"}
    return [r for r in flips if r["flipped"] and (r["factor"], r["pair"], r["suite"]) not in seen]


# ---- W6 agreement -----------------------------------------------------------------------
def read_labels(path: str | Path) -> dict[str, dict[str, str]]:
    """CSV with columns record_id, labeler, label -> {labeler: {record_id: label}}."""
    out: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            lab = out.setdefault(row["labeler"], {})
            if row["record_id"] in lab:
                raise ValueError(f"{row['labeler']} labeled {row['record_id']} twice")
            lab[row["record_id"]] = row["label"]
    return out


def agreement_rows(labels: dict[str, dict[str, str]], rule_name: str = "rule") -> list[dict[str, Any]]:
    """Cohen's kappa for human-human and each human against the rule, over the
    records both raters labeled. A missing second labeler simply yields no
    human-human row."""
    names = sorted(labels)
    out = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ids = sorted(set(labels[a]) & set(labels[b]))
            if not ids:
                continue
            la, lb = [labels[a][r] for r in ids], [labels[b][r] for r in ids]
            out.append({"rater_a": a, "rater_b": b, "n": len(ids),
                        "percent_agree": sum(x == y for x, y in zip(la, lb)) / len(ids),
                        "kappa": cohen_kappa(la, lb),
                        "kind": "human_vs_rule" if rule_name in (a, b) else "human_vs_human"})
    return out
