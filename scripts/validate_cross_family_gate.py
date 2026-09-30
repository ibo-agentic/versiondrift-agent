"""Cross-family release-gate validation: do canary tasks selected from one
model family transfer to another family's upgrade?

Selection: task informativeness comes ONLY from the select pair(s) —
|pooled stress difference| (schema_drift + runtime_fault, task-level mean
over trials), ranked with a category-coverage pass (one task per uncovered
drift/fault category first). Multiple select pairs can be given; ranks
combine by mean |diff| across pairs.

Evaluation: the eval pair's full-suite stress difference is ground truth
(harmful < -0.05, beneficial > +0.05, else neutral). The canary subset's
difference on the EVAL pair is the prediction. Random subsets of the same
size on the eval pair are the baseline.

Usage:
    python scripts/validate_cross_family_gate.py SEL_A SEL_B EVAL_A EVAL_B \
        [--also-select SEL_C SEL_D]

Example (Mistral-selected canary tested on Qwen):
    python scripts/validate_cross_family_gate.py \
        results/...itlwas-v0.1... results/...itlwas-v0.2... \
        results/...qwen25... results/...qwen3... \
        --also-select results/...itlwas-v0.2... results/...itlwas-v0.3...
"""

from __future__ import annotations

import json
import os
import random
import sys

KS = [10, 20, 30, 40]
GATE_THRESHOLD = 0.05
STRESS = ("schema_drift", "runtime_fault")
RANDOM_SUBSETS = 200
RANDOM_SEED = 20241001


def load_run(run_dir: str) -> dict:
    for name in ("parsed_results_corrected.jsonl", "parsed_results.jsonl"):
        path = os.path.join(run_dir, name)
        if os.path.exists(path):
            recs = {}
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    p = json.loads(line)
                    key = (
                        p["task_id"],
                        p["condition"],
                        (p["drift"] or {}).get("type"),
                        (p["fault"] or {}).get("type"),
                        p.get("trial_index", 0),
                    )
                    recs[key] = p
            print(f"[loaded {len(recs)} from {run_dir} ({name})]")
            return recs
    raise FileNotFoundError(f"no parsed results in {run_dir}")


def functional(m: dict) -> float:
    return (
        1.0
        if (m["parse_ok"] and m["tool_name_ok"] and m["args_intent_match"]
            and m["args_valid_under_drift"] and m["executor_ok"])
        else 0.0
    )


def sc(rec: dict) -> float:
    return functional(rec["metrics"])


def gate_label(d: float) -> str:
    if d < -GATE_THRESHOLD:
        return "harmful"
    if d > GATE_THRESHOLD:
        return "beneficial"
    return "neutral"


def subset_diff(ra: dict, rb: dict, keys: list) -> float:
    return sum(sc(rb[k]) - sc(ra[k]) for k in keys) / len(keys)


def select_canary(ranked: list, categories: dict, k: int) -> list:
    selected, covered = [], set()
    for t in ranked:
        if len(selected) >= k:
            break
        if categories[t] - covered:
            selected.append(t)
            covered |= categories[t]
    for t in ranked:
        if len(selected) >= k:
            break
        if t not in selected:
            selected.append(t)
    return selected


def parse_args(argv: list[str]):
    positional, also = [], None
    i = 1
    while i < len(argv):
        if argv[i] == "--also-select":
            also = (argv[i + 1], argv[i + 2])
            i += 3
        else:
            positional.append(argv[i])
            i += 1
    if len(positional) != 4:
        sys.exit("usage: validate_cross_family_gate.py SEL_A SEL_B EVAL_A EVAL_B [--also-select SEL_C SEL_D]")
    return positional, also


def main(argv: list[str]) -> None:
    (sa, sb, ea, eb), also = parse_args(argv)
    sel_pairs = [(load_run(sa), load_run(sb), f"{os.path.basename(sa).split('_seed')[0]}->{os.path.basename(sb).split('_seed')[0]}")]
    if also:
        sel_pairs.append((load_run(also[0]), load_run(also[1]),
                          f"{os.path.basename(also[0]).split('_seed')[0]}->{os.path.basename(also[1]).split('_seed')[0]}"))
    ra, rb = load_run(ea), load_run(eb)
    eval_name = f"{os.path.basename(ea).split('_seed')[0]}->{os.path.basename(eb).split('_seed')[0]}"

    common = sorted(set.intersection(*[set(r) for r in (ra, rb)], *[set(p[0]) & set(p[1]) for p in sel_pairs]))
    task_ids = sorted({k[0] for k in common})
    by_task = {t: [k for k in common if k[0] == t and k[1] in STRESS] for t in task_ids}
    categories = {
        t: {k[2] for k in ks if k[1] == "schema_drift"} | {k[3] for k in ks if k[1] == "runtime_fault"}
        for t, ks in by_task.items()
    }
    stress_keys = [k for k in common if k[1] in STRESS]
    print(f"\nselection pairs: {[p[2] for p in sel_pairs]} | eval pair: {eval_name}")
    print(f"matched stress records: {len(stress_keys)} across {len(task_ids)} tasks")

    # Informativeness: mean |task diff| across select pairs (select-pair records only)
    informativeness = {}
    for t in task_ids:
        vals = []
        for s_a, s_b, _ in sel_pairs:
            ks = by_task[t]
            if all(k in s_a and k in s_b for k in ks):
                vals.append(abs(subset_diff(s_a, s_b, ks)))
        informativeness[t] = sum(vals) / len(vals) if vals else 0.0
    ranked = sorted(task_ids, key=lambda t: informativeness[t], reverse=True)
    print(f"top-12 selected-source tasks: {[(t, round(informativeness[t], 2)) for t in ranked[:12]]}")

    full = subset_diff(ra, rb, stress_keys)
    truth = gate_label(full)
    print(f"eval full-suite stress diff = {full:+.3f} -> truth: {truth}")

    for k in KS:
        canary = select_canary(ranked, categories, k)
        d = subset_diff(ra, rb, [key for t in canary for key in by_task[t]])
        pred = gate_label(d)
        fa = truth == "harmful" and pred != "harmful"
        fr = truth == "beneficial" and pred != "beneficial"
        rng = random.Random(f"{RANDOM_SEED}-{eval_name}-{k}")
        rand_correct = 0
        rand_diffs = []
        for _ in range(RANDOM_SUBSETS):
            sub = rng.sample(task_ids, k)
            rd_ = subset_diff(ra, rb, [key for t in sub for key in by_task[t]])
            rand_diffs.append(rd_)
            rand_correct += gate_label(rd_) == truth
        rand_diffs.sort()
        pct = sum(1 for x in rand_diffs if abs(x) <= abs(d)) / len(rand_diffs)
        print(
            f"  k={k:2d}: canary diff={d:+.3f} pred={pred:<10} correct={pred == truth} "
            f"signMatch={(d > 0) == (full > 0)} FA={fa} FR={fr} | random acc={rand_correct / RANDOM_SUBSETS:.3f} "
            f"|diff| pct vs random={pct:.2f}"
        )


if __name__ == "__main__":
    main(sys.argv)
