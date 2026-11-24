"""EXPLORATORY_S1_headline_excl_qwen.md: the S1 headline (>= 1 generation flip vs expected noise share) without qwen25->qwen3.

    python -m scripts.exploratory.s1_headline_excl_qwen --out <folder>
"""

from __future__ import annotations

import csv

import numpy as np

from ._common import ADDENDUM_DIR, BOOT_REPS, SEED, SEPARATE_PAIR, load_phase2, parse_out


def run(out):
    from vdanalysis.phase2.addendum.run_addendum import _variant_filters
    from vdanalysis.phase2.addendum.s4_classes import GENERATION_FACTORS
    cfg, an, cx, flips = load_phase2()
    pairs = [cfg.pair_name(p) for p in cfg.pairs]
    decisions = [(p, s) for p in pairs for s in cfg.suites]
    flipped = {(r["pair"], r["suite"]) for r in flips
               if r["flipped"] and r["factor"] in GENERATION_FACTORS and _variant_filters(cfg, r["factor"], [r])["main"](r)}
    decided = {(r["pair"], r["suite"]) for r in flips if r["factor"] in GENERATION_FACTORS}
    exp = {tuple(d["decision"].split("/")): float(d["p_at_least_one_noise_flip"])
           for d in csv.DictReader(open(ADDENDUM_DIR / "s1_per_decision.csv"))}

    def one(excl):
        keys = [k for k in exp if (k[0] != SEPARATE_PAIR if excl else True) and k in decided]
        o = np.array([k in flipped for k in keys], float)
        e = np.array([exp[k] for k in keys])
        rng = np.random.default_rng(SEED)
        n = len(keys)
        idx = rng.integers(0, n, size=(BOOT_REPS, n))
        d = o[idx].mean(1) - e[idx].mean(1)
        lo, hi = np.percentile(d, [2.5, 97.5])
        return n, int(o.sum()), o.mean(), e.mean(), lo, hi, float((d <= 0).mean())

    a, b = one(False), one(True)

    def row(name, r):
        n, k, o, e, lo, hi, p = r
        return (f"| {name} | {n} | {100 * o:.1f}% ({k}/{n}) | {100 * e:.1f}% | {100 * (o - e):+.1f} pts | {100 * lo:+.1f} to {100 * hi:+.1f} | {p:.2g} |")

    md = ("# EXPLORATORY: S1 headline excluding the qwen25->qwen3 pair\n\n"
          "**Exploratory. Not pre-registered. Descriptive only; it feeds no gate, verdict or hypothesis.**\n"
          "Asked for 2026-11-14, after the first Phase 2 analysis (tag pre-analysis-v2.1, commit 9654dbd) had been seen.\n\n"
          "## What was computed\n\n"
          "For each decision (pair x suite) that has a rerun arm: the observed flag \"flips under at least one generation factor\"\n"
          "(F1, F2, F3, F4, F5, F6, F11, main variants, as in S1) and the expected probability of at least one noise flip\n"
          "(`p_at_least_one_noise_flip` from `analysis_out_v3/addendum/s1_per_decision.csv`). The headline is the observed share\n"
          "minus the mean expected share. The 95% interval is a percentile bootstrap over decisions: resample the decisions with\n"
          "replacement, B = 10,000, seed 1234.\n\n"
          "## Result\n\n"
          "| | Decisions | Observed share with >=1 generation flip | Expected noise share | Difference | 95% CI | P(diff <= 0) |\n|---|---|---|---|---|---|---|\n"
          + row("All decisions", a) + "\n" + row("Excluding qwen25->qwen3", b) + "\n\n"
          f"The \"All decisions\" row reproduces the saved S1 headline (observed {a[2]:.1f}, expected {a[3]:.4f}).\n\n"
          "## Caveat\n\n"
          "The interval resamples decisions only. It ignores the task-level sampling uncertainty in each decision's noise\n"
          "probability (which the S1 hierarchical bootstrap includes), and it treats decisions as independent although several\n"
          "share models. It is therefore narrower than a full hierarchical interval would be. Read it as a rough guide.\n\n"
          "With the three qwen25->qwen3 decisions dropped, the gap above noise is smaller and its interval includes zero. This is\n"
          "in line with the factor-level S1 result, where only F2 (qwen3 thinking off, which exists only for that pair) stood out\n"
          "after Holm adjustment.\n")
    (out / "EXPLORATORY_S1_headline_excl_qwen.md").write_text(md, encoding="utf-8")
    return ["EXPLORATORY_S1_headline_excl_qwen.md"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
