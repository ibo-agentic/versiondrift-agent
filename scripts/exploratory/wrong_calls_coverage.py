"""EXPLORATORY_wrong_calls_coverage.md (+ CSV): a check of the wrong-call analysis (EXPLORATORY_wrong_calls.md).

    python -m scripts.exploratory.wrong_calls_coverage --out <folder>

For 1, 3, 5 and 10 trials per call, forced (point gate, must say harmful / neutral / beneficial) and inconclusive-allowed (the S3
four-class rule on the pooled trials), protocols D and R: scored reference decisions, calls, wrong, definite calls, coverage, wrong rate
over all calls and over definite calls, serious errors, with 95% intervals from a bootstrap over upgrade pairs (B = 10,000, seed 1234).
Also: the paired difference "3 trials + inconclusive" minus "10 trials forced"; a matched-coverage baseline (10-trial forced verdicts that
abstain on the decisions closest to the +/-0.05 gate); and how the reference verdicts are built, with a sensitivity check that drops the
trial the reference shares with the main run.
"""

from __future__ import annotations

import csv
from collections import defaultdict

import numpy as np

from vdanalysis.phase2.addendum.data import make_arrays
from vdanalysis.phase2.addendum.s3_fourclass import interval

from ._common import ADDENDUM_DIR, BOOT_REPS, DELTA, SEED, SEPARATE_PAIR, ci_gate, classify, load_phase2, parse_out, point_label, rd, static

GROUPS = {1: [[t] for t in range(10)], 3: [[0, 1, 2], [3, 4, 5], [6, 7, 8]], 5: [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]], 10: [list(range(10))]}
FILTERS = (("all 30 decisions", lambda pair: True), ("without qwen25->qwen3", lambda pair: pair != SEPARATE_PAIR))


class Sub:
    """A run restricted to some trials (only .keys is used by make_arrays)."""
    def __init__(self, run, trials):
        self.keys = {k: v for k, v in run.keys.items() if k[4] in trials}


def four_class(old, new, trials, stress):
    a = make_arrays(Sub(old, set(trials)), Sub(new, set(trials)), stress)
    point = a.diff()
    lo95, hi95 = interval(a, 0.95)
    lo90, hi90 = interval(a, 0.90)
    return point, classify(point, lo90, hi90, ci_gate(point, lo95, hi95, DELTA), DELTA)


def kind(call, ref):
    if call == "inconclusive":
        return "inconclusive"
    if call == ref:
        return "right"
    return "serious" if {call, ref} == {"harmful", "beneficial"} else "mild"


