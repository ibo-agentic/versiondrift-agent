"""EXPLORATORY_r_vs_d_noise.md: why R reruns flip more often than D reruns (distance to the boundary, CI widths).

    python -m scripts.exploratory.r_vs_d_noise --out <folder>
"""

from __future__ import annotations

import numpy as np

from ._common import BOOT_REPS, HEAD, SEED, parse_out, pct
from .flip_vs_threshold import prepare


def run(out):
    from scipy import stats as sps
    from vdanalysis.phase2.addendum.s1_noise import per_decision_flip_prob
    cfg, an, cx, decisions, tab = prepare()

    def stats(v):
        v = np.array(v) * 100
        return f"{np.median(v):.2f} / {np.quantile(v, .25):.2f}-{np.quantile(v, .75):.2f}"

    pR = [per_decision_flip_prob(cx.arrays("R", p, s), cx.arrays("R_AA2", p, s), BOOT_REPS, SEED) for (p, s) in decisions
          if cx.arrays("R", p, s) is not None and cx.arrays("R_AA2", p, s) is not None]
    pD = [per_decision_flip_prob(cx.arrays("D", p, s), cx.arrays("D_AA2", p, s), BOOT_REPS, SEED) for (p, s) in decisions
          if cx.arrays("D", p, s) is not None and cx.arrays("D_AA2", p, s) is not None]
    dD = [t["dist_D"] for t in tab]
    dR = [t["dist_R"] for t in tab]
    w = sps.wilcoxon(dD, dR)
    md = HEAD + "# Why R reruns flip more than D reruns (5/30 vs 2/30)\n\n"
    md += ("Per decision (30 decisions, the same pairs and suites under both protocols). Distance = ||stress diff| - 0.05|, in points. CI width = the 95% task-bootstrap interval "
           "of the stress diff from the pipeline's own gate rows. Expected rerun flip probability = per-decision share of task resamples in which the main arm and its rerun arm get "
           "different point labels (S1.4 method, B = 10,000, seed 1234), averaged over the decisions.\n\n| Quantity | D | R |\n|---|---|---|\n")
    md += f"| Observed rerun flips | {sum(t['rerun_D'] for t in tab)}/30 | {sum(t['rerun_R'] for t in tab)}/30 |\n"
    md += f"| Expected rerun flip share (mean of per-decision probabilities) | {pct(np.mean(pD))}% | {pct(np.mean(pR))}% |\n"
    md += f"| Distance to boundary, median / IQR (pts) | {stats(dD)} | {stats(dR)} |\n"
    for thr in (1, 2, 3):
        md += f"| Decisions within {thr} pt(s) of a boundary | {sum(100 * x < thr for x in dD)} | {sum(100 * x < thr for x in dR)} |\n"
    md += f"| 95% CI width of the stress diff, median / IQR (pts) | {stats([t['ciw_D'] for t in tab])} | {stats([t['ciw_R'] for t in tab])} |\n"
    md += f"\nPaired Wilcoxon on the distances, D vs R: p = {w.pvalue:.3f}.\n\n"
    md += ("**Caveat:** 2 vs 5 flips out of 30 is a small difference (the intervals overlap widely), and the comparison explains the gap only descriptively: "
           "R decisions lying closer to a boundary or having wider intervals would raise R's rerun flip chance. In this table R decisions lie closer to a boundary "
           "(median 2.35 vs 3.53 points; paired Wilcoxon p = 0.012) while the CI widths are about the same (8.4 vs 8.7 points), so closeness to the boundary, not wider intervals, "
           "is what differs. D's observed rerun flips (2) are below its expected share (15.1%, about 4.5 flips) and R's (5) are above its expected share (11.8%, about 3.5 flips), "
           "so part of the 2 vs 5 gap is chance; the expected shares themselves differ by only 3 points.\n")
    (out / "EXPLORATORY_r_vs_d_noise.md").write_text(md, encoding="utf-8")
    return ["EXPLORATORY_r_vs_d_noise.md"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
