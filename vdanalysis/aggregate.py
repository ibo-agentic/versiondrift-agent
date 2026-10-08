"""Flip rates, disagreement rates, and the H1-H5 tests (PLAN.md sections 8-9).

Reporting conventions fixed in DEVIATIONS.md (all applied by the ``main``
variant; the ``all`` variant is always reported next to it):

* F6: main number uses only pairs where a model's sampling actually
  changed (factor config ``main_filter: f6_sampling_changed``).
* F4 / R: any decision where a Qwen3 run used the generic-JSON grammar
  carries the label "grammar+thinking_blocked" (two things changed, not
  one); those cells are excluded from the main F4 number and reported as
  their own ``confounded_only`` variant.
"""

from __future__ import annotations

import statistics
from typing import Any

from .config import Config
from .engine import Analysis

SIZE_SUBSETS = {
    "all_pairs": lambda r: True,
    "size_preserving": lambda r: not r["size_changing"],
    "size_changing": lambda r: r["size_changing"],
}


def _variant_filters(cfg: Config, factor: str, flips: list[dict]):
    main_filter = cfg.factors[factor].get("main_filter")

    def main(r):
        return not r["confounding"] and (not main_filter or bool(r[main_filter]))

    variants = {"main": main, "all": lambda r: True}
    if any(r["confounding"] for r in flips):
        variants["confounded_only"] = lambda r: bool(r["confounding"])
    return variants


def _rate(rows: list[dict]) -> dict[str, Any]:
    n = len(rows)
    k = sum(1 for r in rows if r["flipped"])
    return {
        "n_decisions": n,
        "n_flips": k,
        "flip_rate": (k / n) if n else None,
        "n_sign_flips": sum(1 for r in rows if r["sign_flip"]),
        "n_flips_format_dominant": sum(1 for r in rows if r["flipped"] and r["dominant_bucket"] == "format"),
        "n_flips_semantic_dominant": sum(1 for r in rows if r["flipped"] and r["dominant_bucket"] == "semantic"),
    }


def flip_rates(cfg: Config, flips: list[dict]) -> list[dict[str, Any]]:
    out = []
    for factor in cfg.factors:
        rows_f = [r for r in flips if r["factor"] == factor]
        if not rows_f:
            continue
        for vname, vfilter in _variant_filters(cfg, factor, rows_f).items():
            for sname, sfilter in SIZE_SUBSETS.items():
                sel = [r for r in rows_f if vfilter(r) and sfilter(r)]
                if not sel and vname == "confounded_only":
                    continue
                out.append({"factor": factor, "variant": vname, "pair_subset": sname, **_rate(sel)})
    return out


def main_rows(cfg: Config, flips: list[dict], factors: list[str], size_subset: str = "all_pairs") -> list[dict]:
    sfilter = SIZE_SUBSETS[size_subset]
    sel = []
    for f in factors:
        rows_f = [r for r in flips if r["factor"] == f]
        if not rows_f:
            continue
        vfilter = _variant_filters(cfg, f, rows_f)["main"]
        sel += [r for r in rows_f if vfilter(r) and sfilter(r)]
    return sel


def disagreement(analysis: Analysis, base: str, alts: dict[str, str], gate: str,
                 restrict=None) -> dict[str, Any]:
    """Share of base decisions where the base label and the labels under the
    alternative protocols are not all identical (PLAN.md section 8)."""
    label_key = "label_ci" if gate == "ci" else "label_point"
    base_rows = analysis.rows(base)
    alt_rows = {name: analysis.rows(p) for name, p in alts.items()}
    n = k = 0
    for key, row in base_rows.items():
        if restrict is not None and not restrict(row):
            continue
        labels = [row[label_key]]
        for rows in alt_rows.values():
            if key in rows:
                labels.append(rows[key][label_key])
        if len(labels) < 2:
            continue
        n += 1
        k += len(set(labels)) > 1
    return {"n_decisions": n, "n_disagree": k, "disagreement_rate": (k / n) if n else None}


def _median(xs: list[float]):
    return statistics.median(xs) if xs else None


