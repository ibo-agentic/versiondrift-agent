"""EXPLORATORY_S3_W3_tasks.md: the S3 four-class verdict on the original 100 tasks vs the full W3 task set (bfcl suites, D and R).

    python -m scripts.exploratory.s3_w3_tasks --out <folder>
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from ._common import ADDENDUM_DIR, BOOT_REPS, SEED, classify, load_phase2, parse_out, static


def run(out):
    from vdanalysis.phase2.addendum.data import make_arrays
    from vdanalysis.phase2.addendum.s3_fourclass import interval
    from vdanalysis.phase2.analysis import Phase2Analysis, ViewSpec
    from vdanalysis.phase2.hypotheses2 import _rows_for_suites
    cfg, an, cx, flips = load_phase2()
    w3 = cfg.p2["w3"]
    suites = list(w3["suites"])
    ids = {}
    for s, p in w3["original_tasks"].items():
        p = Path(p)
        p = p if p.is_absolute() else cfg.base_dir / p
        ids[s] = {json.loads(line)["task_id"] for line in open(p, encoding="utf-8") if line.strip()}
    pairs = {cfg.pair_name(p): p for p in cfg.pairs}
    data = []
    for name, proto in (("D", w3["protocols"]["D"]["protocol"]), ("R", w3["protocols"]["R"]["protocol"])):
        full_rows = _rows_for_suites(an, proto, suites)
        for suite in suites:
            sub = Phase2Analysis(cfg, an.store, True, False, ViewSpec(tasks=frozenset(ids[suite])))
            orig_rows = _rows_for_suites(sub, proto, [suite])
            for (pair, su), frow in sorted(full_rows.items()):
                if su != suite:
                    continue
                p = pairs[pair]
                res = {"protocol": name, "suite": suite, "pair": pair}
                for tag, a_an, row in (("orig", sub, orig_rows[(pair, suite)]), ("full", an, frow)):
                    old = a_an.run_for(proto, p["old"], suite)
                    new = a_an.run_for(proto, p["new"], suite)
                    arr = make_arrays(old, new, cfg.stress)
                    lo, hi = interval(arr, 0.90, BOOT_REPS, SEED)
                    res[tag] = classify(row["stress_diff"], lo, hi, row["label_ci"])
                    res[tag + "_diff"] = row["stress_diff"]
                    res[tag + "_n_tasks"] = arr.n_tasks
                data.append(res)
    saved = {(r["protocol"], r["pair"], r["suite"]): r["class4"] for r in csv.DictReader(open(ADDENDUM_DIR / "s3_classes.csv"))}
    mismatch = sum(1 for r in data if saved.get((r["protocol"], r["pair"], r["suite"])) != r["orig"])
    n_tasks = {s: sorted({(r["orig_n_tasks"], r["full_n_tasks"]) for r in data if r["suite"] == s}) for s in suites}
    C = ("harmful", "neutral", "beneficial", "inconclusive")

    def cnt(sel, k):
        c = Counter(r[k] for r in sel)
        return [c[x] for x in C]

    def fmt_pct(n, total):
        return f"{100 * n / total:g}%"

    def pooled(sel, k):
        c = cnt(sel, k)
        t = len(sel)
        return " | ".join(f"{n} ({fmt_pct(n, t)})" for n in c)

    md = ("# EXPLORATORY: S3 four-class verdict on the original 100 tasks vs the full W3 task set\n\n"
          "**Exploratory. Not pre-registered. Descriptive only; it feeds no gate, verdict or hypothesis.**\n"
          "Made 2026-11-14 from existing data only (no new runs), after the Phase 2 analysis had been seen.\n"
          "Code state: tag pre-analysis-v2.2, commit 8e68388. Script: `scripts/exploratory/s3_w3_tasks.py` (added later; rounding-safe gate comparisons).\n\n"
          "## What was computed\n\n"
          "For bfcl_simple and bfcl_multiple (synthetic is not extended in W3), protocols D and R, all 10 adjacent pairs\n"
          "(20 decisions per protocol, 40 in total), the S3 class under two task sets:\n\n"
          "- (a) the original 100 tasks (the W3 records restricted to the original task ids);\n"
          f"- (b) the full W3 task set: {n_tasks['bfcl_simple'][0][1]} tasks for bfcl_simple, {n_tasks['bfcl_multiple'][0][1]} tasks for bfcl_multiple.\n\n"
          "Classes are the S3 rules (delta = 0.05): harmful / beneficial = the pre-registered CI-gate label (`label_ci`);\n"
          "neutral = the 90% interval entirely inside [-0.05, +0.05]; inconclusive = everything else. Intervals come from the\n"
          "task-level bootstrap (B = 10,000, seed 1234). Both protocols use the CI-based classes, as in S3. As a check, the\n"
          f"(a) classes reproduce the saved S3 classes of the main analysis for all 40 decisions ({mismatch} mismatches).\n\n"
          "## Class shares, side by side (counts of decisions)\n\n"
          "| Protocol | Suite | Task set | Harmful | Neutral | Beneficial | Inconclusive |\n|---|---|---|---|---|---|---|\n")
    for proto in ("D", "R"):
        for suite in suites:
            sel = [r for r in data if r["protocol"] == proto and r["suite"] == suite]
            for k, label in (("orig", f"original ({n_tasks[suite][0][0]})"), ("full", f"full ({n_tasks[suite][0][1]})")):
                md += f"| {proto} | {suite} | {label} | " + " | ".join(str(x) for x in cnt(sel, k)) + " |\n"
        sel = [r for r in data if r["protocol"] == proto]
        for k, label in (("orig", "original"), ("full", "full")):
            md += f"| {proto} | both suites ({len(sel)}) | {label} | {pooled(sel, k)} |\n"
    for k, label in (("orig", "original"), ("full", "full")):
        md += f"| D and R | both suites ({len(data)}) | {label} | {pooled(data, k)} |\n"
    moves = [r for r in data if r["orig"] == "inconclusive" and r["full"] != "inconclusive"]
    inc_all = [r for r in data if r["orig"] == "inconclusive"]
    into_inc = [r for r in data if r["orig"] != "inconclusive" and r["full"] == "inconclusive"]
    other = [r for r in data if r["orig"] != r["full"] and r["orig"] != "inconclusive" and r["full"] != "inconclusive"]
    byp = {p: (sum(1 for r in moves if r["protocol"] == p), sum(1 for r in inc_all if r["protocol"] == p)) for p in ("D", "R")}
    md += (f"\n## Decisions that move out of \"inconclusive\"\n\n"
           f"{len(moves)} of the {len(inc_all)} inconclusive decisions ({100 * len(moves) / len(inc_all):.0f}%) get a definite class on the full task set: "
           f"D {byp['D'][0]} of {byp['D'][1]}, R {byp['R'][0]} of {byp['R'][1]}. "
           + ("No decision moves\ninto \"inconclusive\", and no harmful, neutral or beneficial decision changes class.\n\n" if not into_inc and not other
              else f"{len(into_inc)} decisions move into \"inconclusive\" and {len(other)} change between definite classes.\n\n")
           + "| Protocol | Suite | Pair | Original -> full | Stress diff, original -> full |\n|---|---|---|---|---|\n")
    for r in moves:
        md += f"| {r['protocol']} | {r['suite']} | {r['pair'].replace('->', ' -> ')} | {r['orig']} -> {r['full']} | {r['orig_diff']:+.3f} -> {r['full_diff']:+.3f} |\n"
    md += "\n" + static("s3_w3_moves_note") + static("s3_w3_caveats")
    (out / "EXPLORATORY_S3_W3_tasks.md").write_text(md, encoding="utf-8")
    return ["EXPLORATORY_S3_W3_tasks.md"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
