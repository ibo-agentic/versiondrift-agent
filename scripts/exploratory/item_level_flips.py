"""EXPLORATORY_item_level_flips.md (+ summary and questions CSVs): who got worse / better, per upgrade, D and R.

    python -m scripts.exploratory.item_level_flips --out <folder>
"""

from __future__ import annotations

import sys, json, csv, re
from collections import Counter, defaultdict
from pathlib import Path
from vdanalysis.loader import record_score
from vdanalysis.phase2.config import load_phase2_config
from vdanalysis.phase2.merge import MergedStore
from ._common import CONFIG, P7_DIR, parse_out, static
from ._item_level_noise import section as noise_section


def run(outdir):
    OUT = outdir
    cfg = load_phase2_config(str(CONFIG))
    store = MergedStore(cfg)
    stress = set(cfg.stress)
    pairs = [(cfg.pair_name(p), p["old"], p["new"]) for p in cfg.pairs]
    REASONS = ["wrong tool name", "wrong/invalid arguments", "unparsed/broken output", "fault-reporting wrong status", "fabricated answer", "other"]
    cache = {}
    raw0 = {}


    def reason(p):
        m = p["metrics"]
        if not m.get("parse_ok", False):
            return "unparsed/broken output"
        if p["condition"] == "fault_reporting":
            if not m.get("status_ok", True):
                return "fault-reporting wrong status"
            if not m.get("no_fabrication", True):
                return "fabricated answer"
            return "other"
        if not m.get("tool_name_ok", True):
            return "wrong tool name"
        if not (m.get("args_valid_under_drift", True) and m.get("args_intent_match", True) and m.get("executor_ok", True)):
            return "wrong/invalid arguments"
        return "other"


    def load(proto, model, suite):
        k = (proto, model, suite)
        if k in cache:
            return cache[k]
        d = defaultdict(dict)                      # (task, cond) -> trial -> (ok, reason)
        for part, spec in store.part_dirs(proto, model, suite):
            run_dir = store._find_run_dir(part)
            fr = open(run_dir / "raw_outputs.jsonl", encoding="utf-8") if proto == "D" else None
            with open(run_dir / "parsed_results.jsonl", encoding="utf-8") as fp:
                for i, lp in enumerate(fp):
                    lr = fr.readline() if fr else None
                    p = json.loads(lp)
                    if p["condition"] not in stress:
                        continue
                    t = int(p.get("trial_index", 0)) + spec.trial_offset
                    ok = record_score(p) >= 1.0
                    d[(p["task_id"], p["condition"])][t] = (ok, None if ok else reason(p))
                    if fr and t == 0:
                        r = json.loads(lr)
                        raw0[(model, suite, p["task_id"], p["condition"])] = (r["raw_output"] or "", r["prompt"])
            if fr:
                fr.close()
        cache[k] = d
        return d


    def question(prompt):
        i = prompt.find("Question: ")
        return prompt[i + 10:prompt.find("\n", i)].strip()


    def short(s, n=200):
        s = re.sub(r"\s+", " ", s).strip()
        return s if len(s) <= n else s[:n] + " ..."


    def majority(tr):
        rate = sum(ok for ok, _ in tr.values()) / len(tr)
        return rate, (rate > 0.5), (rate == 0.5)


    def cell(a, b):
        return "both right" if a and b else "got worse" if a and not b else "got better" if b and not a else "both wrong"


    stress_diff = {}
    for proto, fn in (("D", str(P7_DIR / "decisions_D.csv")), ("R", None)):
        if fn:
            for r in csv.DictReader(open(fn)):
                stress_diff[("D", r["pair"], r["suite"])] = float(r["stress_diff"])
    for r in csv.DictReader(open(P7_DIR / "decisions_all_protocols.csv")):
        if r["protocol"] == "R":
            stress_diff[("R", r["pair"], r["suite"])] = float(r["stress_diff"])

    summary, qrows = [], []
    reasons = defaultdict(Counter)                 # (proto, pair) -> reason counts for 'got worse' (majority)
    reasons_cond = defaultdict(Counter)            # (proto, pair, condition) -> the same, split by stress condition
    worse_examples = defaultdict(list)
    for proto in ("D", "R"):
        for name, old, new in pairs:
            for suite in cfg.suites:
                a, b = load(proto, old, suite), load(proto, new, suite)
                cnt = {"maj": Counter(), "greedy": Counter()}
                ties = 0
                for key in sorted(set(a) & set(b)):
                    ra, ma, ta = majority(a[key])
                    rb, mb, tb = majority(b[key])
                    ties += ta or tb
                    cm = cell(ma, mb)
                    cg = cell(a[key][0][0], b[key][0][0])
                    cnt["maj"][cm] += 1
                    cnt["greedy"][cg] += 1
                    rs = ""
                    if cm == "got worse":
                        fails = Counter(r for ok, r in b[key].values() if not ok)
                        rs = fails.most_common(1)[0][0] if fails else "other"
                        reasons[(proto, name)][rs] += 1
                        reasons_cond[(proto, name, key[1])][rs] += 1
                        if proto == "D" and a[key][0][0] is True and b[key][0][0] is False:
                            worse_examples[name].append((suite, key, rs))
                    qrows.append([proto, name, suite, key[0], key[1], f"{ra:.1f}", int(ma), f"{rb:.1f}", int(mb), cm, cg, rs])
                for basis in ("maj", "greedy"):
                    c = cnt[basis]
                    summary.append({"protocol": proto, "pair": name, "suite": suite, "basis": "majority of 10 trials" if basis == "maj" else "greedy trial",
                                    "stress_diff": stress_diff[(proto, name, suite)], "both_right": c["both right"], "got_worse": c["got worse"],
                                    "got_better": c["got better"], "both_wrong": c["both wrong"], "net_change": c["got better"] - c["got worse"],
                                    "churn": c["got better"] + c["got worse"], "tie_questions": ties if basis == "maj" else ""})

    with open(OUT / "EXPLORATORY_item_level_flips_summary.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    with open(OUT / "EXPLORATORY_item_level_flips_questions.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["protocol", "upgrade", "suite", "task_id", "condition", "old_pass_rate_10", "old_correct_majority", "new_pass_rate_10",
                    "new_correct_majority", "cell_majority", "cell_greedy", "why_new_failed_if_got_worse"])
        w.writerows(qrows)

    HEAD = ("**EXPLORATORY, post hoc. Not pre-registered. Existing data only (analysis at tag pre-analysis-v2.3, commit 73a9017); descriptive; "
            "feeds no gate, verdict or hypothesis.**\n\n")
    md = HEAD + "# Item-level view of the upgrades: who got worse, who got better\n\n"
    md += ("**Unit:** one question = one task under one stress condition (schema_drift or fault_reporting): 200 per suite, 600 per upgrade. "
           "**Correct** = the study's own pass/fail (`record_score`). A model counts as right on a question when it passed in **more than half of the 10 trials** "
           "(6 or more); exactly 5 of 10 counts as not right (a tie, counted in the table). The check column uses only the greedy trial (trial 0). "
           "Cells: *both right*; *got worse* (old right, new wrong); *got better* (old wrong, new right); *both wrong*. Net = got better minus got worse; "
           "churn = got better plus got worse. Stress diff is the study's own number for that decision (new minus old score), for comparison.\n\n")
    for proto, title in (("D", "Default protocol (D)"), ("R", "Robust protocol (R)")):
        md += f"## {title}: per upgrade and suite\n\n"
        md += ("| Upgrade | Suite | Stress diff | Both right | Got worse | Got better | Both wrong | Net | Churn | Ties | Greedy check: worse / better / net |\n|---|---|---|---|---|---|---|---|---|---|---|\n")
        S = [s for s in summary if s["protocol"] == proto]
        for s in S:
            if s["basis"] != "majority of 10 trials":
                continue
            g = next(x for x in S if x["pair"] == s["pair"] and x["suite"] == s["suite"] and x["basis"] == "greedy trial")
            md += (f"| {s['pair']} | {s['suite']} | {s['stress_diff']:+.3f} | {s['both_right']} | {s['got_worse']} | {s['got_better']} | {s['both_wrong']} | "
                   f"{s['net_change']:+d} | {s['churn']} | {s['tie_questions']} | {g['got_worse']} / {g['got_better']} / {g['net_change']:+d} |\n")
        md += f"\n### {title}: per upgrade, three suites together (600 questions)\n\n| Upgrade | Both right | Got worse | Got better | Both wrong | Net | Churn | Churn as share of questions | Mean stress diff |\n|---|---|---|---|---|---|---|---|---|\n"
        for name, _, _ in pairs:
            rows = [s for s in S if s["pair"] == name and s["basis"] == "majority of 10 trials"]
            t = {k: sum(r[k] for r in rows) for k in ("both_right", "got_worse", "got_better", "both_wrong", "net_change", "churn")}
            md += (f"| {name} | {t['both_right']} | {t['got_worse']} | {t['got_better']} | {t['both_wrong']} | {t['net_change']:+d} | {t['churn']} | "
                   f"{100 * t['churn'] / 600:.1f}% | {sum(r['stress_diff'] for r in rows) / 3:+.3f} |\n")
        md += f"\n### {title}: why the new model failed on the 'got worse' questions\n\n(The failure type that was most common among the new model's failing trials on that question.)\n\n"
        md += "| Upgrade | Got worse | " + " | ".join(REASONS) + " |\n|---|---|" + "---|" * len(REASONS) + "\n"
        tot = Counter()
        for name, _, _ in pairs:
            c = reasons[(proto, name)]
            tot.update(c)
            md += f"| {name} | {sum(c.values())} | " + " | ".join(str(c[r]) for r in REASONS) + " |\n"
        md += f"| **All upgrades** | {sum(tot.values())} | " + " | ".join(f"**{tot[r]}**" for r in REASONS) + " |\n\n"

    md += "## Real examples of 'got worse' (Default protocol, greedy trial outputs)\n\nThe questions were 'got worse' on the 10-trial majority, and the new model's greedy trial also failed while the old model's passed.\n\n"
    for name in ("qwen25->qwen3", "mistral_v01->mistral_v02"):
        old, new = next((o, n) for nm, o, n in pairs if nm == name)
        md += f"### {name}\n\n"
        used, shown = set(), 0
        for suite, key, rs in worse_examples[name]:
            if rs in used and len(used) < 2 and shown < 2:
                continue
            if shown >= 2:
                break
            ro, rp = raw0[(old, suite, key[0], key[1])]
            rn, _ = raw0[(new, suite, key[0], key[1])]
            md += (f"- **{suite} / {key[0]} / {key[1]}**: \"{question(rp)}\"\n  - OLD {old}: `{short(ro)}` (correct)\n"
                   f"  - NEW {new}: `{short(rn)}` (**wrong: {rs}**)\n")
            used.add(rs)
            shown += 1
        md += "\n"
    md = md.rstrip("\n") + "\n\n" + static("item_level_flips_tail")
    noise_md, noise_files = noise_section(OUT, cfg, load, pairs, summary, reasons_cond, REASONS)
    md = md.rstrip("\n") + "\n" + noise_md
    (OUT / "EXPLORATORY_item_level_flips.md").write_text(md, encoding="utf-8")
    print("ok", len(qrows))

    return ["EXPLORATORY_item_level_flips.md", "EXPLORATORY_item_level_flips_summary.csv", "EXPLORATORY_item_level_flips_questions.csv"] + noise_files


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
