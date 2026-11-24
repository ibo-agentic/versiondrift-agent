"""Part 2 of EXPLORATORY_wrong_calls: more trials per call (3, 5, 10 pooled), 3 trials + inconclusive, the dropped decisions.

Called by wrong_calls.py after part 1; extends the decisions CSV, writes the summary CSV and returns the markdown section."""

from __future__ import annotations

import sys, json, csv
import numpy as np
from collections import Counter
from pathlib import Path
from vdanalysis.phase2.addendum.data import make_arrays
from vdanalysis.phase2.addendum.s3_fourclass import interval
from ._common import ADDENDUM_DIR, ci_gate, classify, load_phase2, point_label


def run(outdir):
    OUT = outdir
    cfg, an, cx, flips = load_phase2()
    SEP = "qwen25->qwen3"
    DELTA = 0.05
    pairs = [(cfg.pair_name(p), p["old"], p["new"]) for p in cfg.pairs]
    decisions = [(n, o, nw, s) for (n, o, nw) in pairs for s in cfg.suites]
    cls = {(r["protocol"], r["pair"], r["suite"]): r["class4"] for r in csv.DictReader(open(ADDENDUM_DIR / "s3_classes.csv"))}


    class Sub:
        """A run restricted to some trials (only .keys is used by make_arrays)."""
        def __init__(self, run, trials):
            self.keys = {k: v for k, v in run.keys.items() if k[4] in trials}


    label_of = point_label        # rounding-safe


    GROUPS = {"1": [[t] for t in range(10)], "3": [[0, 1, 2], [3, 4, 5], [6, 7, 8]], "5": [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]], "10": [list(range(10))]}
    res = {}                                          # (proto, pair, suite) -> dict of call lists
    for proto in ("D", "R"):
        for (pair, old, new, suite) in decisions:
            ro, rn = an.run_for(proto, old, suite), an.run_for(proto, new, suite)
            d = {}
            for k, groups in GROUPS.items():
                diffs = []
                for g in groups:
                    a = make_arrays(Sub(ro, set(g)), Sub(rn, set(g)), cfg.stress)
                    diffs.append(a.diff())
                d[f"naive{k}"] = [label_of(x) for x in diffs]
                d[f"diff{k}"] = [round(float(x), 4) for x in diffs]
            cal3 = []
            for g in GROUPS["3"]:
                a = make_arrays(Sub(ro, set(g)), Sub(rn, set(g)), cfg.stress)
                lo95, hi95 = interval(a, 0.95)
                lo90, hi90 = interval(a, 0.90)
                point = a.diff()
                cal3.append(classify(point, lo90, hi90, ci_gate(point, lo95, hi95, DELTA), DELTA))
            d["cal3"] = cal3
            d["reference"] = cls[(proto + "_AA2", pair, suite)]
            d["calibrated10"] = cls[(proto, pair, suite)]
            res[(proto, pair, suite)] = d
        print("done", proto, flush=True)

    # cross-check the single-trial calls against the earlier CSV
    old_rows = list(csv.DictReader(open(OUT / "EXPLORATORY_wrong_calls_decisions.csv", encoding="utf-8")))
    mism = 0
    for r in old_rows:
        calls = [r[f"naive_call_trial{t}"] for t in range(10)]
        if calls != res[(r["protocol"], r["upgrade"], r["suite"])]["naive1"]:
            mism += 1
    print("single-trial cross-check mismatching decisions:", mism)


    def kind(call, ref):
        if call == ref:
            return None
        return "serious" if {call, ref} == {"harmful", "beneficial"} else "mild"


    def summ(proto, key, flt, allow_inc):
        n = w = s = m = inc = 0
        nd = 0
        for (p, pair, suite), d in res.items():
            if p != proto or not flt(pair) or d["reference"] == "inconclusive":
                continue
            nd += 1
            for c in d[key]:
                n += 1
                if c == "inconclusive":
                    inc += 1
                    continue
                k = kind(c, d["reference"])
                w += k is not None; s += k == "serious"; m += k == "mild"
        return {"decisions": nd, "calls": n, "wrong": w, "serious": s, "mild": m, "inconclusive": inc}


    def pc(a, b):
        return f"{100 * a / b:.1f}%" if b else "n/a"


    VERS = [("naive1", "1 trial, naive (previous section)", False), ("naive3", "3 trials pooled, naive", False), ("naive5", "5 trials pooled, naive", False),
            ("naive10", "10 trials pooled, naive (point gate on all trials)", False), ("cal3", "3 trials + CI gate + 'inconclusive' allowed", True),
            ("calibrated10", "10 trials + CI gate + 'inconclusive' allowed (the calibrated method)", True)]
    for (p, pair, suite), d in res.items():
        d["calibrated10"] = [d["calibrated10"]]
    FILTERS = [("all 30 decisions", lambda pair: True), ("without qwen25->qwen3", lambda pair: pair != SEP)]
    SUMMARY = []
    md = ["\n## More runs vs. the method\n",
          "**EXPLORATORY, post hoc, existing data only.** Same A/A reference and the same scored decisions as above (decisions whose reference is inconclusive are left out of every error rate). "
          "All versions use the main run. 'Naive' = point gate at +/-0.05, forced to say harmful, neutral or beneficial. Groups of trials are disjoint and pooled (all records of the trials in the group, equal weight): "
          "3 trials = trials 0-2, 3-5, 6-8 (trial 9 unused; 3 calls per decision); 5 trials = 0-4 and 5-9 (2 calls); 10 trials = all (1 call). "
          "'3 trials + inconclusive' applies the study's four-class verdict (95% CI gate for harmful/beneficial, 90% equivalence test for neutral, otherwise inconclusive; task-level bootstrap, B = 10,000, seed 1234) to each group of 3 trials. "
          "Shares are over calls (decisions x calls per decision); serious = harmful and beneficial swapped, mild = neutral against harmful or beneficial.\n"]
    for proto in ("D", "R"):
        for tag, flt in FILTERS:
            md.append(f"### {proto}: {tag}\n")
            md.append("| Version | Trials per call | Calls | Wrong | Serious | Mild | Inconclusive | Wrong among its definite calls |\n|---|---|---|---|---|---|---|---|")
            for key, name, allow in VERS:
                s = summ(proto, key, flt, allow)
                tp = {"naive1": "1", "naive3": "3", "naive5": "5", "naive10": "10", "cal3": "3", "calibrated10": "10"}[key]
                definite = s["calls"] - s["inconclusive"]
                md.append(f"| {name} | {tp} | {s['calls']} ({s['decisions']} decisions) | **{pc(s['wrong'], s['calls'])}** ({s['wrong']}) | {pc(s['serious'], s['calls'])} ({s['serious']}) | "
                          f"{pc(s['mild'], s['calls'])} ({s['mild']}) | {pc(s['inconclusive'], s['calls']) if allow else 'not allowed'}{' (' + str(s['inconclusive']) + ')' if allow else ''} | "
                          f"{pc(s['wrong'], definite)} of {definite} |")
                SUMMARY.append({"protocol": proto, "decisions": tag, "version": name, "trials_per_call": tp, "calls": s["calls"], "scored_decisions": s["decisions"],
                                "wrong": s["wrong"], "serious": s["serious"], "mild": s["mild"], "inconclusive": s["inconclusive"] if allow else ""})
            md.append("")
    # dropped decisions
    md.append("### The dropped decisions (reference inconclusive) and what a one-trial test says about them\n")
    tot = Counter()
    for proto in ("D", "R"):
        drops = [(k, d) for k, d in res.items() if k[0] == proto and d["reference"] == "inconclusive"]
        md.append(f"**{proto}: {len(drops)} of 30 decisions have an inconclusive reference.**\n")
        md.append("| Upgrade | Suite | 10-trial calibrated verdict | One-trial calls (of 10): harmful / neutral / beneficial |\n|---|---|---|---|")
        h = b = n_ = 0
        for (p, pair, suite), d in drops:
            c = Counter(d["naive1"])
            h += c["harmful"]; b += c["beneficial"]; n_ += c["neutral"]
            md.append(f"| {pair} | {suite} | {d['calibrated10'][0]} | {c['harmful']} / {c['neutral']} / {c['beneficial']} |")
        tot[proto] = (h, b, n_)
        allc = h + b + n_
        md.append(f"\nOver these {len(drops)} decisions ({allc} one-trial calls): **{pc(h + b, allc)} of the calls said harmful or beneficial anyway** ({h} harmful, {b} beneficial); {pc(n_, allc)} said neutral. "
                  f"For comparison, the 10-trial calibrated method said 'inconclusive' on {sum(1 for _, d in drops if d['calibrated10'][0] == 'inconclusive')} of the {len(drops)}.\n")
    more_md = "\n".join(md)
    # CSVs: summary + extend the decisions CSV
    with open(OUT / "EXPLORATORY_wrong_calls_summary.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(SUMMARY[0]))
        w.writeheader(); w.writerows(SUMMARY)
    cols_new = ["naive_3trial_calls", "naive_5trial_calls", "naive_10trial_call", "inconclusive_allowed_3trial_calls"]
    with open(OUT / "EXPLORATORY_wrong_calls_decisions.csv", "w", encoding="utf-8", newline="") as fh:
        fn = list(old_rows[0].keys())
        fn = [c for c in fn if c not in cols_new] + cols_new
        w = csv.DictWriter(fh, fieldnames=fn)
        w.writeheader()
        for r in old_rows:
            d = res[(r["protocol"], r["upgrade"], r["suite"])]
            r["naive_3trial_calls"] = " | ".join(d["naive3"]); r["naive_5trial_calls"] = " | ".join(d["naive5"])
            r["naive_10trial_call"] = d["naive10"][0]; r["inconclusive_allowed_3trial_calls"] = " | ".join(d["cal3"])
            for t in range(10):
                r[f"naive_call_trial{t}"] = d["naive1"][t]                # same values, boundary-safe
            w.writerow(r)

    return more_md
