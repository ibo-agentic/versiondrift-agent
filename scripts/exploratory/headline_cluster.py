"""EXPLORATORY_headline_cluster.md: the S1 headline excess with a bootstrap over upgrade PAIRS.

    python -m scripts.exploratory.headline_cluster --out <folder>
"""

from __future__ import annotations

import csv

import numpy as np

from ._common import ADDENDUM_DIR, HEAD, SEED, BOOT_REPS, SEPARATE_PAIR, load_phase2, parse_out, pct


def run(out):
    from vdanalysis.phase2.addendum.run_addendum import _variant_filters
    from vdanalysis.phase2.addendum.s4_classes import GENERATION_FACTORS
    cfg, an, cx, flips = load_phase2()
    gen = [f for f in GENERATION_FACTORS if f in cfg.factors and cfg.factors[f].get("kind", "run") == "run"]
    pairs = [cfg.pair_name(p) for p in cfg.pairs]
    decisions = [(p, s) for p in pairs for s in cfg.suites]
    flip_gen = {(r["pair"], r["suite"]) for r in flips
                if r["factor"] in gen and r["flipped"] and _variant_filters(cfg, r["factor"], [r])["main"](r)}
    pdict = {tuple(r["decision"].split("/")): float(r["p_at_least_one_noise_flip"])
             for r in csv.DictReader(open(ADDENDUM_DIR / "s1_per_decision.csv"))}
    decided = [d for d in decisions if d in pdict]
    obs = {d: float(d in flip_gen) for d in decided}

    def pair_boot(use_pairs):
        rng = np.random.default_rng(SEED)
        P = len(use_pairs)
        on = [np.array([obs[d] for d in decided if d[0] == p]) for p in use_pairs]
        en = [np.array([pdict[d] for d in decided if d[0] == p]) for p in use_pairs]
        idx = rng.integers(0, P, size=(BOOT_REPS, P))
        diffs = np.empty(BOOT_REPS)
        for j, row in enumerate(idx):
            so = sum(on[i].sum() for i in row)
            se = sum(en[i].sum() for i in row)
            n = sum(len(on[i]) for i in row)
            diffs[j] = (so - se) / n
        return (np.mean(np.concatenate(on)), np.mean(np.concatenate(en)), np.quantile(diffs, [.025, .975]),
                float((diffs <= 0).mean()), len(np.concatenate(on)), P)

    r2 = {k: pair_boot([p for p in pairs if (k == "all" or p != SEPARATE_PAIR)]) for k in ("all", "excl")}
    md = HEAD + "# Headline excess with a bootstrap over upgrade PAIRS\n\n"
    md += ("Headline = share of decisions with >= 1 generation-factor flip (F1-F6, F11, main variants) minus the mean expected share with >= 1 noise flip "
           "(`s1_per_decision.csv`). The earlier exploratory note resampled decisions; here whole pairs (all of a pair's suites) are resampled with replacement, "
           "B = 10,000, seed 1234, so the 3 suites of a pair stay together.\n\n"
           "| | Pairs | Decisions | Observed share | Expected noise share | Difference (pts) | 95% CI (pts) | P(diff <= 0) |\n|---|---|---|---|---|---|---|---|\n")
    for k, name in (("all", "All pairs"), ("excl", "Excluding qwen25->qwen3")):
        O, E, ci, p, n, P = r2[k]
        md += f"| {name} | {P} | {n} | {pct(O)}% | {pct(E)}% | {100 * (O - E):+.1f} | {100 * ci[0]:+.1f} to {100 * ci[1]:+.1f} | {p:.3f} |\n"
    md += ("\n**Caveat:** only 10 pairs (9 after the exclusion) are resampled, so the interval is coarse; the expected noise share per decision is held fixed "
           "(task-level uncertainty in it is ignored), and pairs sharing a model are treated as independent.\n")
    (out / "EXPLORATORY_headline_cluster.md").write_text(md, encoding="utf-8")
    return ["EXPLORATORY_headline_cluster.md"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
