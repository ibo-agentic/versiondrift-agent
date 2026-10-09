"""Extra tables: failure split, Qwen3 F4-vs-F2 comparison, R checks."""

from __future__ import annotations

from typing import Any

from .engine import Analysis
from .stats import compare

CONDITION_GROUPS = ("baseline", "schema_drift", "fault_reporting")


def failure_split(analysis: Analysis) -> list[dict[str, Any]]:
    """Per loaded run x condition: success / format-failure / semantic-failure
    shares. Format = nothing parseable came out (parse_ok false); semantic =
    parsed fine but wrong. Records are never moved between buckets."""
    out = []
    for run in analysis.store._cache.values():
        for cond in CONDITION_GROUPS:
            vals = [v for k, v in run.keys.items() if k[1] == cond]
            if not vals:
                continue
            n = len(vals)
            fmt = sum(1 for _, b in vals if b == "format")
            sem = sum(1 for _, b in vals if b == "semantic")
            out.append({
                "protocol": run.protocol, "model": run.model, "suite": run.suite, "condition": cond,
                "n": n, "success_rate": sum(s for s, _ in vals) / n,
                "format_fail_rate": fmt / n, "semantic_fail_rate": sem / n,
                "n_format_fail": fmt, "n_semantic_fail": sem,
            })
    return out


def qwen3_f4_vs_f2(analysis: Analysis) -> list[dict[str, Any]]:
    """Separate Qwen3's two F4 effects (DEVIATIONS.md 2026-10-08).

    F2 = thinking off, grammar off; F4 = grammar on, thinking blocked (as a
    side effect); D = both off-defaults. Paired diffs on the same records:
      F2 - D   effect of thinking off alone
      F4 - D   effect of grammar + thinking blocked (the labeled F4 result)
      F4 - F2  what remains after both runs have no thinking, i.e. the
               grammar's own effect
    """
    spec = analysis.cfg.raw.get("qwen3_study")
    if not spec:
        return []
    cfg = analysis.cfg
    model = spec["model"]
    d, f2, f4 = cfg.base_protocol, spec["thinking_off"], spec["grammar"]
    label = spec.get("label", "grammar+thinking_blocked")
    out = []
    for suite in cfg.suites:
        runs = {p: analysis.run_for(p, model, suite) for p in (d, f2, f4)}
        if any(r is None for r in runs.values()):
            continue
        for cond_name, conds in (("stress", cfg.stress), ("baseline", [cfg.baseline_condition])):
            row: dict[str, Any] = {"model": model, "suite": suite, "conditions": cond_name,
                                   "f4_label": label}
            for p, run in runs.items():
                vals = [v for k, v in run.keys.items() if k[1] in conds]
                row[f"mean_{p}"] = sum(s for s, _ in vals) / len(vals)
                row[f"format_fail_{p}"] = sum(1 for _, b in vals if b == "format") / len(vals)
            for tag, (a, b) in {
                "thinking_off_effect(F2-D)": (d, f2),
                "grammar_plus_thinking_blocked(F4-D)": (d, f4),
                "grammar_only_effect(F4-F2)": (f2, f4),
            }.items():
                c = compare(runs[a], runs[b], conds, cfg.threshold, cfg.reps, cfg.seed, with_ci=analysis.with_ci)
                row[f"{tag}_diff"] = c.diff
                row[f"{tag}_ci_lo"] = c.ci_lo
                row[f"{tag}_ci_hi"] = c.ci_hi
            out.append(row)
    return out


def qwen3_pair_labels(analysis: Analysis) -> list[dict[str, Any]]:
    """The size-changing Qwen2.5->Qwen3 decision under D, F2 and F4, side by side."""
    spec = analysis.cfg.raw.get("qwen3_study")
    if not spec:
        return []
    out = []
    for proto in (analysis.cfg.base_protocol, spec["thinking_off"], spec["grammar"]):
        for (pair, suite), r in analysis.rows(proto).items():
            if r["new"] == spec["model"] or r["old"] == spec["model"]:
                out.append({"protocol": proto, "pair": pair, "suite": suite,
                            "stress_diff": r["stress_diff"], "label_point": r["label_point"],
                            "label_ci": r["label_ci"], "confounding": r["confounding"]})
    return out


def robust_checks(analysis: Analysis) -> list[dict[str, Any]]:
    """PLAN.md section 7 items 1 and 6 for protocol R: truncation flag
    (>2% truncated records) and clean-suite ceiling flag per decision, plus
    the unconstrained run's format-failure rate (a deployment-risk flag,
    reported next to but never mixed into R's decision)."""
    cfg = analysis.cfg
    base = cfg.robust.get("base")
    if not base:
        return []
    unc = cfg.robust.get("unconstrained")
    out = []
    for (pair, suite), r in analysis.rows(base).items():
        row = {"protocol": base, "pair": pair, "suite": suite, "label_ci": r["label_ci"],
               "confounding": r["confounding"], "clean_uninformative": r["clean_uninformative"],
               "baseline_old": r["baseline_old"], "baseline_new": r["baseline_new"]}
        for side in ("old", "new"):
            run = analysis.run_for(base, r[side], suite)
            t = analysis.store.truncation_rate(run) if run else None
            row[f"truncation_{side}"] = t
            row[f"truncation_flag_{side}"] = None if t is None else t > cfg.truncation_limit
        if unc:
            for side in ("old", "new"):
                run = analysis.run_for(unc, r[side], suite)
                vals = [b for k, (s, b) in run.keys.items()] if run else []
                row[f"unconstrained_format_fail_{side}"] = (
                    sum(1 for b in vals if b == "format") / len(vals) if vals else None
                )
        out.append(row)
    return out
