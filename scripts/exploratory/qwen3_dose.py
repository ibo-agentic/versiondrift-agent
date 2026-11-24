"""EXPLORATORY_qwen3_dose.md: qwen25 -> qwen3 under D (thinking, 256 tokens), F1 (thinking, 1024) and F2 (no thinking).

    python -m scripts.exploratory.qwen3_dose --out <folder>
"""

from __future__ import annotations

import csv

from ._common import HEAD, P7_DIR, SEPARATE_PAIR, load_phase2, parse_out, pct


def run(out):
    from vdanalysis.phase2.analysis import ViewSpec
    cfg, an, cx, flips = load_phase2()
    pairs = [cfg.pair_name(p) for p in cfg.pairs]
    decisions = [(p, s) for p in pairs for s in cfg.suites]
    md = HEAD + "# qwen25->qwen3: dose of thinking budget\n\n"
    md += ("Protocols: D (thinking on, 256 tokens), F1 (thinking on, 1024 tokens), F2 (thinking off). Stress diff = qwen3 minus qwen25 under the same protocol "
           "for the pair as the analysis builds it. Unparsed = share of stress-condition records for qwen3 where nothing parseable came out "
           "(failure bucket 'format'); truncated = share of all raw outputs of the qwen3 run flagged truncated.\n\n")
    md += "| Suite | Protocol | Stress diff | 95% CI | Point label | CI label | qwen3 unparsed | qwen3 truncated |\n|---|---|---|---|---|---|---|---|\n"
    for suite in cfg.suites:
        for proto, name in (("D", "D (think, 256)"), ("F1", "F1 (think, 1024)"), ("F2", "F2 (no think)")):
            r = an.rows(proto).get((SEPARATE_PAIR, suite))
            if r is None:
                md += f"| {suite} | {name} | not available | | | | | |\n"
                continue
            run_ = an.run_for(proto, "qwen3", suite)
            stress = [k for k in run_.keys if k[1] in cfg.stress]
            unp = sum(run_.keys[k][1] == "format" for k in stress) / len(stress)
            tr = an.store.truncation_rate(run_)
            md += (f"| {suite} | {name} | {r['stress_diff']:+.3f} | [{r['ci_lo']:+.3f}, {r['ci_hi']:+.3f}] | {r['label_point']} | {r['label_ci']} | "
                   f"{pct(unp)}% | {'n/a' if tr is None else pct(tr) + '%'} |\n")
    ag = an.with_view(ViewSpec(trials="greedy"))
    gD, gA = ag.rows("D"), ag.rows("D_AA2")
    flipsg = [d for d in decisions if d in gD and d in gA and gD[d]["label_point"] != gA[d]["label_point"]]
    gR, gRA = ag.rows("R"), ag.rows("R_AA2")
    flipsgR = [d for d in decisions if d in gR and d in gRA and gR[d]["label_point"] != gRA[d]["label_point"]]
    vc = list(csv.DictReader(open(P7_DIR / "views_controls.csv")))
    aaD = [r for r in vc if r["view"] == "greedy" and r["protocol"] == "D_AA2"]
    nonneutral = [r for r in aaD if r["label_point"] != "neutral"]
    md += ("\n## Greedy-only A/A\n\nTrial 0 only (temperature 0). Label changes between the main arm and its rerun arm, point gate:\n\n"
           f"- D vs D_AA2 over the 30 decisions: **{len(flipsg)} flip(s)**" + (": " + ", ".join(f"{p}/{s}" for p, s in flipsg) if flipsg else "") + "\n"
           f"- R vs R_AA2 over the 30 decisions: {len(flipsgR)} flip(s)\n"
           f"- D vs D_AA2 over the 48 A/A control decisions (16 models x 3 suites, model vs itself): **{len(nonneutral)} non-neutral label(s)** of {len(aaD)}\n")
    md += ("\n**Caveat:** three decisions (one pair, three suites) and one model's thinking budget; this shows how the qwen3 result moves with the budget, "
           "not why. Truncation is computed over all conditions of the run, unparsed over stress conditions only.\n")
    (out / "EXPLORATORY_qwen3_dose.md").write_text(md, encoding="utf-8")
    return ["EXPLORATORY_qwen3_dose.md"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