def hypotheses(cfg: Config, analysis: Analysis, flips: list[dict], control_summary: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    base = analysis.rows(cfg.base_protocol)
    h1_factors = cfg.groups.get("h1", [])

    def add(h, variant, statement, supported, **vals):
        out.append({"hypothesis": h, "variant": variant, "statement": statement,
                    "supported": supported, **vals})

    for sname in SIZE_SUBSETS:
        sfilter = SIZE_SUBSETS[sname]
        decisions = {k: r for k, r in base.items() if sfilter(r)}
        n_dec = len(decisions)
        variant = f"main/{sname}"

        # H1
        flipped_keys = {(r["pair"], r["suite"]) for r in main_rows(cfg, flips, h1_factors, sname) if r["flipped"]}
        rate = (len(flipped_keys) / n_dec) if n_dec else None
        add("H1", variant, ">=20% of decisions change label under >=1 factor level (F1-F10)",
            None if rate is None else rate >= 0.20,
            n_decisions=n_dec, n_flipped=len(flipped_keys), value=rate, threshold=0.20)

        # H2
        fmt_rows = main_rows(cfg, flips, cfg.groups.get("format", []), sname)
        oth_rows = main_rows(cfg, flips, cfg.groups.get("other", []), sname)
        fr = (sum(r["flipped"] for r in fmt_rows) / len(fmt_rows)) if fmt_rows else None
        orr = (sum(r["flipped"] for r in oth_rows) / len(oth_rows)) if oth_rows else None
        add("H2", variant, "format factors (F1,F2,F4,F7) flip more than other factors (F3,F5,F6,F8)",
            None if fr is None or orr is None else fr > orr,
            n_decisions=len(fmt_rows) + len(oth_rows), value=fr, comparison_value=orr,
            n_flipped=sum(r["flipped"] for r in fmt_rows), comparison_n_flipped=sum(r["flipped"] for r in oth_rows),
            comparison_n=len(oth_rows), n_format=len(fmt_rows))

        # H3
        med_f = _median([abs(base[k]["stress_diff"]) for k in decisions if k in flipped_keys])
        med_n = _median([abs(base[k]["stress_diff"]) for k in decisions if k not in flipped_keys])
        add("H3", variant, "flipping decisions have smaller median |stress diff| under D than never-flipping ones",
            None if med_f is None or med_n is None else med_f < med_n,
            n_decisions=n_dec, value=med_f, comparison_value=med_n,
            n_flipped=len(flipped_keys), comparison_n=n_dec - len(flipped_keys))

    # H4 (held-out pairs; D vs R across the nuisance set)
    robust = cfg.robust
    nuis = cfg.groups.get("nuisance", [])
    if robust.get("base"):
        d_alts = {f: cfg.factors[f]["protocol"] for f in nuis}
        r_alts = dict(robust.get("nuisance", {}))
        variants = {
            "primary/held_out": lambda r: r["split"] == "held-out",
            "held_out_sampling_changed_only": lambda r: r["split"] == "held-out" and r["f6_sampling_changed"],
            "held_out_size_preserving": lambda r: r["split"] == "held-out" and not r["size_changing"],
        }
        for vname, restrict in variants.items():
            dd = disagreement(analysis, cfg.base_protocol, d_alts, "point", restrict)
            rd = disagreement(analysis, robust["base"], r_alts, "ci", restrict)
            ok = None
            if dd["disagreement_rate"] is not None and rd["disagreement_rate"] is not None:
                ok = rd["disagreement_rate"] < dd["disagreement_rate"]
            add("H4", vname, "R disagrees less than D across nuisance set {F3,F5,F6} on held-out pairs",
                ok, n_decisions=rd["n_decisions"], value=rd["disagreement_rate"],
                comparison_value=dd["disagreement_rate"], n_flipped=rd["n_disagree"],
                comparison_n=dd["n_decisions"], comparison_n_flipped=dd["n_disagree"])

    # H5
    fa = control_summary.get("false_alarm_rate")
    dr = control_summary.get("detection_rate")
    ok = None if fa is None or dr is None else (fa <= 0.05 and dr >= 0.90)
    add("H5", "R_controls", "under R: A/A false-alarm rate <=5% and positive-control detection rate >=90%",
        ok, n_decisions=control_summary.get("n_aa"), value=fa, comparison_value=dr,
        comparison_n=control_summary.get("n_pc"))
    return out
