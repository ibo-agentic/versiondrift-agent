"""Run the F7 / F8 / F10 rescore rules on every FINISHED run under a results
root, writing only to a rescored/ folder (never inside results*/).

"Finished" = <protocol>/<model>/<suite>/_status.json says completed with the
expected record count AND exactly one run directory holding 900 parsed and
900 raw records. Anything else is skipped and reported (nothing is guessed).

It reuses vdanalysis/rescore.py's rules unchanged (rescore_lenient,
rescore_relaxed_intent, subsample_greedy, write_rescored); it does not
compute verdicts, gates, pair differences or any cross-run statistic. F9
(CI gate) is NOT run: it only exists as a per-pair verdict table.

Layout of the output (so each source protocol keeps its own tree):
  rescored/<F7|F8|F10>/<model>/<suite>/<run_id>-<f>/             source protocol D
                                                                  (what analysis_official_folders.yaml expects)
  rescored/by_source/<protocol>/<F7|F8|F10>/<model>/<suite>/...   every other source protocol

Existing destination folders are never overwritten (skipped + reported).

Usage:
  python scripts/rescore_all_finished.py --results-root <.../results_v2> [--out-root rescored]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from vdanalysis.config import assert_safe_output_dir  # noqa: E402
from vdanalysis.rescore import (  # noqa: E402
    FACTORS, rescore_lenient, rescore_relaxed_intent, subsample_greedy, write_rescored,
)
from upgradecanary.tasks import load_tasks  # noqa: E402
from upgradecanary.utils import read_jsonl  # noqa: E402

BASE_PROTOCOL = "D"
CONFIG = REPO_ROOT / "configs" / "analysis_official_folders.yaml"


def _count(path: Path) -> int:
    with open(path, encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def find_finished(results_root: Path, expected: int):
    """Yield (protocol, model, suite, run_dir|None, problem|None) for every suite dir."""
    for pdir in sorted(p for p in results_root.iterdir() if p.is_dir() and not p.name.startswith("_")):
        for mdir in sorted(d for d in pdir.iterdir() if d.is_dir() and not d.name.startswith("_")):
            for sdir in sorted(d for d in mdir.iterdir() if d.is_dir()):
                tag = (pdir.name, mdir.name, sdir.name)
                st = sdir / "_status.json"
                try:
                    status = json.loads(st.read_text(encoding="utf-8"))
                except Exception:
                    yield (*tag, None, "no readable _status.json (not finished / still running)")
                    continue
                if not (status.get("completed") and status.get("record_count_ok", True)):
                    yield (*tag, None, f"status not completed: {status.get('error') or status.get('num_records')}")
                    continue
                runs = sorted(d for d in sdir.iterdir() if d.is_dir() and (d / "parsed_results.jsonl").exists())
                if len(runs) != 1:
                    yield (*tag, None, f"{len(runs)} run directories (need exactly 1): {[r.name for r in runs]}")
                    continue
                n_p = _count(runs[0] / "parsed_results.jsonl")
                raw = runs[0] / "raw_outputs.jsonl"
                n_r = _count(raw) if raw.exists() else -1
                if n_p != expected or n_r != expected:
                    yield (*tag, None, f"record counts parsed={n_p}, raw={n_r}, expected {expected}")
                    continue
                yield (*tag, runs[0], None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-root", required=True, help="read-only: a results_v2 folder")
    ap.add_argument("--out-root", default=str(REPO_ROOT / "rescored"))
    ap.add_argument("--factors", nargs="+", default=["F7", "F8", "F10"], choices=["F7", "F8", "F10"])
    ap.add_argument("--protocols", nargs="*", default=None, help="default: every protocol folder found")
    args = ap.parse_args(argv)

    results_root = Path(args.results_root).resolve()
    out_root = assert_safe_output_dir(args.out_root)
    if results_root == out_root or results_root in out_root.parents:
        print("refusing: out-root is inside the results root", file=sys.stderr)
        return 2
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    expected = int(cfg["expected_records_per_run"])
    task_paths = {s: (CONFIG.parent / p) for s, p in cfg["task_data"].items()}
    tasks_cache: dict[str, dict] = {}

    def tasks_for(suite: str) -> dict:
        if suite not in tasks_cache:
            tasks_cache[suite] = {t.task_id: t for t in load_tasks(task_paths[suite])}
        return tasks_cache[suite]

    log: list[dict] = []
    for protocol, model, suite, run_dir, problem in find_finished(results_root, expected):
        if args.protocols and protocol not in args.protocols:
            continue
        entry = {"protocol": protocol, "model": model, "suite": suite}
        if suite not in task_paths:
            log.append({**entry, "status": "skipped", "detail": f"unknown suite {suite!r}"})
            continue
        if problem:
            log.append({**entry, "status": "skipped", "detail": problem})
            continue
        try:
            parsed = read_jsonl(run_dir / "parsed_results.jsonl")
            raw = read_jsonl(run_dir / "raw_outputs.jsonl")
            mpath = run_dir / "run_manifest.json"
            manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
            tasks = tasks_for(suite)
            for factor in args.factors:
                if factor == "F7":
                    rows, diffs = rescore_lenient(parsed, raw, tasks)
                elif factor == "F8":
                    rows, diffs = rescore_relaxed_intent(parsed, tasks)
                else:
                    rows, diffs = subsample_greedy(parsed)
                base = out_root if protocol == BASE_PROTOCOL else out_root / "by_source" / protocol
                dest = base / factor / model / suite / f"{run_dir.name}-{factor.lower()}"
                if dest.exists():
                    log.append({**entry, "factor": factor, "status": "exists-not-overwritten", "dest": str(dest)})
                    continue
                write_rescored(dest, manifest, rows, diffs, run_dir, protocol, factor, FACTORS[factor]["extra"])
                log.append({**entry, "factor": factor, "status": "written", "records": len(rows),
                            "changed": len(diffs), "dest": str(dest)})
        except Exception as exc:  # noqa: BLE001 -- report, keep going
            log.append({**entry, "status": "ERROR", "detail": f"{type(exc).__name__}: {exc}"})

    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "_rescore_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    written = [e for e in log if e["status"] == "written"]
    folders = sorted({(e["protocol"], e["model"], e["suite"]) for e in written})
    print(f"source runs rescored: {len(folders)}; rescored folders written: {len(written)}")
    for st in ("skipped", "exists-not-overwritten", "ERROR"):
        for e in (x for x in log if x["status"] == st):
            print(f"  {st}: {e['protocol']}/{e['model']}/{e['suite']} {e.get('factor', '')} {e.get('detail', '')}")
    return 1 if any(e["status"] == "ERROR" for e in log) else 0


if __name__ == "__main__":
    sys.exit(main())
