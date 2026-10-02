"""AUDIT question H: old (pre-fix) vs new (corrected) BFCL numbers, computed
directly from the existing pre-fix and post-fix result folders (both still
present under results/). Read-only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FINAL_RUNS, PREFIX_BFCL_RUNS, REPO_ROOT, sc  # noqa: E402

CONDITIONS = ["baseline", "schema_drift", "runtime_fault"]


def load(run_dir_name: str) -> dict:
    path = os.path.join(REPO_ROOT, "results", run_dir_name, "parsed_results.jsonl")
    recs = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            p = json.loads(line)
            key = (p["task_id"], p["condition"], p.get("trial_index", 0))
            recs[key] = p
    return recs


def mean_by_condition(recs: dict) -> dict:
    out = {}
    for cond in CONDITIONS:
        vals = [sc(r) for r in recs.values() if r["condition"] == cond]
        out[cond] = sum(vals) / len(vals) if vals else None
    return out


def main() -> None:
    print("=== Q17: pre-fix vs corrected (post-fix) BFCL scores, same models ===")
    for model, prefix_dir in PREFIX_BFCL_RUNS.items():
        postfix_dir = FINAL_RUNS[("BFCL", model)]
        pre = mean_by_condition(load(prefix_dir))
        post = mean_by_condition(load(postfix_dir))
        print(f"\n{model}:")
        print(f"  pre-fix  dir: {prefix_dir}")
        print(f"  post-fix dir: {postfix_dir}")
        for cond in CONDITIONS:
            delta = post[cond] - pre[cond]
            print(f"  {cond:14}: pre={pre[cond]:.3f}  post={post[cond]:.3f}  delta={delta:+.3f}")


if __name__ == "__main__":
    main()
