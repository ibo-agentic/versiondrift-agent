"""Scoring-only factors (F7 lenient parsing, F8 relaxed intent) on Phase 2's new records.

The scoring-only factors are recomputed from saved records (PLAN_PHASE2.md W1).
Phase 1's D records were rescored into ``rescored/`` already; this module
rescores only the *new* D parts (results_v3), writing them next to Phase 1's
under ``rescored_v3/<F7|F8>/<model>/<suite>/<run_id>-<factor>``. The merged
loader then puts the two parts on one trial axis exactly as it does for D.
F10 (greedy trial only) needs no files in Phase 2: it is a view of D.

It uses the very same scoring functions as Phase 1 (vdanalysis.rescore) and,
like them, reads records and writes only into a new folder (never into
results_v2/ or results_v3/).

    python -m vdanalysis.phase2.rescore_v3 --config configs/analysis_phase2.yaml --factor F7
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from upgradecanary.tasks import load_tasks
from upgradecanary.utils import read_jsonl

from ..rescore import FACTORS, rescore_lenient, rescore_relaxed_intent, subsample_greedy, write_rescored
from .config import Phase2Config, load_phase2_config
from .merge import MergedStore
from .run_phase2 import assert_safe_output_dir_p2


def rescore_v3_parts(cfg: Phase2Config, factor: str, out_root: Path, models=None, suites=None,
                     tasks_loader: Callable[[str], dict] | None = None) -> list[dict]:
    """Rescore every D part that does not live in the Phase 1 results root."""
    out_root = assert_safe_output_dir_p2(out_root)
    store = MergedStore(cfg)
    if tasks_loader is None:
        def tasks_loader(suite: str) -> dict:
            path = Path(cfg.raw["task_data"][suite])
            return {t.task_id: t for t in load_tasks(path if path.is_absolute() else cfg.base_dir / path)}
    spec = FACTORS[factor]
    base = cfg.base_protocol
    log = []
    for model in models or list(cfg.models):
        for suite in suites or cfg.suites:
            for part_dir, part in store.part_dirs(base, model, suite):
                if part.root == "results_root":
                    continue                      # Phase 1's part: already rescored under rescored/
                src = store._find_run_dir(part_dir)
                parsed = read_jsonl(src / "parsed_results.jsonl")
                mp = src / "run_manifest.json"
                manifest = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
                if factor == "F7":
                    new_rows, diffs = rescore_lenient(parsed, read_jsonl(src / "raw_outputs.jsonl"), tasks_loader(suite))
                elif factor == "F8":
                    new_rows, diffs = rescore_relaxed_intent(parsed, tasks_loader(suite))
                else:
                    new_rows, diffs = subsample_greedy(parsed)
                folder = cfg.protocols[factor].get("folder", factor) if factor in cfg.protocols else factor
                dest = out_root / folder / model / suite / f"{src.name}-{factor.lower()}"
                write_rescored(dest, manifest, new_rows, diffs, src, base, factor, spec["extra"])
                log.append({"model": model, "suite": suite, "part": str(src), "records": len(new_rows),
                            "diffs": len(diffs), "dest": str(dest)})
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/analysis_phase2.yaml")
    ap.add_argument("--factor", required=True, choices=["F7", "F8"])
    ap.add_argument("--out-root", default=None, help="default: the config's rescored_v3 root")
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--suites", nargs="*", default=None)
    args = ap.parse_args(argv)
    cfg = load_phase2_config(args.config)
    out = Path(args.out_root) if args.out_root else cfg.root_path("rescored_v3")
    for e in rescore_v3_parts(cfg, args.factor, out, args.models, args.suites):
        print(f"{e['model']}/{e['suite']}: {e['records']} records, {e['diffs']} changed -> {e['dest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
