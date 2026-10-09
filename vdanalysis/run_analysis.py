"""Full analysis entry point.

    python -m vdanalysis.run_analysis --config configs/analysis_official_folders.yaml --out analysis_out

Reads run records only (never raw model calls); writes CSV tables and a
Markdown summary into --out. Refuses to write inside results/,
results_smoke/ or results_v2/.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from .aggregate import disagreement, flip_rates, hypotheses
from .config import Config, assert_safe_output_dir, load_config
from .controls import control_rows, control_summary, per_control_summary
from .engine import Analysis
from .studies import failure_split, qwen3_f4_vs_f2, qwen3_pair_labels, robust_checks


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: _fmt(r.get(k)) for k in cols})


def _fmt(v: Any) -> Any:
    if isinstance(v, float):
        return f"{v:.6f}"
    return "" if v is None else v


def _md_table(rows: list[dict[str, Any]], cols: list[str]) -> str:
    if not rows:
        return "_(no rows)_\n"
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(str(_fmt(r.get(c))) for c in cols) + " |")
    return "\n".join(out) + "\n"


def run_all(cfg: Config, out_dir: Path, with_ci: bool = True, allow_missing: bool = False) -> dict[str, Any]:
    out_dir = assert_safe_output_dir(out_dir)
    an = Analysis(cfg, with_ci=with_ci, allow_missing=allow_missing)

    # Decisions under every protocol (each also carries both gate labels).
    decisions = [
        r for proto, spec in cfg.protocols.items() if not spec.get("control_only")
        for r in an.rows(proto).values()
    ]
    base_rows = list(an.rows(cfg.base_protocol).values())
    flips = an.flip_table()
    rates = flip_rates(cfg, flips)
    ctl_rows = control_rows(an) if cfg.controls else []
    ctl_sum = control_summary(ctl_rows)
    hyp = hypotheses(cfg, an, flips, ctl_sum)

    # Disagreement over named factor sets.
    dis = []
    for set_name, factors in cfg.groups.items():
        alts = {f: cfg.factors[f]["protocol"] for f in factors if cfg.factors[f].get("kind", "run") == "run"}
        for variant, restrict in (("all_pairs", None), ("held_out", lambda r: r["split"] == "held-out")):
            d = disagreement(an, cfg.base_protocol, alts, "point", restrict)
            dis.append({"factor_set": set_name, "factors": "+".join(alts), "decisions": variant, **d})
    if cfg.robust.get("base"):
        d = disagreement(an, cfg.robust["base"], dict(cfg.robust.get("nuisance", {})), "ci")
        dis.append({"factor_set": "R_nuisance", "factors": "+".join(cfg.robust.get("nuisance", {})),
                    "decisions": "all_pairs", **d})

    size_rows = [r for r in decisions if r["size_changing"]]
    tables = {
        "decisions_D": base_rows,
        "decisions_all_protocols": decisions,
        "factor_flips_long": flips,
        "flip_rates_by_factor": rates,
        "disagreement": dis,
        "size_changing_decisions": size_rows,
        "failure_split": failure_split(an),
        "flip_failure_decomposition": [
            r for r in flips if r["flipped"]
        ],
        "controls": ctl_rows,
        "controls_summary": per_control_summary(ctl_rows),
        "qwen3_f4_vs_f2": qwen3_f4_vs_f2(an),
        "qwen3_pair_labels": qwen3_pair_labels(an),
        "robust_protocol_checks": robust_checks(an),
        "hypotheses": hyp,
    }
    for name, rows in tables.items():
        write_csv(out_dir / f"{name}.csv", rows)

    warnings = an.store.all_warnings()
    report = _report(cfg, tables, hyp, warnings, an.missing)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    (out_dir / "run_warnings.json").write_text(
        json.dumps({"warnings": warnings, "missing": an.missing}, indent=2), encoding="utf-8")
    return {"tables": tables, "warnings": warnings, "missing": an.missing, "report": report}


def _report(cfg: Config, tables: dict, hyp: list[dict], warnings: list[str], missing: list[str]) -> str:
    lines = ["# Upgrade-verdict stability: analysis report\n"]
    lines.append(f"Gate: point +-{cfg.threshold}; CI gate cluster bootstrap {cfg.reps} reps, seed {cfg.seed}. "
                 f"Stress conditions: {', '.join(cfg.stress)}.\n")
    if missing:
        lines.append(f"**{len(missing)} runs missing - results below are partial.**\n")
    if warnings:
        lines.append(f"**{len(warnings)} loader warnings (see run_warnings.json).**\n")
    lines.append("\n## Hypotheses\n")
    lines.append(_md_table(hyp, ["hypothesis", "variant", "supported", "n_decisions", "n_flipped", "value",
                                 "comparison_value", "comparison_n", "comparison_n_flipped"]))
    lines.append("\n## Flip rate by factor (main variant, all pairs)\n")
    lines.append(_md_table([r for r in tables["flip_rates_by_factor"] if r["pair_subset"] == "all_pairs"],
                           ["factor", "variant", "n_decisions", "n_flips", "flip_rate", "n_sign_flips",
                            "n_flips_format_dominant", "n_flips_semantic_dominant"]))
    lines.append("\n## Decisions under D\n")
    lines.append(_md_table(tables["decisions_D"],
                           ["pair", "suite", "size_changing", "stress_diff", "ci_lo", "ci_hi",
                            "label_point", "label_ci", "clean_uninformative"]))
    lines.append("\n## Controls\n")
    lines.append(_md_table(tables["controls_summary"], list(tables["controls_summary"][0]) if tables["controls_summary"] else []))
    lines.append("\n## Qwen3 F4 vs F2 (F4 = grammar + thinking blocked)\n")
    q = tables["qwen3_f4_vs_f2"]
    lines.append(_md_table(q, list(q[0]) if q else []))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="analysis_out")
    ap.add_argument("--results-root", default=None, help="override config results_root (e.g. a fake folder)")
    ap.add_argument("--no-ci", action="store_true", help="skip the bootstrap (point gate only; faster)")
    ap.add_argument("--allow-missing", action="store_true", help="skip missing runs instead of failing")
    args = ap.parse_args(argv)
    cfg = load_config(args.config, results_root=args.results_root)
    res = run_all(cfg, Path(args.out), with_ci=not args.no_ci, allow_missing=args.allow_missing)
    print(f"wrote {len(res['tables'])} tables to {args.out}; {len(res['warnings'])} warnings, {len(res['missing'])} missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
