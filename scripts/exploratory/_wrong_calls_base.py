"""Part 1 of EXPLORATORY_wrong_calls: reference verdicts (A/A arms), one-trial naive calls, calibrated verdicts, broken-output check.

Called by wrong_calls.py; writes the decisions and bad-output-share CSVs and returns the markdown text."""

from __future__ import annotations

import sys, json, csv
import numpy as np
from collections import defaultdict, Counter
from itertools import combinations
from pathlib import Path
from vdanalysis.loader import record_score
from vdanalysis.phase2.config import load_phase2_config
from vdanalysis.phase2.merge import MergedStore
from ._common import ADDENDUM_DIR, CONFIG, point_label


def run(outdir):
    OUT = outdir
    cfg = load_phase2_config(str(CONFIG))
    store = MergedStore(cfg)
    stress = list(cfg.stress)
    SEP = "qwen25->qwen3"
    pairs = [(cfg.pair_name(p), p["old"], p["new"]) for p in cfg.pairs]
    decisions = [(n, o, nw, s) for (n, o, nw) in pairs for s in cfg.suites]
    DELTA = 0.05
    THRESH = (0.05, 0.10, 0.20)

    # ---- classes from the addendum (S3): reference arms and main runs
    cls = {}
    for r in csv.DictReader(open(ADDENDUM_DIR / "s3_classes.csv")):
        cls[(r["protocol"], r["pair"], r["suite"])] = r["class4"]

    # ---- per (protocol, model, suite): per-trial condition means, and output flags
    trial_mat = {}
    flags = {}
    for proto in ("D", "R"):
        for model in sorted({m for _, o, n in pairs for m in (o, n)}):
            for suite in cfg.suites:
                s = defaultdict(float); c = defaultdict(int)
                n = bad = trunc = either = 0
                for part, spec in store.part_dirs(proto, model, suite):
                    run_dir = store._find_run_dir(part)
                    with open(run_dir / "parsed_results.jsonl", encoding="utf-8") as fp, open(run_dir / "raw_outputs.jsonl", encoding="utf-8") as fr:
                        for lp, lr in zip(fp, fr):
                            p = json.loads(lp)
                            if p["condition"] not in stress:
                                continue
                            r = json.loads(lr)
                            t = int(p.get("trial_index", 0)) + spec.trial_offset
                            s[(t, p["condition"])] += record_score(p) >= 1.0
                            c[(t, p["condition"])] += 1
                            unp = not p["metrics"].get("parse_ok", False)
                            tr = bool(r.get("truncated"))
                            n += 1; bad += unp; trunc += tr; either += (unp or tr)
                trial_mat[(proto, model, suite)] = np.array([[s[(t, cond)] / c[(t, cond)] for cond in stress] for t in range(10)])
                flags[(proto, model, suite)] = {"n": n, "unparsed": bad / n, "truncated": trunc / n, "either": either / n}


    label_of = point_label        # rounding-safe (an exact +/-0.05 is neutral)


    def err_kind(call, ref):
        """call: harmful/neutral/beneficial; ref: definite class. None = agree."""
        if call == ref:
            return None
        return "serious" if {call, ref} == {"harmful", "beneficial"} else "mild"


    rows = []
    for proto in ("D", "R"):
        for (pair, old, new, suite) in decisions:
            ref = cls[(proto + "_AA2", pair, suite)]
            cal = cls[(proto, pair, suite)]
            M = trial_mat[(proto, new, suite)] - trial_mat[(proto, old, suite)]      # 10 x conditions
            diffs = M.mean(axis=1)
            naive = [label_of(d) for d in diffs]
            fl = {t: max(flags[(proto, old, suite)]["either"], flags[(proto, new, suite)]["either"]) for t in THRESH}
            worst = max(flags[(proto, old, suite)]["either"], flags[(proto, new, suite)]["either"])
            rows.append({"protocol": proto, "pair": pair, "suite": suite, "reference": ref, "calibrated": cal, "naive_calls": naive,
                         "naive_diffs": [round(float(d), 4) for d in diffs], "worst_bad_share": worst,
                         "old_bad_share": flags[(proto, old, suite)]["either"], "new_bad_share": flags[(proto, new, suite)]["either"]})


    def summarize(sel):
        """sel: list of decision rows. Denominator for errors: decisions whose reference is definite."""
        out = {"n_dec": len(sel), "n_ref_definite": 0, "n_ref_inconclusive": 0, "naive_calls": 0, "naive_wrong": 0, "naive_serious": 0, "naive_mild": 0,
               "decisions_with_disagreeing_calls": 0, "pairwise_call_disagreement": [], "cal_definite": 0, "cal_wrong": 0, "cal_serious": 0, "cal_mild": 0,
               "cal_inconclusive": 0, "flag": {t: 0 for t in THRESH}, "cal_wrong_unflagged": {t: 0 for t in THRESH}, "cal_definite_unflagged": {t: 0 for t in THRESH},
               "naive_wrong_unflagged": {t: 0 for t in THRESH}, "naive_calls_unflagged": {t: 0 for t in THRESH}}
        for r in sel:
            if r["reference"] == "inconclusive":
                out["n_ref_inconclusive"] += 1
                continue
            out["n_ref_definite"] += 1
            calls = r["naive_calls"]
            kinds = [err_kind(c, r["reference"]) for c in calls]
            out["naive_calls"] += len(calls)
            out["naive_wrong"] += sum(k is not None for k in kinds)
            out["naive_serious"] += sum(k == "serious" for k in kinds)
            out["naive_mild"] += sum(k == "mild" for k in kinds)
            out["decisions_with_disagreeing_calls"] += len(set(calls)) > 1
            out["pairwise_call_disagreement"].append(np.mean([a != b for a, b in combinations(calls, 2)]))
            cal = r["calibrated"]
            if cal == "inconclusive":
                out["cal_inconclusive"] += 1
            else:
                out["cal_definite"] += 1
                k = err_kind(cal, r["reference"])
                out["cal_wrong"] += k is not None
                out["cal_serious"] += k == "serious"
                out["cal_mild"] += k == "mild"
            for t in THRESH:
                flagged = r["worst_bad_share"] > t
                out["flag"][t] += flagged
                if not flagged:
                    out["naive_calls_unflagged"][t] += len(calls)
                    out["naive_wrong_unflagged"][t] += sum(k is not None for k in kinds)
                    if cal != "inconclusive":
                        out["cal_definite_unflagged"][t] += 1
                        out["cal_wrong_unflagged"][t] += err_kind(cal, r["reference"]) is not None
        return out


    def pc(a, b):
        return f"{100 * a / b:.1f}%" if b else "n/a"


    SUM = {}
    for proto in ("D", "R"):
        for tag, flt in (("all 30 decisions", lambda r: True), ("without qwen25->qwen3 (27)", lambda r: r["pair"] != SEP)):
            SUM[(proto, tag)] = summarize([r for r in rows if r["protocol"] == proto and flt(r)])

    # CSVs
    with open(OUT / "EXPLORATORY_wrong_calls_decisions.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["protocol", "upgrade", "suite", "reference_AA_arm_verdict", "calibrated_verdict_main_run", "naive_call_trial0", "naive_call_trial1", "naive_call_trial2",
                    "naive_call_trial3", "naive_call_trial4", "naive_call_trial5", "naive_call_trial6", "naive_call_trial7", "naive_call_trial8", "naive_call_trial9",
                    "naive_calls_disagreeing_with_reference", "naive_serious", "naive_mild", "old_model_bad_output_share", "new_model_bad_output_share",
                    "flag_at_5pct", "flag_at_10pct", "flag_at_20pct"])
        for r in rows:
            ks = [err_kind(c, r["reference"]) for c in r["naive_calls"]] if r["reference"] != "inconclusive" else [None] * 10
            w.writerow([r["protocol"], r["pair"], r["suite"], r["reference"], r["calibrated"], *r["naive_calls"],
                        sum(k is not None for k in ks) if r["reference"] != "inconclusive" else "", sum(k == "serious" for k in ks), sum(k == "mild" for k in ks),
                        f"{r['old_bad_share']:.4f}", f"{r['new_bad_share']:.4f}", *[int(r["worst_bad_share"] > t) for t in THRESH]])
    with open(OUT / "EXPLORATORY_wrong_calls_bad_output_shares.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["protocol", "model", "suite", "stress_records", "unparsed_or_broken_share", "hit_token_limit_share", "either_share"])
        for (proto, model, suite), f in sorted(flags.items()):
            w.writerow([proto, model, suite, f["n"], f"{f['unparsed']:.4f}", f"{f['truncated']:.4f}", f"{f['either']:.4f}"])

    # ---- markdown
    md = ["**EXPLORATORY, post hoc. Not pre-registered. Existing data only, no reruns; descriptive.** Analysis state: tag pre-analysis-v2.3 (commit 73a9017). "
          "Stress conditions (schema_drift + fault_reporting), 10 upgrades x 3 suites = 30 decisions, protocols D and R reported separately.\n"]
    md.append("# How often does a one-run upgrade test give the wrong ship / don't-ship call?\n")
    md.append("## Definitions (what was compared with what)\n")
    md.append("- **Reference verdict ('truth').** For each decision and protocol, the verdict of the **A/A rerun arm** (D_AA2 for D, R_AA2 for R) over all 10 trials, using the pre-registered "
              "CI gate for harmful/beneficial and the 90% equivalence test (TOST, +/-0.05) for neutral, otherwise *inconclusive* (the study's four-class verdict, S3). The main runs are not used for the reference. "
              "Where the reference itself is *inconclusive* the truth is undetermined, so **those decisions are left out of every error rate** and counted separately.\n"
              "- **Naive test.** One trial of the main run (each of trials 0 to 9 on its own: 10 naive calls per decision), stress diff = new minus old model score, point gate at +/-0.05, "
              "forced to say harmful, neutral or beneficial.\n"
              "- **Error kinds.** *Serious* = harmful called beneficial or the reverse. *Mild* = neutral called harmful or beneficial, or harmful/beneficial called neutral.\n"
              "- **Calibrated method.** The main run over all 10 trials with the study's four-class verdict (S3): CI gate for harmful/beneficial, TOST for neutral, *inconclusive* allowed. "
              "'Calibrated' means the gate's error behaviour was measured on A/A reruns (false-alarm rate 4.2% for the R gate, 2.1% for the D point gate). "
              "A separate rule that additionally required |stress diff| to exceed an A/A noise bound is not used: under D that bound (the 95th percentile of |diff| over the A/A decisions, 0.040, from the F5 table of the main analysis) is below the 0.05 gate, so it would change no D verdict (not checked for R). "
              "Its verdicts are compared with the reference only where it is definite; 'wrong' = a definite call that differs from a definite reference.\n"
              "- **Broken-output check.** Per model x suite x protocol: the share of stress-condition outputs (all 10 trials) that are unparsed or broken (the scorer found no valid reply) **or** hit the token limit. "
              "A decision is flagged 'don't trust' if the share for either model is **above** the threshold (5%, 10% or 20%).\n")
    for proto in ("D", "R"):
        md.append(f"## Results, protocol {proto}\n")
        for tag in ("all 30 decisions", "without qwen25->qwen3 (27)"):
            s = SUM[(proto, tag)]
            nd = s["n_ref_definite"]
            md.append(f"### {proto}: {tag}\n")
            md.append(f"Decisions: {s['n_dec']}; reference definite: {nd}; reference inconclusive (left out): {s['n_ref_inconclusive']}.\n")
            md.append("| Method | Calls or decisions | Wrong | Serious | Mild | Inconclusive |\n|---|---|---|---|---|---|")
            md.append(f"| **Naive, one trial** | {s['naive_calls']} calls ({nd} decisions x 10 trials) | **{pc(s['naive_wrong'], s['naive_calls'])}** ({s['naive_wrong']}) | "
                      f"{pc(s['naive_serious'], s['naive_calls'])} ({s['naive_serious']}) | {pc(s['naive_mild'], s['naive_calls'])} ({s['naive_mild']}) | not allowed |")
            md.append(f"| **Calibrated, 10 trials** | {nd} decisions | **{pc(s['cal_wrong'], nd)}** ({s['cal_wrong']}; {pc(s['cal_wrong'], s['cal_definite'])} of its {s['cal_definite']} definite calls) | "
                      f"{pc(s['cal_serious'], nd)} ({s['cal_serious']}) | {pc(s['cal_mild'], nd)} ({s['cal_mild']}) | **{pc(s['cal_inconclusive'], nd)}** ({s['cal_inconclusive']}) |")
            md.append("")
            md.append(f"- **The 10 single-trial naive calls disagree with each other** for {pc(s['decisions_with_disagreeing_calls'], nd)} of the decisions ({s['decisions_with_disagreeing_calls']} of {nd}: "
                      f"not all 10 calls identical); on average {100 * float(np.mean(s['pairwise_call_disagreement'])):.1f}% of pairs of calls for the same decision differ.")
            md.append("- **Broken-output check:** decisions flagged 'don't trust' (of all decisions with a definite reference): " +
                      "; ".join(f"above {int(100 * t)}%: **{pc(s['flag'][t], nd)}** ({s['flag'][t]})" for t in THRESH) + ".")
            md.append("- After dropping the flagged decisions: calibrated wrong " +
                      "; ".join(f"at {int(100 * t)}%: {pc(s['cal_wrong_unflagged'][t], s['cal_definite_unflagged'][t])} of {s['cal_definite_unflagged'][t]} definite calls" for t in THRESH) +
                      "; naive wrong " + "; ".join(f"at {int(100 * t)}%: {pc(s['naive_wrong_unflagged'][t], s['naive_calls_unflagged'][t])} of {s['naive_calls_unflagged'][t]} calls" for t in THRESH) + ".\n")
        md.append(f"### {proto}: which decisions the broken-output check flags\n")
        md.append("| Threshold | Flagged decisions (share of old / new model outputs broken or at the limit) |\n|---|---|")
        for t in THRESH:
            fl = [r for r in rows if r["protocol"] == proto and r["worst_bad_share"] > t]
            txt = "; ".join(f"{r['pair']} / {r['suite']} ({100 * r['old_bad_share']:.0f}% / {100 * r['new_bad_share']:.0f}%)" for r in fl) or "none"
            md.append(f"| above {int(100 * t)}% ({len(fl)} of 30) | {txt} |")
        md.append("")
    md.append("## Plain-language summary\n")
    for proto in ("D", "R"):
        for tag in ("all 30 decisions", "without qwen25->qwen3 (27)"):
            s = SUM[(proto, tag)]; nd = s["n_ref_definite"]
            md.append(f"- **{proto}, {tag}:** A one-run test gave the wrong call **{pc(s['naive_wrong'], s['naive_calls'])}** of the time "
                      f"({pc(s['naive_serious'], s['naive_calls'])} serious); the calibrated method was wrong **{pc(s['cal_wrong'], nd)}** of the time and said 'inconclusive' "
                      f"**{pc(s['cal_inconclusive'], nd)}** of the time (broken-output check flags {pc(s['flag'][0.10], nd)} of decisions at a 10% threshold).")
    md.append("\n## Caveats\n")
    md.append("- The 'truth' is itself an estimate: the A/A arm is another noisy 10-trial run of the same models, so the reference can share some noise with the main run (they are separate trials, "
              "same prompts) and is inconclusive for several decisions; the error rates are errors against that reference, not against an unknowable true quality.\n"
              "- 30 decisions (27 without qwen25->qwen3), not independent (a model belongs to two upgrades; D and R use the same tasks); the 10 naive calls per decision are not independent either, "
              "so the percentages carry no confidence interval and should be read as rough.\n"
              "- The naive test is the harshest simple version (one trial, point gate, no inconclusive); a naive test that used the same 10 trials with the point gate would be the 'main run' D verdict.\n"
              "- Broken-output shares use the scorer's `parse_ok` plus the stored token-limit flag over stress conditions only; they include qwen3's long thinking that hits the 256 limit under D.\n"
              "- Files: `EXPLORATORY_wrong_calls_decisions.csv` (60 rows: reference, calibrated verdict, the 10 naive calls, errors, flags), `EXPLORATORY_wrong_calls_bad_output_shares.csv` (model x suite x protocol).\n")
    md_text = "\n".join(md)

    return md_text
