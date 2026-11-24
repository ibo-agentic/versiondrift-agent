"""EXPLORATORY task_level_comparison_D_greedy.csv: every stress question, old vs new model output side by side (D, greedy trial).

    python -m scripts.exploratory.task_level_comparison --out <folder>
"""

from __future__ import annotations

import sys, csv, json
from collections import defaultdict
from pathlib import Path
from vdanalysis.loader import record_score
from vdanalysis.phase2.config import load_phase2_config
from vdanalysis.phase2.merge import MergedStore
from ._common import CONFIG, parse_out


def run(outdir):
    cfg = load_phase2_config(str(CONFIG))
    store = MergedStore(cfg)
    stress = set(cfg.stress)
    cache = {}


    def load(model, suite):
        """{(task, cond): {"scores": {trial: 0/1}, "out0": raw output of trial 0, "prompt": prompt, "sha": sha}}"""
        if (model, suite) in cache:
            return cache[(model, suite)]
        d = defaultdict(lambda: {"scores": {}})
        for part, spec in store.part_dirs("D", model, suite):
            run_dir = store._find_run_dir(part)
            with open(run_dir / "parsed_results.jsonl", encoding="utf-8") as fp, open(run_dir / "raw_outputs.jsonl", encoding="utf-8") as fr:
                for lp, lr in zip(fp, fr):
                    p = json.loads(lp)
                    if p["condition"] not in stress:
                        continue
                    trial = int(p.get("trial_index", 0)) + spec.trial_offset
                    e = d[(p["task_id"], p["condition"])]
                    e["scores"][trial] = 1 if record_score(p) >= 1.0 else 0
                    if trial == 0:
                        r = json.loads(lr)
                        assert r["task_id"] == p["task_id"] and r["condition"] == p["condition"]
                        e["out0"] = r["raw_output"] or ""
                        e["prompt"] = r["prompt"]
                        e["sha"] = r["prompt_sha256"]
        cache[(model, suite)] = d
        return d


    OUT = outdir / "task_level_comparison_D_greedy.csv"
    cols = ["upgrade", "suite", "task_id", "condition", "prompt_given_to_both_models", "old_model", "new_model",
            "old_model_output", "new_model_output", "old_correct", "new_correct", "outcome",
            "old_pass_rate_10_trials", "new_pass_rate_10_trials"]
    n = mism = 0
    counts = defaultdict(lambda: defaultdict(int))
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(cols)
        for pair in cfg.pairs:
            old, new = pair["old"], pair["new"]
            name = cfg.pair_name(pair)
            for suite in cfg.suites:
                a, b = load(old, suite), load(new, suite)
                for key in sorted(set(a) & set(b)):
                    ea, eb = a[key], b[key]
                    if ea["sha"] != eb["sha"]:
                        mism += 1
                    oa, ob = ea["scores"][0], eb["scores"][0]
                    outcome = ("both correct" if oa and ob else "both wrong" if not oa and not ob
                               else "only the NEW model correct" if ob else "only the OLD model correct")
                    counts[(name, suite)][outcome] += 1
                    w.writerow([name, suite, key[0], key[1], ea["prompt"], old, new, ea["out0"], eb["out0"], oa, ob, outcome,
                                f"{sum(ea['scores'].values()) / len(ea['scores']):.2f}", f"{sum(eb['scores'].values()) / len(eb['scores']):.2f}"])
                    n += 1
    print("rows", n, "prompt hash mismatches between old and new", mism)

    return ["task_level_comparison_D_greedy.csv"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
