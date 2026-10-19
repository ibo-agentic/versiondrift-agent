"""P1-P7 (PLAN_PHASE2.md section 4).

Every function here is a pure function of decision rows, flip rows and control
rows; none reads files or loads a model. Verdict columns (``supported``) use
the thresholds of the plan; they come from ``cfg.p2['hypotheses']`` so a
changed threshold is a config edit, not a code edit.

P2 and P6 use the *replicate* notion of section 5 ("the same decision flips
under the same factor, in the same direction, at 10 trials"). The plan does not
say how a decision that flipped under several factors in Phase 1 is counted,
nor whether "same direction" means the same label change or the same sign of
the change. Rather than pick one, ``replication_variants`` computes the count
under every reading and the P2 / P6 rows carry ``supported = None`` (pending)
until the choice is written into the plan.
"""

from __future__ import annotations

from typing import Any

from ..aggregate import SIZE_SUBSETS, main_rows
from .analysis import Phase2Analysis, ViewSpec
from .stats2 import clopper_pearson

RANK = {"harmful": -1, "neutral": 0, "beneficial": 1}


def _truthy(v: Any) -> bool:
    return v is True or str(v).lower() == "true"


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)


# ---- P1 ----------------------------------------------------------------
def p1_rows(an: Phase2Analysis, flips: list[dict], view_name: str = "all") -> list[dict[str, Any]]:
    cfg = an.cfg
    thr = float(cfg.threshold_p("p1_threshold", 0.20))
    base = an.rows(cfg.base_protocol)
    h1 = cfg.groups.get("h1", [])
    out = []
    for sname, sfilter in SIZE_SUBSETS.items():
        decisions = {k: r for k, r in base.items() if sfilter(r)}
        n = len(decisions)
        keys = {(r["pair"], r["suite"]) for r in main_rows(cfg, flips, h1, sname) if r["flipped"]}
        lo = hi = rate = None
        if n:
            rate = len(keys) / n
            lo, hi = clopper_pearson(len(keys), n)
        out.append({"hypothesis": "P1", "view": view_name, "variant": f"main/{sname}",
                    "statement": f"share of decisions that flip under >=1 factor (F1-F10) is at least {thr:.0%}",
                    "n_decisions": n, "n_flipped": len(keys), "value": rate, "ci95_lo": lo, "ci95_hi": hi,
                    "threshold": thr, "supported": None if rate is None else rate >= thr, "note": ""})
    return out


# ---- P2 / P6: replication -------------------------------------------------
def reference_flip_index(ref_rows: list[dict], cfg, factors: list[str], main_only: bool = True) -> dict[tuple, list[dict]]:
    """{(pair, suite): [flip rows]} of Phase 1's flipped decisions, from the
    frozen Phase 1 flip table. ``main_only`` applies the same main-variant
    filter H1 used (so the count is Phase 1's 13)."""
    rows = [dict(r, flipped=_truthy(r["flipped"]), n_models_changed=int(r["n_models_changed"]),
                 confounding=r.get("confounding") or "") for r in ref_rows]
    sel = main_rows(cfg, rows, factors) if main_only else [r for r in rows if r["factor"] in factors]
    out: dict[tuple, list[dict]] = {}
    for r in sel:
        if r["flipped"]:
            out.setdefault((r["pair"], r["suite"]), []).append(r)
    return out


def _same_direction(ref: dict, now: dict, mode: str) -> bool:
    if mode == "labels":
        return (ref["d_label"], ref["factor_label"]) == (now["d_label"], now["factor_label"])
    if mode == "sign":
        return _sign(RANK[ref["factor_label"]] - RANK[ref["d_label"]]) == \
               _sign(RANK[now["factor_label"]] - RANK[now["d_label"]]) != 0
    raise ValueError(mode)