def run(out):
    cfg, an, cx, flips = load_phase2()
    pairs = [(cfg.pair_name(p), p["old"], p["new"]) for p in cfg.pairs]
    saved = {(r["protocol"], r["pair"], r["suite"]): r["class4"] for r in csv.DictReader(open(ADDENDUM_DIR / "s3_classes.csv"))}

    # ---------------------------------------------------------------- calls and references per decision
    dec = {}
    checks = defaultdict(int)
    for proto in ("D", "R"):
        for pair, old, new in pairs:
            for suite in cfg.suites:
                ro, rn = an.run_for(proto, old, suite), an.run_for(proto, new, suite)
                ao, aa = an.run_for(proto + "_AA2", old, suite), an.run_for(proto + "_AA2", new, suite)
                d = {"forced": {}, "inc": {}, "diff": {}}
                for n, groups in GROUPS.items():
                    res = [four_class(ro, rn, g, cfg.stress) for g in groups]
                    d["diff"][n] = [p for p, _ in res]
                    d["forced"][n] = [point_label(p) for p, _ in res]
                    d["inc"][n] = [c for _, c in res]
                ref_pt, ref10 = four_class(ao, aa, range(10), cfg.stress)
                _, ref19 = four_class(ao, aa, range(1, 10), cfg.stress)
                d["ref"] = saved[(proto + "_AA2", pair, suite)]
                d["ref_recomputed"] = ref10
                d["ref_no_greedy"] = ref19
                d["main_saved"] = saved[(proto, pair, suite)]
                checks[f"{proto}: reference recomputed = saved S3 class"] += ref10 == d["ref"]
                checks[f"{proto}: 10-trial inconclusive-allowed recomputed = saved S3 class"] += d["inc"][10][0] == d["main_saved"]
                dec[(proto, pair, suite)] = d
        print("calls done", proto, flush=True)

    # greedy-trial overlap: main trial 0 vs reference-arm trial 0, record by record
    overlap = defaultdict(lambda: [0, 0])
    for proto in ("D", "R"):
        for model in sorted({m for _, o, n in pairs for m in (o, n)}):
            for suite in cfg.suites:
                a, b = an.run_for(proto, model, suite), an.run_for(proto + "_AA2", model, suite)
                for k, v in a.keys.items():
                    if k[1] in cfg.stress and k in b.keys:
                        g = "greedy (trial 0)" if k[4] == 0 else "sampled (trials 1-9)"
                        overlap[(proto, g)][0] += 1
                        overlap[(proto, g)][1] += b.keys[k][0] == v[0]

    # ---------------------------------------------------------------- per-pair tallies and pair bootstrap
    pair_names = [p for p, _, _ in pairs]
    rng = np.random.default_rng(SEED)
    draws = {}
    for tag, flt in FILTERS:
        P = [p for p in pair_names if flt(p)]
        idx = rng.integers(0, len(P), size=(BOOT_REPS, len(P)))
        M = np.zeros((BOOT_REPS, len(P)))
        for j in range(len(P)):
            M[:, j] = (idx == j).sum(axis=1)
        draws[tag] = (P, M)

    def tally(proto, flt, calls_of, ref_key="ref"):
        """Per pair: [calls, wrong, definite, serious] over decisions whose reference is definite."""
        t = defaultdict(lambda: np.zeros(4))
        nref = 0
        for (p, pair, suite), d in dec.items():
            if p != proto or not flt(pair) or d[ref_key] == "inconclusive":
                continue
            nref += 1
            for c in calls_of(d):
                k = kind(c, d[ref_key])
                t[pair] += [1, k in ("mild", "serious"), k != "inconclusive", k == "serious"]
        return t, nref

    def ci(tag, t, num, den):
        P, M = draws[tag]
        A = np.array([t[p] if p in t else np.zeros(4) for p in P])
        n, dd = M @ A[:, num], M @ A[:, den]
        r = np.where(dd > 0, n / np.where(dd > 0, dd, 1), np.nan)
        return np.nanpercentile(r, 2.5), np.nanpercentile(r, 97.5), r

    VERS = [(f"{n} trial{'s' if n > 1 else ''}, {'inconclusive allowed' if inc else 'forced'}", n, inc) for n in (1, 3, 5, 10) for inc in (False, True)]
    rows, md_tables = [], {}
    for proto in ("D", "R"):
        for tag, flt in FILTERS:
            lines = []
            for name, n, inc in VERS:
                t, nref = tally(proto, flt, lambda d, n=n, inc=inc: d["inc" if inc else "forced"][n])
                S = sum(t.values())
                calls, wrong, definite, serious = (int(x) for x in S)
                lo_a, hi_a, _ = ci(tag, t, 1, 0)
                lo_d, hi_d, _ = ci(tag, t, 1, 2)
                lo_c, hi_c, _ = ci(tag, t, 2, 0)
                row = {"protocol": proto, "decisions": tag, "version": name, "trials_per_call": n, "inconclusive_allowed": int(inc),
                       "reference_decisions": nref, "calls": calls, "definite_calls": definite, "coverage": definite / calls,
                       "coverage_ci95": f"{lo_c:.3f} to {hi_c:.3f}", "wrong": wrong, "wrong_rate_all_calls": wrong / calls,
                       "wrong_all_ci95": f"{lo_a:.3f} to {hi_a:.3f}", "wrong_rate_definite_calls": wrong / definite if definite else float("nan"),
                       "wrong_definite_ci95": f"{lo_d:.3f} to {hi_d:.3f}", "serious": serious}
                rows.append(row)
                lines.append(f"| {name} | {nref} | {calls} | {definite} | {100 * definite / calls:.1f}% [{100 * lo_c:.1f}, {100 * hi_c:.1f}] | {wrong} | "
                             f"**{100 * wrong / calls:.1f}%** [{100 * lo_a:.1f}, {100 * hi_a:.1f}] | "
                             f"{(100 * wrong / definite) if definite else float('nan'):.1f}% [{100 * lo_d:.1f}, {100 * hi_d:.1f}] | {serious} |")
            md_tables[(proto, tag)] = lines

    # ---------------------------------------------------------------- paired difference: 3 + inconclusive minus 10 forced
    paired = {}
    for proto in ("D", "R"):
        for tag, flt in FILTERS:
            t3, _ = tally(proto, flt, lambda d: d["inc"][3])
            t10, _ = tally(proto, flt, lambda d: d["forced"][10])
            res = {}
            for label, num, den in (("over all calls", 1, 0), ("over definite calls", 1, 2)):
                _, _, r3 = ci(tag, t3, num, den)
                _, _, r10 = ci(tag, t10, num, den)
                s3, s10 = sum(t3.values()), sum(t10.values())
                point = s3[num] / s3[den] - s10[num] / s10[den]
                dd = r3 - r10
                res[label] = (point, np.nanpercentile(dd, 2.5), np.nanpercentile(dd, 97.5), float(np.nanmean(dd >= 0)))
            paired[(proto, tag)] = res

    # ---------------------------------------------------------------- matched coverage: 10-trial forced, abstain closest to the gate
    matched = {}
    for proto in ("D", "R"):
        for tag, flt in FILTERS:
            sel = [(k, d) for k, d in dec.items() if k[0] == proto and flt(k[1]) and d["ref"] != "inconclusive"]
            for target in ("3 trials, inconclusive allowed", "10 trials, inconclusive allowed"):
                r = next(x for x in rows if x["protocol"] == proto and x["decisions"] == tag and x["version"] == target)
                share_abstain = 1 - r["coverage"]
                m = int(round(share_abstain * len(sel)))
                dist = sorted(sel, key=lambda kd: abs(abs(rd(kd[1]["diff"][10][0])) - DELTA))
                abstain = {kd[0] for kd in dist[:m]}
                t = defaultdict(lambda: np.zeros(4))
                for k, d in sel:
                    c = "inconclusive" if k in abstain else d["forced"][10][0]
                    kk = kind(c, d["ref"])
                    t[k[1]] += [1, kk in ("mild", "serious"), kk != "inconclusive", kk == "serious"]
                S = sum(t.values())
                lo_d, hi_d, _ = ci(tag, t, 1, 2)
                lo_a, hi_a, _ = ci(tag, t, 1, 0)
                matched[(proto, tag, target)] = {"abstain": m, "of": len(sel), "share_abstain_target": share_abstain, "wrong": int(S[1]),
                                                 "definite": int(S[2]), "calls": int(S[0]), "serious": int(S[3]),
                                                 "wrong_def": S[1] / S[2] if S[2] else float("nan"), "ci_def": (lo_d, hi_d),
                                                 "wrong_all": S[1] / S[0], "ci_all": (lo_a, hi_a),
                                                 "target_wrong_def": r["wrong_rate_definite_calls"], "target_wrong_all": r["wrong_rate_all_calls"]}

    # ---------------------------------------------------------------- sensitivity: reference without the shared greedy trial
    sens = {}
    for proto in ("D", "R"):
        for tag, flt in FILTERS:
            for name, n, inc in [("1 trial, forced", 1, False), ("3 trials, inconclusive allowed", 3, True), ("10 trials, forced", 10, False),
                                 ("10 trials, inconclusive allowed", 10, True)]:
                t, nref = tally(proto, flt, lambda d, n=n, inc=inc: d["inc" if inc else "forced"][n], ref_key="ref_no_greedy")
                S = sum(t.values())
                sens[(proto, tag, name)] = (nref, int(S[0]), int(S[1]), int(S[2]))
            ref_changes = sum(1 for k, d in dec.items() if k[0] == proto and flt(k[1]) and d["ref"] != d["ref_no_greedy"])
            sens[(proto, tag, "ref_changes")] = ref_changes

    # ---------------------------------------------------------------- CSV
    with open(out / "EXPLORATORY_wrong_calls_coverage.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()})

    # ---------------------------------------------------------------- markdown
    md = ["**EXPLORATORY, post hoc. Not pre-registered. Existing data only, no reruns; descriptive; feeds no gate, verdict or hypothesis.** "
          "Analysis state: tag pre-analysis-v2.3 (commit 73a9017). A check of `EXPLORATORY_wrong_calls.md`. Script: `scripts/exploratory/wrong_calls_coverage.py`.\n",
          "# Wrong calls vs coverage: a check of the wrong-call analysis\n",
          "## 1. How the reference verdicts are built, and what they share with the scored calls\n",
          "- **Reference** for a decision (pair x suite) under protocol P = the study's four-class verdict (S3) of the **A/A arm** P_AA2 (D_AA2 or R_AA2): "
          "both models of the pair, all 10 trials of the A/A arm, stress conditions, CI gate (95%) for harmful/beneficial, neutral if the 90% interval lies inside "
          "+/-0.05, otherwise inconclusive (task-level bootstrap, B = 10,000, seed 1234). Read from `analysis_out_v3/addendum/s3_classes.csv`; "
          f"recomputed here for a check (matches: " + "; ".join(f"{k} {v}/30" for k, v in checks.items() if "reference" in k) + "). "
          "Decisions whose reference is inconclusive are left out of every rate.\n"
          "- **Scored calls** come from the **main arm** P (trials 0-9: Phase 1 trials 0-2 + Phase 2 trials 3-9 on the laptop).\n"
          "- **What the A/A arm shares with the main arm:** the same models, the same 100 tasks per suite and the same prompts (run seed 1234), "
          "and the same temperatures. Only the trial seeds differ (main 1234-1243, A/A 5678-5687). **Trial 0 is greedy (temperature 0) in both arms**, "
          "and greedy decoding does not depend on the trial seed, so trial 0 of the A/A arm repeats trial 0 of the main arm. Record by record (stress conditions, "
          "both models of every pair, score equal in the two arms):\n",
          "| Protocol | Trial | Records compared | Same score in main and A/A arm |\n|---|---|---|---|"]
    for (proto, g), (n, s) in sorted(overlap.items()):
        md.append(f"| {proto} | {g} | {n} | {s} ({100 * s / n:.1f}%) |")
    md.append("\n- **So the overlap is:** every scored call that includes trial 0 (the 1-trial call for trial 0, the 3-trial group 0-2, the 5-trial group 0-4, "
              "and every 10-trial call) shares that trial's outputs with the reference; the sampled trials are different draws. The task sample and the prompts are "
              "shared by everything, so task-sampling error is common to the scored calls and the reference: the reference measures agreement with another run "
              "on the same tasks, not with the models' quality on new tasks.\n")
    md.append("- **Sensitivity (reference without the shared greedy trial):** the reference recomputed from A/A trials 1-9 only changes the reference class of " +
              "; ".join(f"{p} {sens[(p, 'all 30 decisions', 'ref_changes')]} of 30" for p in ("D", "R")) + " decisions. Wrong calls against it (all 30 decisions):\n")
    md.append("| Protocol | Version | Reference decisions | Calls | Wrong | Wrong share of calls | Same, with the 10-trial reference |\n|---|---|---|---|---|---|---|")
    for proto in ("D", "R"):
        for name in ("1 trial, forced", "3 trials, inconclusive allowed", "10 trials, forced", "10 trials, inconclusive allowed"):
            nref, calls, wrong, definite = sens[(proto, "all 30 decisions", name)]
            r = next(x for x in rows if x["protocol"] == proto and x["decisions"] == "all 30 decisions" and x["version"] == name)
            md.append(f"| {proto} | {name} | {nref} | {calls} | {wrong} | {100 * wrong / calls:.1f}% | {100 * r['wrong_rate_all_calls']:.1f}% ({r['wrong']} of {r['calls']}) |")
    md.append("")

    md.append("## 2. Wrong calls by trials per call, forced vs inconclusive allowed\n")
    md.append("Calls per decision: 10 (1 trial: each trial alone), 3 (3 trials: groups 0-2, 3-5, 6-8), 2 (5 trials: 0-4, 5-9), 1 (10 trials). *Forced* = point gate "
              "+/-0.05 on the pooled trials. *Inconclusive allowed* = the S3 four-class rule on the pooled trials (task bootstrap, B = 10,000, seed 1234). "
              "Coverage = definite calls / calls. Wrong = a definite call that differs from the reference; serious = harmful vs beneficial. "
              "Brackets: 95% percentile interval from a bootstrap over upgrade pairs (whole pairs resampled with all their suites and calls, B = 10,000, seed 1234). "
              f"Check: the 10-trial inconclusive-allowed call reproduces the saved S3 class of the main run in " +
              "; ".join(f"{k.split(':')[0]} {v}/30" for k, v in checks.items() if "10-trial" in k) + " decisions.\n")
    for proto in ("D", "R"):
        for tag, _ in FILTERS:
            md.append(f"### {proto}, {tag}\n")
            md.append("| Version | Reference decisions | Calls | Definite calls | Coverage | Wrong | Wrong / all calls | Wrong / definite calls | Serious |\n|---|---|---|---|---|---|---|---|---|")
            md.extend(md_tables[(proto, tag)])
            md.append("")

    md.append("## 3. Paired difference: 3 trials + inconclusive minus 10 trials forced\n")
    md.append("Same bootstrap replicates (pairs resampled once, both methods scored on the same resample). Negative = 3 trials + inconclusive makes fewer wrong calls. "
              "P(diff >= 0) = share of replicates in which the 3-trial method is not better.\n")
    md.append("| Protocol | Decisions | Rate | Difference (pts) | 95% CI (pts) | P(diff >= 0) |\n|---|---|---|---|---|---|")
    for (proto, tag), res in paired.items():
        for label, (pt, lo, hi, p) in res.items():
            md.append(f"| {proto} | {tag} | wrong {label} | {100 * pt:+.1f} | {100 * lo:+.1f} to {100 * hi:+.1f} | {p:.3f} |")
    md.append("")

    md.append("## 4. Matched-coverage baseline\n")
    md.append("The 10-trial forced verdict is made to abstain on the same share of decisions as the method it is compared with, choosing the decisions whose "
              "10-trial stress diff lies closest to the +/-0.05 gate (smallest ||diff| - 0.05|). Then its wrong rate among the calls it still makes is compared with the "
              "method's wrong rate among its definite calls.\n")
    md.append("| Protocol | Decisions | Matched to | Abstains on | 10-trial forced, matched: wrong / definite | Method: wrong / definite |\n|---|---|---|---|---|---|")
    for (proto, tag, target), m in matched.items():
        md.append(f"| {proto} | {tag} | {target} ({100 * m['share_abstain_target']:.1f}% inconclusive) | {m['abstain']} of {m['of']} | "
                  f"{m['wrong']} / {m['definite']} = **{100 * m['wrong_def']:.1f}%** [{100 * m['ci_def'][0]:.1f}, {100 * m['ci_def'][1]:.1f}] | "
                  f"**{100 * m['target_wrong_def']:.1f}%** |")
    md.append("")
    md.append(static("wrong_calls_coverage_summary"))
    (out / "EXPLORATORY_wrong_calls_coverage.md").write_text("\n".join(md), encoding="utf-8")
    return ["EXPLORATORY_wrong_calls_coverage.md", "EXPLORATORY_wrong_calls_coverage.csv"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
