"""EXPLORATORY_flip_vs_threshold.md (+ .png): flip vs distance of the stress diff from the +/-0.05 gate boundary.

    python -m scripts.exploratory.flip_vs_threshold --out <folder>

``prepare()`` is shared with r_vs_d_noise.py. The PNG needs matplotlib (pinned in requirements.txt); without it the table
is still written and the figure is skipped.
"""

from __future__ import annotations

import numpy as np

from ._common import DELTA, HEAD, load_phase2, parse_out, rd


def dist(x):
    return abs(abs(rd(x)) - DELTA)


def prepare():
    from vdanalysis.phase2.addendum.run_addendum import _variant_filters
    from vdanalysis.phase2.addendum.s4_classes import GENERATION_FACTORS
    cfg, an, cx, flips = load_phase2()
    gen = [f for f in GENERATION_FACTORS if f in cfg.factors and cfg.factors[f].get("kind", "run") == "run"]
    h1 = cfg.raw.get("factor_groups", {}).get("h1", [])
    pairs = [cfg.pair_name(p) for p in cfg.pairs]
    decisions = [(p, s) for p in pairs for s in cfg.suites]

    def main_flip(factors):
        return {(r["pair"], r["suite"]) for r in flips
                if r["factor"] in factors and r["flipped"] and _variant_filters(cfg, r["factor"], [r])["main"](r)}

    flip_gen, flip_any = main_flip(gen), main_flip(h1)
    rowsD, rowsR, rowsDA, rowsRA = an.rows("D"), an.rows("R"), an.rows("D_AA2"), an.rows("R_AA2")
    tab = []
    for d in decisions:
        if d not in rowsD or d not in rowsR:
            continue
        tab.append({"pair": d[0], "suite": d[1], "d_diff": rowsD[d]["stress_diff"], "r_diff": rowsR[d]["stress_diff"],
                    "dist_D": dist(rowsD[d]["stress_diff"]), "dist_R": dist(rowsR[d]["stress_diff"]),
                    "flip_any": d in flip_any, "flip_gen": d in flip_gen,
                    "rerun_D": d in rowsDA and rowsD[d]["label_point"] != rowsDA[d]["label_point"],
                    "rerun_R": d in rowsRA and rowsR[d]["label_point"] != rowsRA[d]["label_point"],
                    "ciw_D": rowsD[d]["ci_hi"] - rowsD[d]["ci_lo"], "ciw_R": rowsR[d]["ci_hi"] - rowsR[d]["ci_lo"]})
    return cfg, an, cx, decisions, tab


def logit(x, y):
    import statsmodels.api as sm
    x = np.asarray(x, float) * 100
    y = np.asarray(y, float)
    if y.sum() in (0, len(y)):
        return {"note": "all outcomes equal"}
    try:
        m = sm.Logit(y, sm.add_constant(x)).fit(disp=0, maxiter=200)
        return {"b0": float(m.params[0]), "b1": float(m.params[1]), "se1": float(m.bse[1]), "p1": float(m.pvalues[1]), "n": len(y), "events": int(y.sum())}
    except Exception as e:
        return {"note": f"fit failed ({type(e).__name__}: separation or too few events)", "n": len(y), "events": int(y.sum())}


