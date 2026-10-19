"""Phase 2 analysis entry point.

    python -m vdanalysis.phase2.run_phase2 --config configs/analysis_phase2.yaml --out analysis_out_v3

Reads run records only (never a model, never a GPU). Refuses to write inside
results/, results_smoke/, results_v2/ or results_v3/. Mode ``phase1`` (config
``phase2.mode``) reproduces the Phase 1 pipeline through the same code path and
is what ``regression.py`` checks against the frozen Phase 1 tables.

NOTE: do not run the Phase 2 mode on real records before the plan is locked
(PLAN_PHASE2.md section 0); the tests use fixture data only.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from ..aggregate import flip_rates, hypotheses
from ..controls import per_control_summary
from ..run_analysis import write_csv
from .analysis import Phase2Analysis, ViewSpec
from .config import Phase2Config, load_phase2_config
from .controls2 import control_rows2, per_control_summary2
from .descriptive import (agreement_rows, f5_shift_vs_aa, hw_noise_pairs, hw_noise_runs, new_flips, r_f5_same_hardware,
                          read_labels)
from .hypotheses2 import p1_rows, p2_p6_rows, p3_row, p4_row, p5_row, p7_rows

PROTECTED = ("results", "results_smoke", "results_v2", "results_v3")


def assert_safe_output_dir_p2(out_dir: str | Path) -> Path:
    out = Path(out_dir).resolve()
    for part in out.parts:
        if part in PROTECTED:
            raise ValueError(f"refusing to write inside protected folder {part!r}: {out}")
    return out


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def decision_protocols(cfg: Phase2Config) -> list[str]:
    explicit = cfg.p2.get("decision_protocols")
    if explicit:
        return list(explicit)
    return [p for p, spec in cfg.protocols.items() if not spec.get("control_only")]


def _factors_for_view(cfg: Phase2Config, view: ViewSpec) -> list[str]:
    """Factors in the H1 set; a 'greedy only' protocol (F10) has no sampled-only view."""
    names = list(cfg.groups.get("h1", cfg.factors))
    if view.trials == "sampled":
        names = [f for f in names if cfg.protocol_p2(cfg.factors[f].get("protocol", "")).get("trials") != "greedy"]
    return names


# =====================================================================================
# Phase 1 mode: same tables as vdanalysis.run_analysis, through the new code path
# =====================================================================================
def run_phase1_mode(cfg: Phase2Config, out_dir: Path, with_ci: bool = True, allow_missing: bool = False) -> dict[str, Any]:
    out_dir = assert_safe_output_dir_p2(out_dir)
    an = Phase2Analysis(cfg, with_ci=with_ci, allow_missing=allow_missing)
    decisions = [r for proto, spec in cfg.protocols.items() if not spec.get("control_only")
                 for r in an.rows(proto).values()]
    base_rows = list(an.rows(cfg.base_protocol).values())
    flips = an.flip_table()
    rates = flip_rates(cfg, flips)
    ctl_rows = control_rows2(an, secondary=False) if cfg.controls else []
    from ..controls import control_summary
    ctl_sum = control_summary(ctl_rows)
    hyp = hypotheses(cfg, an, flips, ctl_sum)
    tables = {"decisions_D": base_rows, "decisions_all_protocols": decisions, "factor_flips_long": flips,
              "flip_rates_by_factor": rates, "controls": ctl_rows, "controls_summary": per_control_summary(ctl_rows),
              "hypotheses": hyp}
    for name, rows in tables.items():
        write_csv(out_dir / f"{name}.csv", rows)
    warnings = an.store.all_warnings()
    (out_dir / "run_warnings.json").write_text(json.dumps({"warnings": warnings, "missing": an.missing}, indent=2),
                                               encoding="utf-8")
    return {"tables": tables, "warnings": warnings, "missing": an.missing}


# =====================================================================================
# Phase 2 mode
# =====================================================================================
def compute_view(an: Phase2Analysis, view_name: str, ref_rows: list[dict] | None) -> dict[str, Any]:
    cfg = an.cfg
    flips = an.flip_table(_factors_for_view(cfg, an.view))
    ctl = control_rows2(an, secondary=True) if cfg.controls else []
    hyp = p1_rows(an, flips, view_name)
    var_rows: list[dict] = []
    if ref_rows is not None:
        rows26, var_rows = p2_p6_rows(an, flips, ref_rows, view_name)
        hyp += rows26
    hyp += [p3_row(cfg, ctl, view_name), p4_row(cfg, ctl, view_name), p5_row(cfg, ctl, view_name)]
    return {"flips": flips, "controls": ctl, "hypotheses": hyp, "variants": var_rows}


def _tag(rows: list[dict], **kv) -> list[dict]:
    return [{**kv, **r} for r in rows]


def run_phase2_mode(cfg: Phase2Config, out_dir: Path, with_ci: bool = True, allow_missing: bool = False,
                    labels_path: str | Path | None = None) -> dict[str, Any]:
    out_dir = assert_safe_output_dir_p2(out_dir)
    an = Phase2Analysis(cfg, with_ci=with_ci, allow_missing=allow_missing)
    ref_path = cfg.p2.get("phase1_reference")
    ref_rows = None
    if ref_path:
        p = Path(ref_path)
        ref_rows = read_csv_rows(p if p.is_absolute() else cfg.base_dir / p)

    tables: dict[str, list[dict]] = {}
    views = {"all": ViewSpec(), "greedy": ViewSpec(trials="greedy"), "sampled": ViewSpec(trials="sampled")}
    computed = {}
    for vname, vspec in views.items():
        computed[vname] = compute_view(an.with_view(vspec), vname, ref_rows)

    main = computed["all"]
    tables["decisions_D"] = list(an.rows(cfg.base_protocol).values())
    tables["decisions_all_protocols"] = [r for proto in decision_protocols(cfg) for r in an.rows(proto).values()]
    tables["decisions_baselines"] = [r for spec in (cfg.p2.get("same_hardware") or {}).values()
                                     for r in an.rows(spec["baseline"]).values()]
    tables["factor_flips_long"] = main["flips"]
    tables["flip_rates_by_factor"] = flip_rates(cfg, main["flips"])
    tables["controls"] = main["controls"]
    tables["controls_summary"] = per_control_summary2(main["controls"])
    tables["hypotheses_p"] = [r for v in computed.values() for r in v["hypotheses"]]
    tables["p2_p6_replication_variants"] = [r for v in computed.values() for r in v["variants"]]
    tables["views_flips"] = [r for vname, v in computed.items() if vname != "all" for r in _tag(v["flips"], view=vname)]
    tables["views_controls"] = [r for vname, v in computed.items() if vname != "all" for r in _tag(v["controls"], view=vname)]
    tables["views_flip_rates"] = [r for vname, v in computed.items() for r in _tag(flip_rates(cfg, v["flips"]), view=vname)]

    # descriptive
    tables["hw_noise_runs"] = hw_noise_runs(an)
    tables["hw_noise_pairs"] = hw_noise_pairs(an)
    aa_d = cfg.p2.get("f5_aa_control", "AA2_D")
    tables["f5_shift_vs_aa"] = f5_shift_vs_aa(an, main["controls"], aa_d)
    tables["r_f5_same_hardware"] = r_f5_same_hardware(an)
    if ref_rows is not None:
        tables["new_flips"] = new_flips(main["flips"], ref_rows)
    if labels_path:
        tables["human_agreement"] = agreement_rows(read_labels(labels_path), cfg.p2.get("rule_labeler", "rule"))

    # P7 (only if W3 data are there)
    w3 = cfg.p2.get("w3")
    p7_note = "W3 not configured"
    if w3:
        try:
            ids = {}
            for suite, path in w3["original_tasks"].items():
                p = Path(path)
                p = p if p.is_absolute() else cfg.base_dir / p
                ids[suite] = {json.loads(l)["task_id"] for l in open(p, encoding="utf-8") if l.strip()}
            tables["p7"] = p7_rows(an, ids)
            p7_note = "computed"
        except FileNotFoundError as exc:
            p7_note = f"W3 not run (missing: {exc})"
            tables["p7"] = []

    for name, rows in tables.items():
        write_csv(out_dir / f"{name}.csv", rows)
    warnings = an.store.all_warnings()
    (out_dir / "run_warnings.json").write_text(
        json.dumps({"warnings": warnings, "missing": an.missing, "p7": p7_note}, indent=2), encoding="utf-8")
    return {"tables": tables, "warnings": warnings, "missing": an.missing, "p7": p7_note}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="analysis_out_v3")
    ap.add_argument("--no-ci", action="store_true")
    ap.add_argument("--allow-missing", action="store_true")
    ap.add_argument("--labels", default=None, help="W6 label CSV (record_id, labeler, label)")
    ap.add_argument("--report", default=None, help="write the Markdown report here (e.g. analysis/phase2/analysis_report.md)")
    args = ap.parse_args(argv)
    cfg = load_phase2_config(args.config)
    fn = run_phase1_mode if cfg.mode == "phase1" else run_phase2_mode
    kwargs = {"labels_path": args.labels} if cfg.mode == "phase2" else {}
    res = fn(cfg, Path(args.out), with_ci=not args.no_ci, allow_missing=args.allow_missing, **kwargs)
    if args.report and cfg.mode == "phase2":
        from .report import write_report
        write_report(cfg, res, Path(args.report))
    print(f"wrote {len(res['tables'])} tables to {args.out}; {len(res['warnings'])} warnings, {len(res['missing'])} missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
