"""EXPLORATORY_equivalence_bounds.md: one-sided 95% upper bound on the excess flip rate per generation factor.

    python -m scripts.exploratory.equivalence_bounds --out <folder>
"""

from __future__ import annotations

import numpy as np

from ._common import HEAD, SEED, BOOT_REPS, SEPARATE_PAIR, load_phase2, parse_out, point_label


def run(out):
    from vdanalysis.phase2.addendum.run_addendum import build_s1_input
    from vdanalysis.phase2.addendum.s1_noise import hier_bootstrap
    from vdanalysis.phase2.addendum.s4_classes import GENERATION_FACTORS
    cfg, an, cx, flips = load_phase2()
    gen = [f for f in GENERATION_FACTORS if f in cfg.factors and cfg.factors[f].get("kind", "run") == "run"]
    inp = build_s1_input(cx, flips, ("D", "D_AA2"), gen)

    def lab(proto, pair, suite):
        a = inp.arrays.get((pair, suite, proto))
        return None if a is None else point_label(a.diff())

    def obs_factor(f, excl):
        k = kr = n = 0
        for (pair, suite, fp, bp) in inp.usable_cells(f):
            if excl and pair == SEPARATE_PAIR:
                continue
            n += 1
            k += lab(fp, pair, suite) != lab(bp, pair, suite)
            kr += lab("D", pair, suite) != lab("D_AA2", pair, suite)
        return n, k, kr

    res = {}
    for excl in (False, True):
        boot = hier_bootstrap(inp, BOOT_REPS, SEED, exclude_pairs=(SEPARATE_PAIR,) if excl else ())
        rows = []
        for f in gen:
            n, k, kr = obs_factor(f, excl)
            e = boot["factors"][f]["e"]
            e = e[np.isfinite(e)]
            row = {"factor": f, "n": n, "k_factor": int(k), "k_rerun": int(kr), "excess": (k - kr) / n if n else None}
            if n and len(e):
                row.update(ub95=float(np.quantile(e, 0.95)), lo=float(np.quantile(e, .025)), hi=float(np.quantile(e, .975)))
            rows.append(row)
        res[excl] = rows

    def fmt_ub(r):
        return "n/a (no decisions)" if "ub95" not in r else f"{100 * r['ub95']:+.1f}"

    md = HEAD + "# Equivalence bounds: upper bound on the excess flip rate per generation factor\n\n"
    md += ("Excess e_F = factor flip rate f_F minus the rerun flip rate (D vs D_AA2) on the same decisions, as in S1. Hierarchical bootstrap "
           "(pairs, then tasks within each pair-suite; f_F and the rerun rate recomputed in every replicate), B = 10,000, seed 1234. "
           "\"Upper bound\" = the one-sided 95% bound (95th percentile of the replicates of e_F). Percentage points.\n\n")
    for excl, title in ((False, "All pairs"), (True, "Excluding qwen25->qwen3")):
        md += (f"## {title}\n\n| Factor | Decisions | Factor flips | Rerun flips | Excess (pts) | 95% interval (pts) | "
               "**95% upper bound: excess <= (pts)** |\n|---|---|---|---|---|---|---|\n")
        for r in res[excl]:
            ci = "n/a" if "lo" not in r else f"{100 * r['lo']:+.1f} to {100 * r['hi']:+.1f}"
            ex = "n/a" if r["excess"] is None else f"{100 * r['excess']:+.1f}"
            md += f"| {r['factor']} | {r['n']} | {r['k_factor']} | {r['k_rerun']} | {ex} | {ci} | {fmt_ub(r)} |\n"
        md += "\n"
    md += ("**Caveat:** with 3 to 30 decisions per factor the bounds are wide, so no factor gets a tight upper bound (the only bound below zero is F1 once "
           "qwen25->qwen3 is excluded: 0 factor flips against 2 rerun flips); F2 exists only for qwen25->qwen3 (n/a after excluding it). The excluded-pair point "
           "estimates are recomputed on the remaining pairs (the addendum's own excluding-pair table first reported the full-data point estimate next to the reduced-data interval; this was corrected in DEVIATIONS entry (m), and that table now reports the excluding-pair point estimates).\n")
    (out / "EXPLORATORY_equivalence_bounds.md").write_text(md, encoding="utf-8")
    return ["EXPLORATORY_equivalence_bounds.md"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
