"""EXPLORATORY_pseudo_aa.md: a pooled (pseudo A/A) noise floor for the rerun flip rate and the S1 excess against it.

    python -m scripts.exploratory.pseudo_aa --out <folder>
"""

from __future__ import annotations

import csv
from collections import defaultdict

import numpy as np

from ._common import ADDENDUM_DIR, HEAD, SEED, SEPARATE_PAIR, load_phase2, parse_out, pct, point_code, point_label


def run(out):
    from vdanalysis.phase2.addendum.run_addendum import build_s1_input
    from vdanalysis.phase2.addendum.s4_classes import GENERATION_FACTORS
    cfg, an, cx, flips = load_phase2()
    stress = list(cfg.stress)
    pairs = [cfg.pair_name(p) for p in cfg.pairs]
    pair_models = {cfg.pair_name(p): (p["old"], p["new"]) for p in cfg.pairs}
    decisions = [(p, s) for p in pairs for s in cfg.suites]
    models = sorted({m for p in cfg.pairs for m in (p["old"], p["new"])})
    gen = [f for f in GENERATION_FACTORS if f in cfg.factors and cfg.factors[f].get("kind", "run") == "run"]
    inp = build_s1_input(cx, flips, ("D", "D_AA2"), gen)
    rows = {p: an.rows(p) for p in ("D", "D_AA2", "R", "R_AA2")}

    def trial_means(run_):
        s = defaultdict(float)
        n = defaultdict(int)
        for k, (score, _b) in run_.keys.items():
            if k[1] in stress:
                s[(k[4], k[1])] += score
                n[(k[4], k[1])] += 1
        trials = sorted({t for t, _ in s})
        return trials, np.array([[s[(t, c)] / n[(t, c)] for c in stress] for t in trials])

    B = 2000
    rng = np.random.default_rng(SEED)
    arm_means = {}
    for proto in ("D", "R"):
        for model in models:
            for suite in cfg.suites:
                ra, rb = an.run_for(proto, model, suite), an.run_for(proto + "_AA2", model, suite)
                ta, Ma = trial_means(ra)
                tb, Mb = trial_means(rb)
                ga, gb = sorted(ra.greedy_trials()), sorted(rb.greedy_trials())
                assert len(ga) == 1 and len(gb) == 1 and len(ta) == 10 and len(tb) == 10
                M = np.vstack([Ma, Mb])
                gi = [ta.index(ga[0]), 10 + tb.index(gb[0])]
                samp = [i for i in range(20) if i not in gi]
                bit = rng.integers(0, 2, size=B)
                perm = np.argsort(rng.random((B, 18)), axis=1)
                sidx = np.array(samp)[perm]
                g1 = np.where(bit == 0, gi[0], gi[1])
                g2 = np.where(bit == 0, gi[1], gi[0])
                arm_means[(proto, model, suite)] = ((M[g1] + M[sidx[:, :9]].sum(axis=1)) / 10, (M[g2] + M[sidx[:, 9:]].sum(axis=1)) / 10)
    pseudo = {}
    for proto in ("D", "R"):
        for (pair, suite) in decisions:
            old, new = pair_models[pair]
            d1 = (arm_means[(proto, new, suite)][0] - arm_means[(proto, old, suite)][0]).mean(axis=1)
            d2 = (arm_means[(proto, new, suite)][1] - arm_means[(proto, old, suite)][1]).mean(axis=1)
            pseudo[(proto, pair, suite)] = float((point_code(d1) != point_code(d2)).mean())

    def pair_boot_mean(proto, use_pairs, reps=10000, seed=SEED):
        r = np.random.default_rng(seed)
        per = [np.array([pseudo[(proto, p, s)] for s in cfg.suites]) for p in use_pairs]
        idx = r.integers(0, len(use_pairs), size=(reps, len(use_pairs)))
        vals = np.array([np.concatenate([per[i] for i in row]).mean() for row in idx])
        return float(np.concatenate(per).mean()), np.quantile(vals, [.025, .975])

    obs_rerun = {p: sum(rows[p][d]["label_point"] != rows[p + "_AA2"][d]["label_point"] for d in decisions) for p in ("D", "R")}
    s14 = {r["decision"]: float(r["p_rerun_flip"]) for r in csv.DictReader(open(ADDENDUM_DIR / "s1_per_decision.csv"))}
    md = HEAD + "# Pseudo A/A: a pooled noise floor for the rerun flip rate\n\n"
    md += ("**Method.** For each model and suite, the 20 trials of the main arm (10) and the A/A arm (10, same prompts) are pooled. Each of B = 2,000 random splits "
           "puts 10 trials in each of two arms; each arm keeps exactly one greedy trial (the two greedy trials are assigned to the arms at random) and gets 9 of the 18 sampled "
           "trials. Splits are independent for every model and suite and shared by the pairs that use the model. In each arm the stress diff (new minus old, equal weight over the two "
           "stress conditions, all tasks) gets the point-gate label (+/-0.05); the per-decision rerun flip probability is the share of splits whose two arms differ. Seed 1234.\n\n"
           "**Assumptions.** Trial 0 of every arm is the greedy trial (checked from the stored temperatures: exactly one greedy trial in each arm for all 96 model-suite runs); "
           "splitting treats the 20 trials as exchangeable apart from the greedy rule, i.e. it assumes the main and the A/A arm have the same sampling process (true by design: same run seed, "
           "same temperatures, other trial seeds). Tasks are not resampled here, so this noise is trial noise only, not task-sampling noise.\n\n")
    md += "## Rerun flip rate\n\n| Protocol | Observed rerun flips (main vs A/A arm) | Pseudo A/A mean flip rate | 95% CI over pairs | S1.4 expected share (task bootstrap) |\n|---|---|---|---|---|\n"
    for proto in ("D", "R"):
        m, ci = pair_boot_mean(proto, pairs)
        s14m = np.mean([s14[f"{p}/{s}"] for (p, s) in decisions]) if proto == "D" else None
        md += f"| {proto} | {obs_rerun[proto]}/30 ({pct(obs_rerun[proto] / 30)}%) | {pct(m)}% | {pct(ci[0])}% to {pct(ci[1])}% | {pct(s14m) + '%' if s14m is not None else 'n/a here'} |\n"
    md += "\n(The S1.4 expected share for R, 11.8%, is in EXPLORATORY_r_vs_d_noise.md.) CI = bootstrap over the 10 upgrade pairs (whole pairs resampled, 10,000 replicates, seed 1234).\n\n"

    def lab(proto, pair, suite):
        a = inp.arrays.get((pair, suite, proto))
        return None if a is None else point_label(a.diff())

    cells = {f: [(c[0], c[1], int(lab(c[2], c[0], c[1]) != lab(c[3], c[0], c[1])), pseudo[("D", c[0], c[1])]) for c in inp.usable_cells(f)] for f in gen}

    def excess(f, use_pairs, reps=10000, seed=SEED):
        cs = [c for c in cells[f] if c[0] in use_pairs]
        if not cs:
            return None
        n = len(cs)
        point = (sum(c[2] for c in cs) - sum(c[3] for c in cs)) / n
        r = np.random.default_rng(seed)
        byp = {p: [c for c in cs if c[0] == p] for p in use_pairs}
        P = len(use_pairs)
        idx = r.integers(0, P, size=(reps, P))
        vals = []
        for row in idx:
            sel = [c for i in row for c in byp[use_pairs[i]]]
            vals.append(np.nan if not sel else (sum(c[2] for c in sel) - sum(c[3] for c in sel)) / len(sel))
        v = np.array(vals)
        v = v[np.isfinite(v)]
        return {"n": n, "flips": sum(c[2] for c in cs), "noise": sum(c[3] for c in cs) / n, "e": point, "lo": float(np.quantile(v, .025)),
                "hi": float(np.quantile(v, .975)), "ub": float(np.quantile(v, .95)), "p": float((np.sum(v <= 0) + 1) / (len(v) + 1))}

    for title, up in (("All pairs", pairs), ("Excluding qwen25->qwen3", [p for p in pairs if p != SEPARATE_PAIR])):
        md += (f"## Excess over the pseudo A/A noise floor: {title}\n\n| Factor | Decisions | Factor flips | Pseudo-A/A noise (expected flips per decision) | Excess (pts) | 95% CI (pts) | 95% upper bound (pts) | P(excess <= 0) |\n|---|---|---|---|---|---|---|---|\n")
        for f in gen:
            e = excess(f, up)
            if e is None:
                md += f"| {f} | 0 | | | n/a | n/a | n/a | n/a |\n"
                continue
            md += f"| {f} | {e['n']} | {e['flips']} | {pct(e['noise'])}% | {100 * e['e']:+.1f} | {100 * e['lo']:+.1f} to {100 * e['hi']:+.1f} | {100 * e['ub']:+.1f} | {e['p']:.3f} |\n"
        md += "\n"
    md += ("The factor flip rate f_F is the observed share of decisions where the factor changes the point-gate label (same cells as S1); the noise column is the mean pseudo-A/A flip "
           "probability (D protocol) over the same decisions, so excess = f_F minus that. The interval resamples pairs and holds each decision's noise probability fixed.\n\n"
           "**Caveat:** pseudo A/A uses all 20 trials, so each arm's decision is made from the same trial pool and the two arms are not independent draws; "
           "it is a lower-variance estimate of the noise than one real rerun, but it also ignores task-sampling noise and is based on 30 decisions per protocol.\n")
    (out / "EXPLORATORY_pseudo_aa.md").write_text(md, encoding="utf-8")
    return ["EXPLORATORY_pseudo_aa.md"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
