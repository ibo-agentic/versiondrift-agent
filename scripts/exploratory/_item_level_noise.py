"""'Noise check' section of EXPLORATORY_item_level_flips.md (+ three CSVs). Called by item_level_flips.py.

1. Same-model churn: each model's main arm vs its A/A arm (D vs D_AA2, R vs R_AA2) on the same stress questions, by the 10-trial majority
   and by the greedy trial; per upgrade: upgrade churn, expected same-model churn (mean of the old and the new model), excess.
2. Reconciliation of the stress diff with the majority count (mistral_v01->mistral_v02 and every decision where the two signs disagree).
3. 'Got worse' failure types split by stress condition.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict

from ._common import rd, static

SEP = "qwen25->qwen3"


def _maj(tr):
    return sum(ok for ok, _ in tr.values()) / len(tr) > 0.5


def _right(tr, basis):
    return _maj(tr) if basis == "majority" else tr[0][0]


def _churn(a, b, basis):
    keys = sorted(set(a) & set(b))
    r2w = sum(1 for k in keys if _right(a[k], basis) and not _right(b[k], basis))
    w2r = sum(1 for k in keys if _right(b[k], basis) and not _right(a[k], basis))
    return len(keys), r2w, w2r


def section(out, cfg, load, pairs, summary, reasons_cond, REASONS):
    stress = sorted(cfg.stress)
    models = sorted({m for _, o, n in pairs for m in (o, n)})
    md = ["\n## Noise check (added 2026-11-28)\n",
          "**EXPLORATORY, post hoc, existing data only.** Script: `scripts/exploratory/_item_level_noise.py` (called by `item_level_flips.py`). "
          "Files: `EXPLORATORY_item_level_flips_noise.csv`, `EXPLORATORY_item_level_flips_reconcile.csv`, `EXPLORATORY_item_level_flips_worse_by_condition.csv`.\n"]

    # ------------------------------------------------------------ 1. same-model churn
    same = {}
    noise_rows = []
    for proto in ("D", "R"):
        for model in models:
            for suite in cfg.suites:
                a, b = load(proto, model, suite), load(proto + "_AA2", model, suite)
                assert all(len(v) == 10 for v in a.values()) and all(len(v) == 10 for v in b.values()), (proto, model, suite)
                for basis in ("majority", "greedy"):
                    n, r2w, w2r = _churn(a, b, basis)
                    same[(proto, model, suite, basis)] = (n, r2w, w2r)
                    noise_rows.append({"kind": "same_model", "protocol": proto, "model_or_upgrade": model, "suite": suite, "basis": basis, "questions": n,
                                       "right_to_wrong_or_got_worse": r2w, "wrong_to_right_or_got_better": w2r, "churn": r2w + w2r,
                                       "expected_same_model_churn": "", "excess_churn": ""})
    md.append("### 1. Same-model churn: does a model 'churn' against a rerun of itself?\n")
    md.append("For every model, its main arm (D or R, trials 0-9) is compared with its A/A arm (D_AA2 or R_AA2: the same model, the same tasks and prompts, trial "
              "seeds 5678-5687) on the same 600 stress questions, with the same rule as the upgrade table: right = passed in 6 or more of 10 trials. "
              "Right->wrong and wrong->right count questions that change sides between the two arms of the **same** model; churn = their sum. "
              "For each upgrade: **expected same-model churn** = the mean of the old and the new model's same-model churn (all three suites, 600 questions); "
              "**excess** = upgrade churn minus that. The greedy-only rows use trial 0 of each arm.\n")
    md.append("**Read the greedy rows with care:** trial 0 is greedy in both arms, with the same prompts, and greedy decoding does not depend on the trial seed, "
              "so the A/A arm's trial 0 repeats the main arm's trial 0; same-model greedy churn is therefore close to zero by construction and is not a usable "
              "noise floor for a greedy comparison (see the counts).\n")
    up_rows = []
    for proto in ("D", "R"):
        for basis in ("majority", "greedy"):
            md.append(f"#### {proto}, {'10-trial majority' if basis == 'majority' else 'greedy trial only'}\n")
            md.append("| Upgrade | Upgrade churn (worse / better) | Old model same-model churn (r->w / w->r) | New model same-model churn (r->w / w->r) | "
                      "Expected same-model churn | Excess churn | Excess as share of 600 |\n|---|---|---|---|---|---|---|")
            tot = Counter()
            for name, old, new in pairs:
                srow = [s for s in summary if s["protocol"] == proto and s["pair"] == name
                        and s["basis"] == ("majority of 10 trials" if basis == "majority" else "greedy trial")]
                worse, better = sum(s["got_worse"] for s in srow), sum(s["got_better"] for s in srow)
                so = [same[(proto, old, s, basis)] for s in cfg.suites]
                sn = [same[(proto, new, s, basis)] for s in cfg.suites]
                o_r2w, o_w2r = sum(x[1] for x in so), sum(x[2] for x in so)
                n_r2w, n_w2r = sum(x[1] for x in sn), sum(x[2] for x in sn)
                exp = ((o_r2w + o_w2r) + (n_r2w + n_w2r)) / 2
                exc = worse + better - exp
                tot.update({"churn": worse + better, "exp": exp, "exc": exc})
                if name != SEP:
                    tot.update({"churn_x": worse + better, "exp_x": exp, "exc_x": exc})
                md.append(f"| {name} | {worse + better} ({worse} / {better}) | {o_r2w + o_w2r} ({o_r2w} / {o_w2r}) | {n_r2w + n_w2r} ({n_r2w} / {n_w2r}) | "
                          f"{exp:.1f} | **{exc:+.1f}** | {100 * exc / 600:+.1f}% |")
                up_rows.append({"kind": "upgrade", "protocol": proto, "model_or_upgrade": name, "suite": "all three", "basis": basis, "questions": 600,
                                "right_to_wrong_or_got_worse": worse, "wrong_to_right_or_got_better": better, "churn": worse + better,
                                "expected_same_model_churn": f"{exp:.1f}", "excess_churn": f"{exc:+.1f}"})
            md.append(f"| **All 10 upgrades** | {tot['churn']:.0f} |  |  | {tot['exp']:.1f} | **{tot['exc']:+.1f}** | {100 * tot['exc'] / 6000:+.1f}% |")
            md.append(f"| **Without qwen25->qwen3** | {tot['churn_x']:.0f} |  |  | {tot['exp_x']:.1f} | **{tot['exc_x']:+.1f}** | {100 * tot['exc_x'] / 5400:+.1f}% |\n")
    # per-model table (majority)
    md.append("#### Same-model churn per model (10-trial majority, 600 questions; D / R)\n")
    md.append("| Model | D: r->w / w->r (churn) | R: r->w / w->r (churn) |\n|---|---|---|")
    for model in models:
        cells = []
        for proto in ("D", "R"):
            r2w = sum(same[(proto, model, s, "majority")][1] for s in cfg.suites)
            w2r = sum(same[(proto, model, s, "majority")][2] for s in cfg.suites)
            cells.append(f"{r2w} / {w2r} ({r2w + w2r}, {100 * (r2w + w2r) / 600:.1f}%)")
        md.append(f"| {model} | {cells[0]} | {cells[1]} |")
    md.append("")
    with open(out / "EXPLORATORY_item_level_flips_noise.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(noise_rows[0]))
        w.writeheader()
        w.writerows(noise_rows + up_rows)

    # ------------------------------------------------------------ 2. reconcile stress diff and majority count
    rec = []
    for proto in ("D", "R"):
        for name, old, new in pairs:
            for suite in cfg.suites:
                a, b = load(proto, old, suite), load(proto, new, suite)
                keys = sorted(set(a) & set(b))
                ncond = Counter(k[1] for k in keys)
                w_q = {k: 1 / (ncond[k[1]] * len(ncond)) for k in keys}
                ko = {k: sum(ok for ok, _ in a[k].values()) for k in keys}
                kn = {k: sum(ok for ok, _ in b[k].values()) for k in keys}
                mo = {c: sum(ko[k] for k in keys if k[1] == c) / (10 * ncond[c]) for c in ncond}
                mn = {c: sum(kn[k] for k in keys if k[1] == c) / (10 * ncond[c]) for c in ncond}
                diff = sum(mn[c] - mo[c] for c in ncond) / len(ncond)
                contrib = Counter()
                cells = Counter()
                for k in keys:
                    ro, rn = ko[k] >= 6, kn[k] >= 6
                    cell = "both right" if ro and rn else "got worse" if ro else "got better" if rn else "both wrong"
                    cells[cell] += 1
                    contrib[cell] += w_q[k] * (kn[k] - ko[k]) / 10
                s = next(x for x in summary if x["protocol"] == proto and x["pair"] == name and x["suite"] == suite and x["basis"] == "majority of 10 trials")
                rec.append({"protocol": proto, "upgrade": name, "suite": suite, "stress_diff_study": s["stress_diff"], "stress_diff_recomputed": diff,
                            "old_mean_pass": sum(mo.values()) / len(mo), "new_mean_pass": sum(mn.values()) / len(mn),
                            "majority_net": cells["got better"] - cells["got worse"], "got_worse": cells["got worse"], "got_better": cells["got better"],
                            "old_ties_5of10": sum(1 for k in keys if ko[k] == 5), "new_ties_5of10": sum(1 for k in keys if kn[k] == 5),
                            "contrib_got_worse": contrib["got worse"], "contrib_got_better": contrib["got better"],
                            "contrib_both_right": contrib["both right"], "contrib_both_wrong": contrib["both wrong"],
                            "old_dist": [sum(1 for k in keys if ko[k] == i) for i in range(11)],
                            "new_dist": [sum(1 for k in keys if kn[k] == i) for i in range(11)]})
    max_dev = max(abs(r["stress_diff_recomputed"] - r["stress_diff_study"]) for r in rec)

    def disagree(d, net):
        d = rd(d)
        return (d > 0 and net < 0) or (d < 0 and net > 0)

    dis = [r for r in rec if disagree(r["stress_diff_study"], r["majority_net"])]
    md.append("### 2. Why the stress diff and the majority count can disagree\n")
    md.append("**What the stress diff measures.** For one decision (upgrade x suite) and protocol: for each stress condition, the new model's pass rate minus the "
              "old model's pass rate over all matched records (every task, every one of the 10 trials); then the plain mean of the two conditions "
              "(schema_drift and fault_reporting weigh the same). Each condition has 100 questions here, so it is the mean, over the 200 questions, of "
              "(new passes - old passes) / 10. It counts **every trial** of every question. The majority table counts only **questions that cross the "
              "6-of-10 line**; a question that moves from 9/10 to 6/10, or from 5/10 to 0/10, changes the stress diff but not the count, and a move from 6/10 to "
              "5/10 counts as a full 'got worse' while changing the stress diff by only 0.1 / 200. "
              f"(Check: recomputed from the records, the stress diff equals the study's value in all {len(rec)} decisions, largest difference {max_dev:.1e}.)\n")
    md.append("The stress diff splits exactly into the contributions of the four majority cells: contribution = sum over the cell's questions of (new passes - old passes) / 10, "
              "weighted as in the stress diff. 'Got worse' questions always contribute a negative amount and 'got better' a positive one; 'both right' and "
              "'both wrong' questions move the stress diff without moving the count.\n")

    def agg(rows):
        t = {k: sum(r[k] for r in rows) / len(rows) for k in ("stress_diff_study", "old_mean_pass", "new_mean_pass", "contrib_got_worse", "contrib_got_better",
                                                            "contrib_both_right", "contrib_both_wrong")}
        t.update({k: sum(r[k] for r in rows) for k in ("majority_net", "got_worse", "got_better", "old_ties_5of10", "new_ties_5of10")})
        t["old_dist"] = [sum(r["old_dist"][i] for r in rows) for i in range(11)]
        t["new_dist"] = [sum(r["new_dist"][i] for r in rows) for i in range(11)]
        return t

    def recon_table(title, items):
        md.append(f"#### {title}\n")
        md.append("| Protocol | Decision | Stress diff | Old / new mean pass rate | Majority: worse / better / net | Contribution to the stress diff: got worse / got better / "
                  "both right / both wrong | Ties at 5/10 (old / new) |\n|---|---|---|---|---|---|---|")
        for lab, t in items:
            md.append(f"| {lab[0]} | {lab[1]} | {t['stress_diff_study']:+.4f} | {t['old_mean_pass']:.4f} / {t['new_mean_pass']:.4f} | "
                      f"{t['got_worse']} / {t['got_better']} / {t['majority_net']:+d} | {t['contrib_got_worse']:+.4f} / {t['contrib_got_better']:+.4f} / "
                      f"{t['contrib_both_right']:+.4f} / {t['contrib_both_wrong']:+.4f} | {t['old_ties_5of10']} / {t['new_ties_5of10']} |")
        md.append("")

    m_items = []
    for proto in ("D", "R"):
        rows = [r for r in rec if r["protocol"] == proto and r["upgrade"] == "mistral_v01->mistral_v02"]
        m_items.append(((proto, "mistral_v01->mistral_v02, three suites (mean of the suites' diffs; counts summed)"), agg(rows)))
        for r in rows:
            m_items.append(((proto, f"mistral_v01->mistral_v02 / {r['suite']}"), r))
    recon_table("mistral_v01 -> mistral_v02", m_items)
    md.append("**Questions by number of passes out of 10 (mistral_v01 -> mistral_v02, three suites, 600 questions):**\n")
    md.append("| Protocol | Model | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Mean passes |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for proto in ("D", "R"):
        t = agg([r for r in rec if r["protocol"] == proto and r["upgrade"] == "mistral_v01->mistral_v02"])
        for lab, dist in (("mistral_v01 (old)", t["old_dist"]), ("mistral_v02 (new)", t["new_dist"])):
            mean = sum(i * c for i, c in enumerate(dist)) / sum(dist)
            md.append(f"| {proto} | {lab} | " + " | ".join(str(c) for c in dist) + f" | {mean:.3f} |")
    md.append("")
    recon_table("Every decision where the sign of the stress diff and the sign of the majority net disagree "
                f"({len(dis)} of {len(rec)}: D {sum(r['protocol'] == 'D' for r in dis)}, R {sum(r['protocol'] == 'R' for r in dis)})",
                [((r["protocol"], f"{r['upgrade']} / {r['suite']}"), r) for r in dis])
    # pair level (three suites)
    pdis = []
    for proto in ("D", "R"):
        for name, _, _ in pairs:
            t = agg([r for r in rec if r["protocol"] == proto and r["upgrade"] == name])
            if disagree(t["stress_diff_study"], t["majority_net"]) or abs(rd(t["stress_diff_study"])) < 0.001:
                pdis.append(((proto, f"{name}, three suites"), t))
    recon_table("Upgrade level (three suites together): sign disagreements, and upgrades with |mean stress diff| < 0.001", pdis)
    md.append("Per-decision pass-count distributions (0..10) for both models of every decision are in `EXPLORATORY_item_level_flips_reconcile.csv`.\n")
    with open(out / "EXPLORATORY_item_level_flips_reconcile.csv", "w", encoding="utf-8", newline="") as fh:
        cols = [c for c in rec[0] if not c.endswith("_dist")] + [f"old_{i}of10" for i in range(11)] + [f"new_{i}of10" for i in range(11)] + ["signs_disagree"]
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rec:
            w.writerow([f"{r[c]:.6f}" if isinstance(r[c], float) else r[c] for c in cols if c in r and not c.endswith("_dist")]
                       + r["old_dist"] + r["new_dist"] + [int(disagree(r["stress_diff_study"], r["majority_net"]))])

    # ------------------------------------------------------------ 3. got-worse failure types by condition
    md.append("### 3. 'Got worse' failure types by stress condition\n")
    md.append("Same questions and the same failure-type rule as the tables above (most common failure type among the new model's failing trials), split by "
              "the stress condition of the question.\n")
    wrows = []
    for proto in ("D", "R"):
        md.append(f"#### {'Default protocol (D)' if proto == 'D' else 'Robust protocol (R)'}\n")
        md.append("| Upgrades | Condition | Got worse | " + " | ".join(REASONS) + " |\n|---|---|---|" + "---|" * len(REASONS))
        for tag, flt in (("all 10", lambda n: True), ("without qwen25->qwen3", lambda n: n != SEP), ("qwen25->qwen3 only", lambda n: n == SEP)):
            for cond in stress:
                c = Counter()
                for name, _, _ in pairs:
                    if flt(name):
                        c.update(reasons_cond[(proto, name, cond)])
                md.append(f"| {tag} | {cond} | {sum(c.values())} | " + " | ".join(str(c[r]) for r in REASONS) + " |")
        md.append("")
        for name, _, _ in pairs:
            for cond in stress:
                c = reasons_cond[(proto, name, cond)]
                wrows.append({"protocol": proto, "upgrade": name, "condition": cond, "got_worse": sum(c.values()), **{r: c[r] for r in REASONS}})
    with open(out / "EXPLORATORY_item_level_flips_worse_by_condition.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(wrows[0]))
        w.writeheader()
        w.writerows(wrows)
    md.append(static("item_level_noise_summary"))
    return "\n".join(md), ["EXPLORATORY_item_level_flips_noise.csv", "EXPLORATORY_item_level_flips_reconcile.csv",
                           "EXPLORATORY_item_level_flips_worse_by_condition.csv"]
