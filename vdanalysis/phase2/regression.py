"""Regression check: the Phase 2 code, run in Phase 1 mode, must reproduce the
frozen Phase 1 tables exactly.

    python -m vdanalysis.phase2.regression --config configs/analysis_phase1_regression.yaml \
        --reference analysis_out --out analysis_out_v3/regression_phase1

Phase 1 mode = Phase 1 records only (3 trials), primary gate only (no
secondary gate), no F6 trimming, no same-hardware baselines, A/A as it was
(different run seed, records matched on drift/fault type). The tables written
here are compared, cell by cell as text, with the reference CSVs written by
the original ``vdanalysis.run_analysis``. Any difference is listed; the exit
status is 0 only when there is none.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .config import load_phase2_config
from .run_phase2 import run_phase1_mode

COMPARED = ("decisions_D", "decisions_all_protocols", "factor_flips_long", "flip_rates_by_factor",
            "controls", "controls_summary", "hypotheses")
# H1-H5 numbers are the hypotheses table; the others pin down every input of it.


def _read(path: Path) -> list[list[str]]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.reader(fh))


def compare_tables(new_dir: Path, ref_dir: Path, names=COMPARED) -> dict[str, dict]:
    out = {}
    for name in names:
        a, b = _read(new_dir / f"{name}.csv"), _read(ref_dir / f"{name}.csv")
        diffs = []
        if a and b and a[0] != b[0]:
            diffs.append({"where": "header", "new": a[0], "ref": b[0]})
        if len(a) != len(b):
            diffs.append({"where": "row count", "new": len(a) - 1, "ref": len(b) - 1})
        if a and b and a[0] == b[0]:
            head = a[0]
            for i, (ra, rb) in enumerate(zip(a[1:], b[1:]), start=1):
                if ra != rb:
                    cols = [(head[j], ra[j], rb[j]) for j in range(min(len(ra), len(rb))) if ra[j] != rb[j]]
                    diffs.append({"where": f"row {i}", "cells": cols})
        out[name] = {"rows_new": max(len(a) - 1, 0), "rows_ref": max(len(b) - 1, 0), "n_diffs": len(diffs),
                     "diffs": diffs[:20]}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/analysis_phase1_regression.yaml")
    ap.add_argument("--reference", default="analysis_out")
    ap.add_argument("--out", default="analysis_out_v3/regression_phase1")
    ap.add_argument("--no-ci", action="store_true")
    args = ap.parse_args(argv)
    cfg = load_phase2_config(args.config)
    if cfg.mode != "phase1":
        raise SystemExit("the regression check needs a config with phase2.mode: phase1")
    out = Path(args.out)
    res = run_phase1_mode(cfg, out, with_ci=not args.no_ci)
    cmp = compare_tables(out, Path(args.reference))
    total = sum(v["n_diffs"] for v in cmp.values())
    (out / "regression_result.json").write_text(
        json.dumps({"total_differences": total, "tables": cmp, "loader_warnings": len(res["warnings"]),
                    "missing": res["missing"]}, indent=2), encoding="utf-8")
    for name, v in cmp.items():
        print(f"{name:26s} rows new/ref {v['rows_new']}/{v['rows_ref']}  differences: {v['n_diffs']}")
    print("TOTAL DIFFERENCES:", total)
    return 0 if total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
