"""Rescore-only factors F7, F8, F10 (and the data side of F9).

These read an existing run's records, recompute scores with a different
rule, and write a NEW run folder under --out-root (default ``rescored/``),
laid out like a real run so the analysis loader reads it unchanged:

    <out-root>/<F7|F8|F10>/<model>/<suite>/<run_id>/
        parsed_results.jsonl  summary.json  run_manifest.json  rescore_diffs.jsonl

Nothing is ever written next to the source records, and --out-root may not
be inside results/, results_smoke/ or results_v2/.

F7  lenient parsing   re-parse raw_output with ``lenient=True`` (invalid
                      backslash-escape repair only). No new key aliases: the
                      Granite-3.0 ``"tool"``-key gap stays unfixed
                      (DEVIATIONS.md 2026-10-07).
F8  relaxed intent    args_intent_match replaced by analysis/audit/
                      relaxed_intent.relaxed_compatible with all 5 causes.
F10 1 vs 3 trials     keep trial_index 0 (greedy) only.
F9  CI gate           no data change; the analysis computes the CI-gate label
                      from D's records (scripts/rescore_f9_ci_gate.py writes it out).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "analysis" / "audit"))

from upgradecanary.evaluator import evaluate, evaluate_fault_reporting, summarize  # noqa: E402
from upgradecanary.parsing import extract_fault_report, extract_tool_call_with_format  # noqa: E402
from upgradecanary.perturbations.runtime_faults import Fault  # noqa: E402
from upgradecanary.perturbations.schema_drift import Drift, drifted_schema  # noqa: E402
from upgradecanary.runner import _safe_execute, task_base_schema  # noqa: E402
from upgradecanary.tasks import load_tasks  # noqa: E402
from upgradecanary.utils import read_jsonl, write_json, write_jsonl  # noqa: E402

from .config import assert_safe_output_dir, load_config  # noqa: E402
from .loader import Store  # noqa: E402

TOOL_CALL_CONDITIONS = {"baseline", "schema_drift"}


def _raw_index(raw_rows: list[dict]) -> dict[tuple, dict]:
    return {(r["task_id"], r["condition"], int(r.get("trial_index", 0))): r for r in raw_rows}


def _row_context(task, parsed_row):
    drift = Drift(**parsed_row["drift"]) if parsed_row.get("drift") else None
    fault = Fault(**parsed_row["fault"]) if parsed_row.get("fault") else None
    base_schema = task_base_schema(task)
    return drift, fault, base_schema, drifted_schema(base_schema, drift)


def rescore_lenient(parsed_rows: list[dict], raw_rows: list[dict], tasks_by_id: dict) -> tuple[list[dict], list[dict]]:
    """F7. Returns (new parsed rows, diffs)."""
    raw_by_key = _raw_index(raw_rows)
    out, diffs = [], []
    for row in parsed_rows:
        cond = row["condition"]
        raw = raw_by_key[(row["task_id"], cond, int(row.get("trial_index", 0)))]["raw_output"]
        new = dict(row)
        if cond in TOOL_CALL_CONDITIONS:
            task = tasks_by_id[row["task_id"]]
            drift, fault, base_schema, schema = _row_context(task, row)
            strict = cond == "baseline"
            call, fmt = extract_tool_call_with_format(raw, lenient=True)
            exec_result = _safe_execute(call, schema, drift, fault, strict, canonical_schema=base_schema)
            metrics = evaluate(cond, task.expected_call, call, exec_result, drift, fault, None,
                               schema, strict, acceptable=task.acceptable)
            new.update(parsed_call=call, detected_format=fmt, exec_result=exec_result, metrics=metrics)
        elif cond == "fault_reporting":
            fault = Fault(**row["fault"]) if row.get("fault") else None
            report = extract_fault_report(raw, lenient=True)
            new.update(parsed_call=report, metrics=evaluate_fault_reporting(report, fault))
        else:
            out.append(new)
            continue
        if new["metrics"]["score"] != row["metrics"]["score"] or new["parsed_call"] != row["parsed_call"]:
            diffs.append({"task_id": row["task_id"], "condition": cond, "trial_index": row.get("trial_index", 0),
                          "old_score": row["metrics"]["score"], "new_score": new["metrics"]["score"],
                          "old_parsed_call": row["parsed_call"], "new_parsed_call": new["parsed_call"]})
        out.append(new)
    return out, diffs


def rescore_relaxed_intent(parsed_rows: list[dict], tasks_by_id: dict) -> tuple[list[dict], list[dict]]:
    """F8. Only args_intent_match changes (and the score derived from it)."""
    from relaxed_intent import ALL_CAUSES, relaxed_compatible

    out, diffs = [], []
    for row in parsed_rows:
        new = dict(row)
        m = row["metrics"]
        if row["condition"] in TOOL_CALL_CONDITIONS and row.get("parsed_call") and not m.get("args_intent_match"):
            task = tasks_by_id[row["task_id"]]
            drift, _fault, _base, schema = _row_context(task, row)
            ok = relaxed_compatible(row["parsed_call"].get("arguments", {}), task.expected_call["arguments"],
                                    drift, task.acceptable, schema, set(ALL_CAUSES))
            if ok:
                nm = dict(m)
                nm["args_intent_match"] = True
                nm["score"] = float(
                    nm["parse_ok"] and nm["tool_name_ok"] and True
                    and nm["args_valid_under_drift"] and nm["executor_ok"]
                )
                new["metrics"] = nm
                if nm["score"] != m["score"]:
                    diffs.append({"task_id": row["task_id"], "condition": row["condition"],
                                  "trial_index": row.get("trial_index", 0),
                                  "old_score": m["score"], "new_score": nm["score"]})
        out.append(new)
    return out, diffs


def subsample_greedy(parsed_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """F10: greedy trial only."""
    return [r for r in parsed_rows if int(r.get("trial_index", 0)) == 0], []


def write_rescored(run_dir: Path, source_manifest: dict, rows: list[dict], diffs: list[dict],
                   source_run_dir: Path, source_protocol: str, factor: str, extra_factors: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(run_dir / "parsed_results.jsonl", rows)
    summary = summarize(rows)
    run_id = f"{source_manifest.get('run_id', source_run_dir.name)}-{factor.lower()}"
    summary["run_id"] = run_id
    write_json(run_dir / "summary.json", summary)
    write_jsonl(run_dir / "rescore_diffs.jsonl", diffs)
    manifest = dict(source_manifest)
    manifest["run_id"] = run_id
    manifest["num_records"] = len(rows)
    manifest["rescore"] = {"factor": factor, "source_protocol": source_protocol,
                           "source_run_dir": str(source_run_dir), "n_diffs": len(diffs)}
    manifest["run_factors"] = {**source_manifest.get("run_factors", {}), **extra_factors}
    write_json(run_dir / "run_manifest.json", manifest)


FACTORS: dict[str, dict[str, Any]] = {
    "F7": {"needs_raw": True, "extra": {"F7_parsing": "lenient"}},
    "F8": {"needs_raw": False, "extra": {"F8_intent_rule": "relaxed"}},
    "F10": {"needs_raw": False, "extra": {"F10_trials": 1}},
}


def rescore_tree(cfg, factor: str, source_protocol: str, out_root: Path, models=None, suites=None,
                 tasks_loader: Callable[[str], dict] | None = None) -> list[dict]:
    """Rescore every (model, suite) run under ``source_protocol``; returns a
    per-run log. ``tasks_loader(suite)`` -> {task_id: Task} (default: cfg.task_data)."""
    out_root = assert_safe_output_dir(out_root)
    store = Store(cfg)
    if tasks_loader is None:
        def tasks_loader(suite: str) -> dict:
            path = Path(cfg.raw["task_data"][suite])
            return {t.task_id: t for t in load_tasks(path if path.is_absolute() else cfg.base_dir / path)}
    spec = FACTORS[factor]
    log = []
    for model in models or list(cfg.models):
        for suite in suites or cfg.suites:
            sdir = store.suite_dir(source_protocol, model, suite)
            src = Store._find_run_dir(sdir)
            parsed = read_jsonl(src / "parsed_results.jsonl")
            manifest_path = src / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
            if factor == "F7":
                new_rows, diffs = rescore_lenient(parsed, read_jsonl(src / "raw_outputs.jsonl"), tasks_loader(suite))
            elif factor == "F8":
                new_rows, diffs = rescore_relaxed_intent(parsed, tasks_loader(suite))
            else:
                new_rows, diffs = subsample_greedy(parsed)
            folder = cfg.protocols[factor].get("folder", factor) if factor in cfg.protocols else factor
            dest = out_root / folder / model / suite / f"{src.name}-{factor.lower()}"
            write_rescored(dest, manifest, new_rows, diffs, src, source_protocol, factor, spec["extra"])
            log.append({"model": model, "suite": suite, "records": len(new_rows), "diffs": len(diffs), "dest": str(dest)})
    return log


def _default_out_root(cfg) -> Path:
    root = Path(cfg.raw["rescored_root"])
    return root if root.is_absolute() else cfg.base_dir / root


def cli(factor: str, argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=f"{factor} rescore: reads existing records, writes a new folder.")
    ap.add_argument("--config", default=str(REPO_ROOT / "configs" / "analysis_official_folders.yaml"))
    ap.add_argument("--source-protocol", default=None, help="default: config base_protocol (D)")
    ap.add_argument("--out-root", default=None, help="default: config rescored_root")
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--suites", nargs="*", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    out_root = Path(args.out_root) if args.out_root else _default_out_root(cfg)
    log = rescore_tree(cfg, factor, args.source_protocol or cfg.base_protocol, out_root, args.models, args.suites)
    for entry in log:
        print(f"{entry['model']}/{entry['suite']}: {entry['records']} records, {entry['diffs']} changed -> {entry['dest']}")
    return 0