def run(out):
    cfg, an, cx, decisions, tab = prepare()
    fits = {"any factor (D diff)": logit([t["dist_D"] for t in tab], [t["flip_any"] for t in tab]),
            "generation factor (D diff)": logit([t["dist_D"] for t in tab], [t["flip_gen"] for t in tab]),
            "rerun D vs D_AA2 (D diff)": logit([t["dist_D"] for t in tab], [t["rerun_D"] for t in tab]),
            "rerun R vs R_AA2 (R diff)": logit([t["dist_R"] for t in tab], [t["rerun_R"] for t in tab])}
    written = []
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 3, figsize=(15, 4.4), sharex=True)
        rng = np.random.default_rng(1234)
        panels = (("Any factor flip (x: D diff)", "dist_D", "flip_any", "any factor (D diff)"),
                  ("Rerun flip, D vs D_AA2 (x: D diff)", "dist_D", "rerun_D", "rerun D vs D_AA2 (D diff)"),
                  ("Rerun flip, R vs R_AA2 (x: R diff)", "dist_R", "rerun_R", "rerun R vs R_AA2 (R diff)"))
        for a, (title, xs, ys, fk) in zip(ax, panels):
            x = np.array([100 * t[xs] for t in tab])
            y = np.array([float(t[ys]) for t in tab])
            a.scatter(x, y + rng.uniform(-0.04, 0.04, len(y)), s=28, alpha=.75)
            f = fits[fk]
            if "b1" in f:
                g = np.linspace(0, max(x.max(), 1), 100)
                a.plot(g, 1 / (1 + np.exp(-(f["b0"] + f["b1"] * g))), color="C3")
                a.set_title(f"{title}\nslope {f['b1']:+.2f}/pt (p={f['p1']:.2f}, {f['events']}/{f['n']} flips)", fontsize=9)
            else:
                a.set_title(f"{title}\n{f.get('note', '')}", fontsize=9)
            a.set_xlabel("distance from nearest boundary ||diff|-0.05| (points)")
            a.set_ylabel("flipped (0/1)")
            a.set_yticks([0, 1])
            a.grid(alpha=.3)
        fig.suptitle("EXPLORATORY: flip vs distance to the +/-0.05 gate boundary (30 decisions)", fontsize=10)
        fig.tight_layout()
        fig.savefig(out / "EXPLORATORY_flip_vs_threshold.png", dpi=130)
        written.append("EXPLORATORY_flip_vs_threshold.png")
    except ImportError:
        print("matplotlib not installed: figure skipped")
    md = HEAD + "# Flip vs distance to the gate boundary\n\n"
    md += ("For each of the 30 decisions: distance = ||stress diff| - 0.05| (percentage points; the point gate changes label at +/-0.05). "
           "'Any factor' = flips under at least one of F1-F10 (P1's definition, main variants); 'generation' = F1-F6, F11. "
           "Rerun flips are point-gate label changes, D vs D_AA2 and R vs R_AA2. Logistic fit of flip ~ distance (points), unpenalised.\n\n"
           "![flip vs distance](EXPLORATORY_flip_vs_threshold.png)\n\n| Outcome | Flips / decisions | Slope per point | SE | p |\n|---|---|---|---|---|\n")
    for k, f in fits.items():
        if "b1" in f:
            md += f"| {k} | {f['events']}/{f['n']} | {f['b1']:+.3f} | {f['se1']:.3f} | {f['p1']:.3f} |\n"
        else:
            md += f"| {k} | {f.get('events', '-')}/{f.get('n', len(tab))} | n/a | n/a | {f['note']} |\n"
    md += "\n| Distance from boundary (D diff) | Decisions | Any-factor flips | Rerun flips (D) |\n|---|---|---|---|\n"
    for lo, hi in [(0, 1), (1, 2), (2, 5), (5, 1000)]:
        s = [t for t in tab if lo <= 100 * t["dist_D"] < hi]
        md += f"| {lo}-{hi if hi < 1000 else '+'} pts | {len(s)} | {sum(t['flip_any'] for t in s)} | {sum(t['rerun_D'] for t in s)} |\n"
    md += ("\n**Caveat:** 30 decisions with at most 13 events, so the fits are crude and a non-significant slope does not show there is none; "
           "decisions are not independent (pairs share models). A negative slope means flips concentrate near the boundary. The R rerun fit is close to separation "
           "(all 5 flips lie within about 1.5 points of a boundary), so its slope and p-value are unstable; read it as \"R rerun flips occurred only very near a boundary\", "
           "not as an effect size.\n")
    (out / "EXPLORATORY_flip_vs_threshold.md").write_text(md, encoding="utf-8")
    return written + ["EXPLORATORY_flip_vs_threshold.md"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
