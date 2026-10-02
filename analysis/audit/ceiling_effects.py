"""AUDIT question I/18: ceiling-effect tasks (passed by all 5 models, all trials, baseline).

Read-only, uses the 10 final result directories.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import load_parsed, sc  # noqa: E402

MODELS = ["Mistral v0.1", "Mistral v0.2", "Mistral v0.3", "Qwen2.5", "Qwen3"]


def main() -> None:
    for suite in ("synthetic", "BFCL"):
        per_model_pass = {}
        all_task_ids: set[str] = set()
        for model in MODELS:
            recs = load_parsed(suite, model)
            by_task: dict[str, list] = {}
            for r in recs.values():
                if r["condition"] == "baseline":
                    by_task.setdefault(r["task_id"], []).append(sc(r))
            all_task_ids |= set(by_task)
            all_pass = {t for t, scores in by_task.items() if all(s == 1.0 for s in scores)}
            per_model_pass[model] = all_pass
        common_task_ids = sorted(set.intersection(*per_model_pass.values()))
        total_tasks = len(all_task_ids)
        print(f"\n=== {suite}: baseline ceiling tasks ===")
        for model in MODELS:
            print(f"  {model:12}: all-trials-pass on {len(per_model_pass[model]):3}/{total_tasks} tasks")
        print(
            f"  Ceiling tasks (ALL 5 models pass ALL trials, baseline): "
            f"{len(common_task_ids)}/{total_tasks} ({100*len(common_task_ids)/total_tasks:.1f}%)"
        )


if __name__ == "__main__":
    main()
