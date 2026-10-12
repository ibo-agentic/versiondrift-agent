"""Kaggle hardware check (DEVIATIONS draft, F5/R_F5 on Kaggle T4).

The same D configuration and the same Q4_K_M files were run on the laptop
(protocol D) and on Kaggle (protocol KAGGLE_HWCHECK) for an adjacent upgrade
pair (llama3 -> llama31). Two readings, both pure functions of run records:

pair level  (hwcheck_pair_rows)   per suite: the pair's stress diff on Kaggle
            minus the same pair's stress diff on the laptop. This
            "hardware-check difference" is the size of a pair-level change
            that machine alone can produce; F5 flips smaller than it are
            labeled "within hardware noise".
run level   (hwcheck_run_rows)    per model x suite: greedy-trial (trial_index
            0) mean score and parse rate, Kaggle vs laptop, with the 0.03
            pass criterion. Parse failure == failure bucket "format" (a
            record that fails with nothing parseable), see loader.failure_bucket.

Nothing here runs a model; no Kaggle-vs-laptop comparison is made for any
protocol other than the one named in the config's ``hardware_check`` block.
"""

from __future__ import annotations

from typing import Any

from .engine import Analysis
from .loader import MissingRun

DEFAULT_TOLERANCE = 0.03


def hwcheck_spec(an: Analysis) -> dict | None:
    return an.cfg.raw.get("hardware_check")


def _runs(an: Analysis, spec: dict, model: str, suite: str):
    return (an.store.get(spec["laptop_protocol"], model, suite),
            an.store.get(spec["kaggle_protocol"], model, suite))


def hwcheck_pair_rows(an: Analysis) -> list[dict[str, Any]]:
    spec = hwcheck_spec(an)
    if not spec:
        return []
    pair = dict(spec["pair"])
    name = an.cfg.pair_name(pair)
    out: list[dict[str, Any]] = []
    for suite in an.cfg.suites:
        try:
            lap = an.row_from_runs(spec["laptop_protocol"], pair, suite,
                                   an.store.get(spec["laptop_protocol"], pair["old"], suite),
                                   an.store.get(spec["laptop_protocol"], pair["new"], suite), confound="")
            kag = an.row_from_runs(spec["kaggle_protocol"], pair, suite,
                                   an.store.get(spec["kaggle_protocol"], pair["old"], suite),
                                   an.store.get(spec["kaggle_protocol"], pair["new"], suite), confound="")
        except MissingRun as exc:
            an.hwcheck_notes.append(f"pair {name}/{suite}: {exc}")
            continue
        if lap is None or kag is None:
            an.hwcheck_notes.append(f"pair {name}/{suite}: runs could not be compared (no matched records)")
            continue
        diff = kag["stress_diff"] - lap["stress_diff"]
        out.append({
            "pair": name, "suite": suite,
            "laptop_stress_diff": lap["stress_diff"], "kaggle_stress_diff": kag["stress_diff"],
            "hardware_diff": diff, "abs_hardware_diff": abs(diff),
            "laptop_label_point": lap["label_point"], "kaggle_label_point": kag["label_point"],
            "label_point_changed": lap["label_point"] != kag["label_point"],
            "laptop_ci_lo": lap["ci_lo"], "laptop_ci_hi": lap["ci_hi"],
            "kaggle_ci_lo": kag["ci_lo"], "kaggle_ci_hi": kag["ci_hi"],
            "laptop_label_ci": lap["label_ci"], "kaggle_label_ci": kag["label_ci"],
            "baseline_hardware_diff": _sub(kag["baseline_diff"], lap["baseline_diff"]),
            "drift_hardware_diff": _sub(kag["drift_diff"], lap["drift_diff"]),
            "fault_hardware_diff": _sub(kag["fault_diff"], lap["fault_diff"]),
            "n_records_laptop": lap["n_records"], "n_records_kaggle": kag["n_records"],
        })
    return out


def _sub(a, b):
    return None if a is None or b is None else a - b


def greedy_stats(run) -> dict[str, float]:
    """Mean score and parse rate over this run's greedy (trial_index 0) records."""
    keys = [k for k in run.keys if k[4] == 0]
    n = len(keys)
    if n == 0:
        return {"n": 0, "score": float("nan"), "parse_rate": float("nan")}
    score = sum(run.keys[k][0] for k in keys) / n
    parse_ok = sum(1 for k in keys if run.keys[k][1] != "format") / n
    return {"n": n, "score": score, "parse_rate": parse_ok}


def hwcheck_run_rows(an: Analysis) -> list[dict[str, Any]]:
    spec = hwcheck_spec(an)
    if not spec:
        return []
    tol = float(spec.get("tolerance", DEFAULT_TOLERANCE))
    out: list[dict[str, Any]] = []
    for model in (spec["pair"]["old"], spec["pair"]["new"]):
        for suite in an.cfg.suites:
            try:
                lap, kag = _runs(an, spec, model, suite)
            except MissingRun as exc:
                an.hwcheck_notes.append(f"run {model}/{suite}: {exc}")
                continue
            a, b = greedy_stats(lap), greedy_stats(kag)
            ds, dp = b["score"] - a["score"], b["parse_rate"] - a["parse_rate"]
            out.append({
                "model": model, "suite": suite, "n_greedy_laptop": a["n"], "n_greedy_kaggle": b["n"],
                "laptop_greedy_score": a["score"], "kaggle_greedy_score": b["score"], "score_diff": ds,
                "laptop_parse_rate": a["parse_rate"], "kaggle_parse_rate": b["parse_rate"], "parse_rate_diff": dp,
                "tolerance": tol, "within_tolerance": abs(ds) <= tol and abs(dp) <= tol,
            })
    return out


def hwcheck_summary(pair_rows: list[dict], run_rows: list[dict], expected_runs: int) -> dict[str, Any]:
    """One-line verdict on the hardware check itself (is Kaggle usable?), plus
    the noise bound for labeling F5 flips. Not a verdict about any model pair."""
    complete = len(run_rows) == expected_runs
    return {
        "runs_compared": len(run_rows),
        "runs_expected": expected_runs,
        "all_within_tolerance": bool(run_rows) and complete and all(r["within_tolerance"] for r in run_rows),
        "n_outside_tolerance": sum(1 for r in run_rows if not r["within_tolerance"]),
        "max_abs_hardware_diff": max((r["abs_hardware_diff"] for r in pair_rows), default=None),
        "pair_suites_label_changed": sum(1 for r in pair_rows if r["label_point_changed"]),
    }
