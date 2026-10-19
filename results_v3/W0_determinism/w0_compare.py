"""W0 comparison: record-by-record, per trial index (and greedy vs sampled).

usage: python w0_compare.py RUN_A RUN_B [--label NAME] [--out FILE.json]
RUN_x = a run directory (contains raw_outputs.jsonl, parsed_results.jsonl).
Records are matched on (task_id, condition, trial_index). Reports for each trial:
  % byte-identical raw_output, % identical parsed_call, % identical strict score,
plus greedy-only (temperature 0) vs sampled-only aggregates and 3 example diffs.
Strict score = metrics.score from parsed_results.jsonl.
"""
import argparse, json, sys, collections
from pathlib import Path


def load(run, name):
    rows = {}
    with open(Path(run) / name, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                rows[(r["task_id"], r["condition"], r["trial_index"])] = r
    return rows


def canon(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def compare(run_a, run_b, label=""):
    ra, rb = load(run_a, "raw_outputs.jsonl"), load(run_b, "raw_outputs.jsonl")
    pa, pb = load(run_a, "parsed_results.jsonl"), load(run_b, "parsed_results.jsonl")
    keys = sorted(set(ra) & set(rb))
    out = {"label": label, "run_a": str(run_a), "run_b": str(run_b),
           "n_a": len(ra), "n_b": len(rb), "n_matched": len(keys), "trials": {}, "examples": []}
    acc = collections.defaultdict(lambda: [0, 0, 0, 0, None, None])  # n, raw, parsed, score
    for k in keys:
        t = k[2]
        temp = ra[k]["temperature"]
        same_raw = ra[k]["raw_output"] == rb[k]["raw_output"]
        same_parsed = canon(pa[k].get("parsed_call")) == canon(pb[k].get("parsed_call"))
        same_score = pa[k]["metrics"]["score"] == pb[k]["metrics"]["score"]
        for g in (f"trial_{t}", "greedy_all" if temp == 0 else "sampled_all", "all"):
            a = acc[g]; a[0] += 1; a[1] += same_raw; a[2] += same_parsed; a[3] += same_score
        acc[f"trial_{t}"][4] = temp; acc[f"trial_{t}"][5] = ra[k]["seed"]
        if not (same_raw and same_parsed and same_score) and len(out["examples"]) < 3:
            out["examples"].append({"key": list(k), "raw_a": ra[k]["raw_output"], "raw_b": rb[k]["raw_output"],
                                    "parsed_a": pa[k].get("parsed_call"), "parsed_b": pb[k].get("parsed_call"),
                                    "score_a": pa[k]["metrics"]["score"], "score_b": pb[k]["metrics"]["score"]})
    for g, (n, r, p, s, temp, seed) in sorted(acc.items()):
        out["trials"][g] = {"n": n, "pct_raw_identical": 100 * r / n, "pct_parsed_identical": 100 * p / n,
                            "pct_score_identical": 100 * s / n, "temperature": temp, "seed_a": seed}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_a"); ap.add_argument("run_b")
    ap.add_argument("--label", default=""); ap.add_argument("--out")
    a = ap.parse_args()
    res = compare(a.run_a, a.run_b, a.label)
    txt = json.dumps(res, indent=1, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")
    for g, v in res["trials"].items():
        print(f"{a.label} {g:12s} n={v['n']:5d} raw={v['pct_raw_identical']:.2f}% parsed={v['pct_parsed_identical']:.2f}% score={v['pct_score_identical']:.2f}%")
    print("examples:", len(res["examples"]))
