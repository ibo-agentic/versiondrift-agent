"""EXPLORATORY failure_examples_old_vs_new.md and failure_cases_old_vs_new.csv: where the old or the new model failed (D, greedy trial).

    python -m scripts.exploratory.failure_examples --out <folder>
"""

from __future__ import annotations

import sys, json, re
from collections import defaultdict
from pathlib import Path
from vdanalysis.loader import record_score
from vdanalysis.phase2.config import load_phase2_config
from vdanalysis.phase2.merge import MergedStore
import csv
from ._common import CONFIG, parse_out


def run(outdir):
    cfg = load_phase2_config(str(CONFIG))
    store = MergedStore(cfg)
    stress = set(cfg.stress)
    cache = {}


    def load(model, suite):
        if (model, suite) in cache:
            return cache[(model, suite)]
        d = {}
        for part, spec in store.part_dirs("D", model, suite):
            run_dir = store._find_run_dir(part)
            with open(run_dir / "parsed_results.jsonl", encoding="utf-8") as fp, open(run_dir / "raw_outputs.jsonl", encoding="utf-8") as fr:
                for lp, lr in zip(fp, fr):
                    p = json.loads(lp)
                    if p["condition"] not in stress or int(p.get("trial_index", 0)) + spec.trial_offset != 0:
                        continue
                    r = json.loads(lr)
                    d[(p["task_id"], p["condition"])] = {"ok": record_score(p) >= 1.0, "out": r["raw_output"] or "", "prompt": r["prompt"],
                                                           "m": p["metrics"], "call": p.get("parsed_call") or {}}
        cache[(model, suite)] = d
        return d


    def expected_status(prompt):
        if "tool call succeeded" in prompt:
            return "ok"
        if "truncated it and some fields are missing" in prompt:
            return "incomplete"
        return "failed"


    def why(e, cond):
        m, call, out = e["m"], e["call"], e["out"]
        if not m.get("parse_ok", False):
            if "<think>" in out and "</think>" not in out:
                return "ran out of tokens while 'thinking'; no answer was given"
            body = re.sub(r"^```(?:json)?|```$", "", out.strip(), flags=re.M).strip()
            try:
                json.loads(body)
            except ValueError:
                return "no valid JSON reply could be read from the output"
            if cond == "fault_reporting":
                return "valid JSON, but not in the required form: 'answer' must be a text string or null (here it is another type)"
            return "valid JSON, but not in the required {name, arguments} form"
        if cond == "fault_reporting":
            exp, got = expected_status(e["prompt"]), call.get("status")
            if not m.get("status_ok", True):
                return f"wrong status: said '{got}' but the tool result was '{exp}'-type"
            if not m.get("no_fabrication", True):
                return f"made up an answer ('{str(call.get('answer'))[:40]}') although the tool call {exp}"
            return "failed the scorer's fault-reporting check"
        bad = []
        if not m.get("tool_name_ok", True):
            bad.append("wrong tool name")
        if not m.get("args_valid_under_drift", True):
            bad.append("arguments not valid under the schema shown (wrong type, missing or unknown argument, or an old value)")
        if not m.get("args_intent_match", True):
            bad.append("arguments do not match what the user asked")
        if not m.get("executor_ok", True):
            bad.append("the call did not run")
        return "; ".join(bad) or "failed the scorer's tool-call check"


    def question(prompt):
        i = prompt.find("Question: ")
        j = prompt.find("\n", i)
        return prompt[i + 10:j].strip()


    def short(s, n=170):
        s = re.sub(r"\s+", " ", s).strip()
        return s if len(s) <= n else s[:n] + " ..."


    md = ["**EXPLORATORY extract (post hoc, descriptive).** Real cases where the older or the newer model failed on the same task, "
          "from the default setup D, greedy trial 0, stress conditions (schema_drift = tool call; fault_reporting = status report). "
          "Examples are the first matching tasks in sorted order, one per suite where available; they are illustrations, not a sample. "
          "'Why wrong' is derived from the scorer's own checks. Source: results_v2 + results_v3, tag pre-analysis-v2.3.\n"]
    summary = []
    for pair in cfg.pairs:
        old, new, name = pair["old"], pair["new"], cfg.pair_name(pair)
        md.append(f"\n## {name}\n")
        groups = {"only the OLD model correct (the NEW model failed)": [], "only the NEW model correct (the OLD model failed)": [], "both wrong": []}
        tally = defaultdict(int)
        for suite in cfg.suites:
            a, b = load(old, suite), load(new, suite)
            for key in sorted(set(a) & set(b)):
                ea, eb = a[key], b[key]
                g = ("both wrong" if not ea["ok"] and not eb["ok"] else "only the OLD model correct (the NEW model failed)" if ea["ok"] and not eb["ok"]
                     else "only the NEW model correct (the OLD model failed)" if eb["ok"] and not ea["ok"] else None)
                if g:
                    tally[g] += 1
                    groups[g].append((suite, key, ea, eb))
        for g, items in groups.items():
            picked, seen = [], set()
            for it in items:
                if it[0] not in seen:
                    picked.append(it); seen.add(it[0])
                if len(picked) >= (1 if g == "both wrong" else 3):
                    break
            md.append(f"### {g} ({tally[g]} of 600 task-conditions)\n")
            for suite, key, ea, eb in picked:
                md.append(f"- **{suite} / {key[0]} / {key[1]}**: \"{question(ea['prompt'])}\"")
                md.append(f"  - OLD {old}: `{short(ea['out'])}` -> {'correct' if ea['ok'] else 'WRONG: ' + why(ea, key[1])}")
                md.append(f"  - NEW {new}: `{short(eb['out'])}` -> {'correct' if eb['ok'] else 'WRONG: ' + why(eb, key[1])}")
            md.append("")
    (outdir / "failure_examples_old_vs_new.md").write_text("\n".join(md), encoding="utf-8")

    cols = ["upgrade", "suite", "task_id", "condition", "question", "outcome", "old_model", "old_model_output", "old_correct",
            "old_why_wrong", "new_model", "new_model_output", "new_correct", "new_why_wrong"]
    n = 0
    with open(outdir / "failure_cases_old_vs_new.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(cols)
        for pair in cfg.pairs:
            old, new, name = pair["old"], pair["new"], cfg.pair_name(pair)
            for suite in cfg.suites:
                a, b = load(old, suite), load(new, suite)
                for key in sorted(set(a) & set(b)):
                    ea, eb = a[key], b[key]
                    if ea["ok"] and eb["ok"]:
                        continue
                    outcome = ("both wrong" if not ea["ok"] and not eb["ok"] else
                               "only the NEW model failed" if ea["ok"] else "only the OLD model failed")
                    w.writerow([name, suite, key[0], key[1], question(ea["prompt"]), outcome,
                                old, ea["out"], int(ea["ok"]), "" if ea["ok"] else why(ea, key[1]),
                                new, eb["out"], int(eb["ok"]), "" if eb["ok"] else why(eb, key[1])])
                    n += 1

    return ["failure_examples_old_vs_new.md", "failure_cases_old_vs_new.csv"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
