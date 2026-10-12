"""Hardware check: how closely do greedy records produced on Kaggle's T4
match the laptop's D greedy records (same Q4_K_M files, same config)?

Compares ONLY trial_index == 0 (temperature 0.0) records, matched one to one
on (task_id, condition, trial_index). For every matched record:

  prompt_equal   prompt_sha256 identical (inputs were byte-identical)
  raw_equal      raw_output (and retry_raw_output) identical -- THE match rate
  call_equal     parsed_call identical
  score_equal    metrics.score identical

It reports counts and rates only: no verdicts, no pair differences, no
accuracy comparison between models or versions.

Usage:
  python scripts/compare_kaggle_hwcheck.py \
      --kaggle-root results_v2/KAGGLE_HWCHECK --laptop-root results_v2/D \
      [--models llama31 mistral_v02] [--out-dir DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "kaggle"))
import kaggle_plan as plan  # noqa: E402


def find_run_dir(suite_dir: Path) -> Path:
    if (suite_dir / "parsed_results.jsonl").exists():
        return suite_dir
    cands = sorted(d for d in suite_dir.glob("*") if d.is_dir() and (d / "parsed_results.jsonl").exists()) \
        if suite_dir.exists() else []
    if not cands:
        raise FileNotFoundError(f"no run with parsed_results.jsonl under {suite_dir}")
    if len(cands) > 1:
        raise ValueError(f"ambiguous: {len(cands)} run directories under {suite_dir}")
    return cands[0]


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def greedy_records(run_dir: Path) -> dict[tuple, dict]:
    raw = {(r["task_id"], r["condition"], int(r.get("trial_index", 0))): r
           for r in read_jsonl(run_dir / "raw_outputs.jsonl") if int(r.get("trial_index", 0)) == 0}
    out = {}
    for p in read_jsonl(run_dir / "parsed_results.jsonl"):
        if int(p.get("trial_index", 0)) != 0:
            continue
        k = (p["task_id"], p["condition"], 0)
        if k not in raw:
            raise ValueError(f"{run_dir}: parsed record {k} has no raw_outputs row")
        out[k] = {"raw": raw[k], "parsed": p}
    return out


def compare_run(kaggle_dir: Path, laptop_dir: Path) -> dict:
    a, b = greedy_records(kaggle_dir), greedy_records(laptop_dir)
    common = sorted(set(a) & set(b))
    res = {"kaggle_run": kaggle_dir.name, "laptop_run": laptop_dir.name,
           "n_kaggle": len(a), "n_laptop": len(b), "n_matched_keys": len(common),
           "only_kaggle": len(set(a) - set(b)), "only_laptop": len(set(b) - set(a)),
           "by_condition": {}, "mismatches": []}
    tot = {"prompt_equal": 0, "raw_equal": 0, "call_equal": 0, "score_equal": 0}
    for k in common:
        ra, rb = a[k]["raw"], b[k]["raw"]
        pa, pb = a[k]["parsed"], b[k]["parsed"]
        flags = {
            "prompt_equal": ra.get("prompt_sha256") == rb.get("prompt_sha256"),
            "raw_equal": ra.get("raw_output") == rb.get("raw_output")
                         and ra.get("retry_raw_output") == rb.get("retry_raw_output"),
            "call_equal": pa.get("parsed_call") == pb.get("parsed_call"),
            "score_equal": pa["metrics"].get("score") == pb["metrics"].get("score"),
        }
        cond = res["by_condition"].setdefault(k[1], {"n": 0, **{f: 0 for f in tot}})
        cond["n"] += 1
        for f, v in flags.items():
            tot[f] += int(v)
            cond[f] += int(v)
        if not flags["raw_equal"]:
            res["mismatches"].append({"task_id": k[0], "condition": k[1],
                                      "prompt_equal": flags["prompt_equal"],
                                      "kaggle_raw": (ra.get("raw_output") or "")[:300],
                                      "laptop_raw": (rb.get("raw_output") or "")[:300]})
    n = len(common)
    res.update({f: v for f, v in tot.items()})
    res["raw_match_rate"] = tot["raw_equal"] / n if n else None
    res["score_match_rate"] = tot["score_equal"] / n if n else None
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kaggle-root", default=str(REPO_ROOT / "results_v2" / "KAGGLE_HWCHECK"))
    ap.add_argument("--laptop-root", default=str(REPO_ROOT / "results_v2" / plan.HWCHECK_LAPTOP_PROTOCOL))
    ap.add_argument("--models", nargs="+", default=list(plan.HWCHECK_MODELS))
    ap.add_argument("--suites", nargs="+", default=list(plan.SUITES))
    ap.add_argument("--out-dir", default=None, help="write hwcheck_comparison.json / .md here")
    ap.add_argument("--max-mismatches", type=int, default=5, help="examples shown per run")
    args = ap.parse_args(argv)

    results, problems = [], []
    for m in args.models:
        for s in args.suites:
            try:
                r = compare_run(find_run_dir(Path(args.kaggle_root) / m / s),
                                find_run_dir(Path(args.laptop_root) / m / s))
            except (FileNotFoundError, ValueError) as exc:
                problems.append(f"{m}/{s}: {exc}")
                continue
            r.update(model=m, suite=s)
            results.append(r)

    lines = ["| model | suite | greedy records | prompt equal | raw output equal | parsed call equal | score equal |",
             "|---|---|---|---|---|---|---|"]
    T = {"n": 0, "prompt_equal": 0, "raw_equal": 0, "call_equal": 0, "score_equal": 0}
    for r in results:
        n = r["n_matched_keys"]
        lines.append(f"| {r['model']} | {r['suite']} | {n} | {r['prompt_equal']}/{n} | "
                     f"{r['raw_equal']}/{n} ({100 * r['raw_equal'] / n:.1f}%) | {r['call_equal']}/{n} | "
                     f"{r['score_equal']}/{n} |" if n else f"| {r['model']} | {r['suite']} | 0 | - | - | - | - |")
        T["n"] += n
        for f in ("prompt_equal", "raw_equal", "call_equal", "score_equal"):
            T[f] += r[f]
    if T["n"]:
        lines.append(f"| **all** | | {T['n']} | {T['prompt_equal']}/{T['n']} | "
                     f"{T['raw_equal']}/{T['n']} ({100 * T['raw_equal'] / T['n']:.1f}%) | "
                     f"{T['call_equal']}/{T['n']} | {T['score_equal']}/{T['n']} |")
    md = "\n".join(lines)
    print(md)
    for r in results:
        if r["only_kaggle"] or r["only_laptop"]:
            print(f"NOTE {r['model']}/{r['suite']}: unmatched keys: {r['only_kaggle']} only on Kaggle, "
                  f"{r['only_laptop']} only on laptop")
        for mm in r["mismatches"][: args.max_mismatches]:
            print(f"  MISMATCH {r['model']}/{r['suite']} {mm['task_id']} {mm['condition']} "
                  f"(prompt_equal={mm['prompt_equal']})\n    kaggle: {mm['kaggle_raw']!r}\n    laptop: {mm['laptop_raw']!r}")
    for p in problems:
        print("PROBLEM", p, file=sys.stderr)

    if args.out_dir:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "hwcheck_comparison.json").write_text(
            json.dumps({"totals": T, "runs": results, "problems": problems}, indent=2), encoding="utf-8")
        (out / "hwcheck_comparison.md").write_text(md + "\n", encoding="utf-8")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
