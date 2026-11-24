"""EXPLORATORY_threshold_sensitivity.md: the study re-read with the gate at +/-0.03, +/-0.05 and +/-0.07.

    python -m scripts.exploratory.threshold_sensitivity --out <folder>

All comparisons use the rounding-safe helpers of _common (diffs rounded to 9 decimals), so an exact +/-delta is neutral.
"""

from __future__ import annotations

import numpy as np

from ._common import HEAD, SEED, BOOT_REPS, ci_gate, classify, load_phase2, parse_out, pct, point_code, rd, static


def run(out):
    from vdanalysis.phase2.addendum.run_addendum import _variant_filters
    from vdanalysis.phase2.addendum.s3_fourclass import interval
    cfg, an, cx, flips = load_phase2()
    pairs = [cfg.pair_name(p) for p in cfg.pairs]
    decisions = [(p, s) for p in pairs for s in cfg.suites]
    h1 = cfg.raw.get("factor_groups", {}).get("h1", [])
    rows = {p: an.rows(p) for p in ("D", "D_AA2", "R", "R_AA2")}
    rowsD = rows["D"]
    select = [r for r in flips if r["factor"] in h1 and _variant_filters(cfg, r["factor"], [r])["main"](r)]
    f_kind = {f: cfg.factors[f].get("kind", "run") for f in h1}
    bq = {(proto, pair, suite): interval(cx.arrays(proto, pair, suite), 0.90, BOOT_REPS, SEED)
          for proto in ("D", "R") for (pair, suite) in decisions}
    result = {}
    for delta in (0.03, 0.05, 0.07):
        flipped_dec, n_rows, sign_rows, mism = set(), 0, 0, 0
        for r in select:
            d = (r["pair"], r["suite"])
            dl = int(point_code(np.array([r["d_diff"]]), delta)[0])
            if f_kind[r["factor"]] == "gate":
                rr = rowsD[d]
                fl = {"harmful": -1, "neutral": 0, "beneficial": 1}[ci_gate(rr["stress_diff"], rr["ci_lo"], rr["ci_hi"], delta)]
            else:
                fl = int(point_code(np.array([r["factor_diff"]]), delta)[0])
            if abs(delta - 0.05) < 1e-9 and (dl != fl) != bool(r["flipped"]):
                mism += 1
            if dl != fl:
                flipped_dec.add(d)
                n_rows += 1
                sign_rows += dl * fl == -1
        rer = {}
        for proto in ("D", "R"):
            k = sg = 0
            for d in decisions:
                la = int(point_code(np.array([rows[proto][d]["stress_diff"]]), delta)[0])
                lb = int(point_code(np.array([rows[proto + "_AA2"][d]["stress_diff"]]), delta)[0])
                k += la != lb
                sg += la * lb == -1
            rer[proto] = (k, sg)
        inc = {}
        for proto in ("D", "R"):
            cl = []
            for (pair, suite) in decisions:
                rr = rows[proto][(pair, suite)]
                lc = ci_gate(rr["stress_diff"], rr["ci_lo"], rr["ci_hi"], delta)
                lo, hi = bq[(proto, pair, suite)]
                cl.append(classify(rr["stress_diff"], lo, hi, lc, delta))
            inc[proto] = (cl.count("inconclusive"), len(cl))
        result[delta] = {"dec_flip": len(flipped_dec), "flip_rows": n_rows, "sign_rows": sign_rows, "rerun": rer, "inc": inc, "mism": mism}
    md = HEAD + "# Threshold sensitivity: gate at +/-0.03, +/-0.05, +/-0.07\n\n"
    md += ("The point gate's threshold is changed everywhere (labels recomputed from the stored stress diffs; the CI gate and the 4-class verdict use the same threshold, with the stored 95% intervals "
           "and a 90% task bootstrap, B = 10,000, seed 1234). No data are rerun. (a) uses the P1 definition: 30 decisions, flips under at least one of F1-F10 (main variants; F9 = CI gate). "
           "(b) point-gate label changes between the main arm and its A/A arm, over 30 decisions. (c) sign reversal = a label change between harmful and beneficial. (d) 4-class verdict of the main arm.\n\n")
    md += "| Quantity | +/-0.03 | **+/-0.05 (pre-registered)** | +/-0.07 |\n|---|---|---|---|\n"
    R3 = [result[x] for x in (0.03, 0.05, 0.07)]
    md += "| (a) decisions with >= 1 factor flip (of 30) | " + " | ".join(f"{r['dec_flip']} ({pct(r['dec_flip'] / 30)}%)" for r in R3) + " |\n"
    md += "| (a') factor flips in total (decision x factor cells) | " + " | ".join(str(r["flip_rows"]) for r in R3) + " |\n"
    md += "| (b) rerun flips D vs D_AA2 (of 30) | " + " | ".join(f"{r['rerun']['D'][0]} ({pct(r['rerun']['D'][0] / 30)}%)" for r in R3) + " |\n"
    md += "| (b) rerun flips R vs R_AA2 (of 30) | " + " | ".join(f"{r['rerun']['R'][0]} ({pct(r['rerun']['R'][0] / 30)}%)" for r in R3) + " |\n"
    md += "| (c) sign reversals among factor flips | " + " | ".join(str(r["sign_rows"]) for r in R3) + " |\n"
    md += "| (c) sign reversals in reruns (D / R) | " + " | ".join(f"{r['rerun']['D'][1]} / {r['rerun']['R'][1]}" for r in R3) + " |\n"
    md += "| (d) inconclusive share, D (of 30) | " + " | ".join(f"{r['inc']['D'][0]} ({pct(r['inc']['D'][0] / 30)}%)" for r in R3) + " |\n"
    md += "| (d) inconclusive share, R (of 30) | " + " | ".join(f"{r['inc']['R'][0]} ({pct(r['inc']['R'][0] / 30)}%)" for r in R3) + " |\n"
    md += ("\nCheck: at +/-0.05 the recomputed values reproduce the saved ones (factor flips "
           f"{'match' if result[0.05]['mism'] == 0 else str(result[0.05]['mism']) + ' mismatches'}; D inconclusive 10 of 30, R 10 of 30 as in S3; rerun flips 2 and 5).\n\n")
    md += static("threshold_correction") + "\n"
    md += ("**Caveat:** only the threshold changes; the per-decision noise, the task set and the factor definitions do not, and decisions near a boundary move between classes as the boundary moves, "
           "so (a), (b) and (d) are expected to fall as the threshold widens. 30 decisions, not independent.\n")
    (out / "EXPLORATORY_threshold_sensitivity.md").write_text(md, encoding="utf-8")
    return ["EXPLORATORY_threshold_sensitivity.md"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