def replication_variants(ref_index: dict[tuple, list[dict]], now_flips: list[dict],
                         factors: list[str] | None = None) -> dict[str, int]:
    """Number of reference decisions that replicate, under each reading:
    direction: ``labels`` (same label change) | ``sign`` (same sign of the change);
    multi-factor decisions: ``any`` (one replicated factor suffices) | ``all``.
    ``factors`` restricts the reference flips considered (P6 uses only F5)."""
    now = {(r["factor"], r["pair"], r["suite"]): r for r in now_flips if r["flipped"]}
    out = {}
    n_ref = 0
    for direction in ("labels", "sign"):
        for multi in ("any", "all"):
            n = 0
            n_ref = 0
            for (pair, suite), refs in ref_index.items():
                refs = [r for r in refs if factors is None or r["factor"] in factors]
                if not refs:
                    continue
                n_ref += 1
                hits = [(r["factor"], pair, suite) in now and _same_direction(r, now[(r["factor"], pair, suite)], direction)
                        for r in refs]
                n += any(hits) if multi == "any" else all(hits)
            out[f"{direction}/{multi}"] = n
    out["n_reference_decisions"] = n_ref
    return out


def p2_p6_rows(an: Phase2Analysis, flips: list[dict], ref_rows: list[dict], view_name: str = "all"
               ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = an.cfg
    h1 = cfg.groups.get("h1", [])
    f5_name = cfg.p2.get("p6_factor", "F5")
    p2_min = int(cfg.threshold_p("p2_min_replicated", 7))
    p6_min = int(cfg.threshold_p("p6_min_replicated", 4))
    ref_all = reference_flip_index(ref_rows, cfg, h1)
    ref_f5 = reference_flip_index(ref_rows, cfg, [f5_name])
    v2 = replication_variants(ref_all, flips)
    v6 = replication_variants(ref_f5, flips, factors=[f5_name])
    note = "replicate definition pending (see README): verdict withheld"
    rows = [
        {"hypothesis": "P2", "view": view_name, "variant": "pending", "statement":
         f"of Phase 1's flipped decisions, at least {p2_min} replicate at 10 trials",
         "n_decisions": v2["n_reference_decisions"], "n_flipped": None, "value": None, "threshold": p2_min,
         "supported": None, "note": note},
        {"hypothesis": "P6", "view": view_name, "variant": "pending", "statement":
         f"{f5_name} same-hardware flips at least {p6_min} of the decisions it flipped in Phase 1",
         "n_decisions": v6["n_reference_decisions"], "n_flipped": None, "value": None, "threshold": p6_min,
         "supported": None, "note": note},
    ]
    var_rows = []
    for hyp, v, thr in (("P2", v2, p2_min), ("P6", v6, p6_min)):
        for k, n in v.items():
            if k == "n_reference_decisions":
                continue
            direction, multi = k.split("/")
            var_rows.append({"hypothesis": hyp, "view": view_name, "direction_rule": direction,
                             "multi_factor_rule": multi, "n_reference_decisions": v["n_reference_decisions"],
                             "n_replicated": n, "threshold": thr, "would_be_supported": n >= thr})
    return rows, var_rows


# ---- P3 / P4 / P5 -------------------------------------------------------------
def _control_subset(rows: list[dict], name: str) -> list[dict]:
    return [r for r in rows if r["control"] == name]


def _rate_row(h: str, view: str, statement: str, k: int, n: int, threshold: float, ok_fn, **extra) -> dict[str, Any]:
    if n == 0:
        return {"hypothesis": h, "view": view, "variant": "", "statement": statement, "n_decisions": 0,
                "n_flipped": 0, "value": None, "threshold": threshold, "supported": None, "note": "no data", **extra}
    lo, hi = clopper_pearson(k, n)
    return {"hypothesis": h, "view": view, "variant": "", "statement": statement, "n_decisions": n, "n_flipped": k,
            "value": k / n, "ci95_lo": lo, "ci95_hi": hi, "threshold": threshold, "supported": ok_fn(k / n),
            "note": "", **extra}


def p3_row(cfg, ctl_rows: list[dict], view: str = "all") -> dict[str, Any]:
    name = cfg.p2.get("p3_control", "AA2_R")
    thr = float(cfg.threshold_p("p3_max", 0.05))
    sel = _control_subset(ctl_rows, name)
    k = sum(r["label"] != "neutral" for r in sel)
    return _rate_row("P3", view, f"R-gate A/A false-alarm rate is at most {thr:.0%}", k, len(sel), thr,
                     lambda v: v <= thr, control=name)


def p4_row(cfg, ctl_rows: list[dict], view: str = "all") -> dict[str, Any]:
    name = cfg.p2.get("p4_control", "PC_Q2K_R")
    thr = float(cfg.threshold_p("p4_min", 0.90))
    sel = _control_subset(ctl_rows, name)
    k = sum(r["label"] == "harmful" for r in sel)
    return _rate_row("P4", view, f"Q2_K positive control detected under R in at least {thr:.0%}", k, len(sel), thr,
                     lambda v: v >= thr, control=name)


def p5_row(cfg, ctl_rows: list[dict], view: str = "all") -> dict[str, Any]:
    name = cfg.p2.get("p5_control", "PC_NODESC_R")
    sel = _control_subset(ctl_rows, name)
    statement = "the full-score gate detects the no-description control in more decisions than the stress-only gate"
    if not sel or "full_label" not in sel[0]:
        return {"hypothesis": "P5", "view": view, "variant": "", "statement": statement, "n_decisions": len(sel),
                "n_flipped": None, "value": None, "threshold": None, "supported": None, "note": "no data",
                "control": name}
    stress = sum(r["label"] == "harmful" for r in sel)
    full = sum(r["full_label"] == "harmful" for r in sel)
    return {"hypothesis": "P5", "view": view, "variant": "", "statement": statement, "n_decisions": len(sel),
            "n_flipped": full, "value": full, "comparison_value": stress, "threshold": None,
            "supported": full > stress, "note": "value = full-score detections, comparison_value = stress-only detections",
            "control": name}


# ---- P7 -------------------------------------------------------------------------
def p7_rows(an: Phase2Analysis, task_ids_by_suite: dict[str, set[str]]) -> list[dict[str, Any]]:
    """Per protocol (D with the point gate, R with the CI gate) and suite: the
    share of decisions whose verdict on the original tasks differs from the
    verdict on the full task set. ``an`` must be built on the full-task-set
    protocols (config ``w3``)."""
    w3 = an.cfg.p2.get("w3") or {}
    out = []
    for proto_name, spec in (w3.get("protocols") or {}).items():
        proto, gate = spec["protocol"], spec.get("gate", "point")
        key = "label_ci" if gate == "ci" else "label_point"
        full = an.rows(proto)
        orig_view = {}
        for suite, ids in task_ids_by_suite.items():
            sub = Phase2Analysis(an.cfg, an.store, an.with_ci, an.allow_missing, ViewSpec(tasks=frozenset(ids)))
            orig_view[suite] = {k: r for k, r in sub.rows(proto).items() if k[1] == suite}
        tot_n = tot_d = 0
        for suite in an.cfg.suites:
            f_rows = {k: r for k, r in full.items() if k[1] == suite}
            o_rows = orig_view.get(suite, {})
            keys = sorted(set(f_rows) & set(o_rows))
            differ = [k for k in keys if f_rows[k][key] != o_rows[k][key]]
            tot_n += len(keys)
            tot_d += len(differ)
            lo = hi = None
            if keys:
                lo, hi = clopper_pearson(len(differ), len(keys))
            out.append({"hypothesis": "P7", "protocol": proto_name, "gate": gate, "suite": suite,
                        "n_decisions": len(keys), "n_differ": len(differ),
                        "share": (len(differ) / len(keys)) if keys else None, "ci95_lo": lo, "ci95_hi": hi,
                        "differing": ";".join(f"{k[0]}:{o_rows[k][key]}->{f_rows[k][key]}" for k in differ)})
        out.append({"hypothesis": "P7", "protocol": proto_name, "gate": gate, "suite": "all",
                    "n_decisions": tot_n, "n_differ": tot_d, "share": (tot_d / tot_n) if tot_n else None,
                    "ci95_lo": clopper_pearson(tot_d, tot_n)[0] if tot_n else None,
                    "ci95_hi": clopper_pearson(tot_d, tot_n)[1] if tot_n else None, "differing": ""})
    return out
