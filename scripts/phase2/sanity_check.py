"""Read-only sanity check of finished Phase 2 runs.

    python -m scripts.phase2.sanity_check W1_laptop D/gemma2_2b/synthetic [more run ids] [--out report.md]

For each run: the status file (completed, record count against the manifest), errors, the trial seeds and
temperatures the records carry, and whether the run merges with Phase 1's records (the very merge the analysis
does: no duplicate (task, condition, trial), byte-identical prompts, matching drift/fault types, seeds equal to
seed base + trial index). It then compares the parse rate and truncation rate of the new trials with Phase 1's
trials of the same run (all three, and the two sampled ones, since every new trial is sampled).

Parse rate = share of records with metrics.parse_ok (tool-call conditions, and all conditions). Truncation rate =
share of raw outputs with truncated = true. Nothing is written except the optional report.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.phase2.plan import load_manifest  # noqa: E402
from scripts.phase2.run_one import status_path  # noqa: E402
from vdanalysis.phase2.config import load_phase2_config  # noqa: E402
from vdanalysis.phase2.merge import MergeError, MergedStore  # noqa: E402

TOOL_CALL = ("baseline", "schema_drift")


def _rows(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _run_dir(root: Path, out_dir: str) -> Path | None:
    c = [Path(p) for p in glob.glob(str(root / out_dir / "*")) if (Path(p) / "parsed_results.jsonl").exists()]
    return c[0] if len(c) == 1 else None


def rates(parsed: list[dict], raw: list[dict], trials: set[int]) -> dict:
    p = [r for r in parsed if int(r["trial_index"]) in trials]
    q = [r for r in raw if int(r["trial_index"]) in trials]
    tc = [r for r in p if r["condition"] in TOOL_CALL]
    return {"n_records": len(p),
            "parse_rate_tool_call": sum(bool(r["metrics"].get("parse_ok")) for r in tc) / len(tc) if tc else None,
            "parse_rate_all": sum(bool(r["metrics"].get("parse_ok")) for r in p) / len(p) if p else None,
            "truncation_rate": sum(bool(r.get("truncated")) for r in q) / len(q) if q else None}


def check_run(manifest: str, entry: dict, cfg, root: Path = REPO_ROOT, phase1_root: Path | None = None) -> dict:
    res: dict = {"id": entry["id"], "problems": []}
    P = res["problems"].append
    sp = status_path(entry, root)
    try:
        st = json.loads(sp.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        P(f"no readable _status.json: {exc}")
        return res
    res["status"] = {k: st.get(k) for k in ("completed", "num_records", "expected_records", "record_count_ok", "elapsed_seconds", "error")}
    if st.get("error"):
        P(f"run error: {st['error']}")
    if not st.get("completed"):
        P("run not complete")
    if st.get("num_records") != entry["expected_records"]:
        P(f"{st.get('num_records')} records, manifest expects {entry['expected_records']}")
    rd = _run_dir(root, entry["output_dir"])
    if rd is None:
        P("not exactly one run folder")
        return res
    parsed, raw = _rows(rd / "parsed_results.jsonl"), _rows(rd / "raw_outputs.jsonl")
    res["records"] = len(parsed)
    res["trial_seeds_in_records"] = sorted({int(r["seed"]) for r in parsed})
    res["temperatures_in_records"] = sorted({float(r["temperature"]) for r in parsed})
    res["trial_indices_in_records"] = sorted({int(r["trial_index"]) for r in parsed})
    if res["trial_seeds_in_records"] != sorted(entry["trial_seeds"]):
        P(f"trial seeds {res['trial_seeds_in_records']} != manifest {entry['trial_seeds']}")
    if res["temperatures_in_records"] != sorted(set(entry["temperatures"])):
        P(f"temperatures {res['temperatures_in_records']} != manifest")
    per_trial = {}
    for r in parsed:
        per_trial[r["trial_index"]] = per_trial.get(r["trial_index"], 0) + 1
    res["records_per_trial"] = dict(sorted(per_trial.items()))
    # the merge the analysis does (Phase 1 part + this part)
    try:
        run = MergedStore(cfg).get(entry["folder"], entry["model"], entry["suite"])
        res["merge"] = {"ok": True, "trials": run.trials, "records": len(run), "tasks": len(run.tasks),
                        "parts": [str(p.relative_to(root)) if root in p.parents else str(p) for p in run.parts],
                        "warnings": run.warnings, "trial_seeds": {t: run.trial_info[t][1] for t in run.trials},
                        "temperatures": {t: run.trial_info[t][0] for t in run.trials}}
        if run.warnings:
            P(f"merge warnings: {run.warnings}")
        if run.trials != list(range(10)):
            P(f"merged trials {run.trials}")
    except (MergeError, FileNotFoundError, ValueError) as exc:
        res["merge"] = {"ok": False, "error": str(exc)}
        P(f"merge with Phase 1 failed: {exc}")
    # Phase 1 part of the same run
    p1 = None
    for part, spec in MergedStore(cfg).part_dirs(entry["folder"], entry["model"], entry["suite"]):
        if spec.root == "results_root":
            p1 = MergedStore._find_run_dir(part)
    if p1 is not None:
        p1_parsed, p1_raw = _rows(p1 / "parsed_results.jsonl"), _rows(p1 / "raw_outputs.jsonl")
        res["phase1_run"] = p1.name
        res["new_trials"] = rates(parsed, raw, set(range(7)))
        res["phase1_trials_all"] = rates(p1_parsed, p1_raw, {0, 1, 2})
        res["phase1_trials_sampled"] = rates(p1_parsed, p1_raw, {1, 2})
    return res


def report(results: list[dict]) -> str:
    L = ["# Phase 2 sanity check", ""]
    f = lambda x: "n/a" if x is None else f"{100 * x:.2f}%"
    for r in results:
        L += [f"## {r['id']}", "", f"problems: {r['problems'] or 'none'}"]
        if "status" in r:
            s = r["status"]
            L.append(f"- status: completed={s['completed']}, records {s['num_records']} / expected {s['expected_records']}, "
                     f"{(s['elapsed_seconds'] or 0) / 3600:.2f} h, error={s['error']}")
        if "records" in r:
            L.append(f"- records per trial_index: {r['records_per_trial']}; trial seeds {r['trial_seeds_in_records']}; "
                     f"temperatures {r['temperatures_in_records']}")
        m = r.get("merge")
        if m:
            L.append(f"- merge with Phase 1: {'PASS' if m['ok'] else 'FAIL'}" + (
                f" ({m['records']} records, {m['tasks']} tasks, trials {m['trials']}, seeds {m['trial_seeds']}, warnings {m['warnings']})"
                if m["ok"] else f" - {m['error']}"))
        if "new_trials" in r:
            L += ["", "| trials | records | parse rate (tool-call) | parse rate (all conditions) | truncation rate |", "|---|---|---|---|---|"]
            for name, k in (("new 4-10 (7 sampled)", "new_trials"), ("Phase 1 1-3 (greedy + 2 sampled)", "phase1_trials_all"),
                            ("Phase 1 2-3 (2 sampled)", "phase1_trials_sampled")):
                x = r[k]
                L.append(f"| {name} | {x['n_records']} | {f(x['parse_rate_tool_call'])} | {f(x['parse_rate_all'])} | {f(x['truncation_rate'])} |")
        L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest")
    ap.add_argument("run_ids", nargs="+")
    ap.add_argument("--analysis", default=str(REPO_ROOT / "configs" / "analysis_phase2.yaml"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    cfg = load_phase2_config(args.analysis)
    m = load_manifest(args.manifest)
    by_id = {e["id"]: e for e in m["runs"]}
    results = [check_run(args.manifest, by_id[i], cfg) for i in args.run_ids]
    text = report(results)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0 if all(not r["problems"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
