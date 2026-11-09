"""EXPLORATORY, Phase 1 data only (results_v2/, analysis_out/). Reads nothing from results_v3/.

Writes into analysis/exploratory/:
  decisions_D_halfwidth.csv        30 D decisions: stress diff, 95% CI, half-width
  mde_by_pair.csv, mde_by_suite.csv  minimum detectable effect (80% power, alpha 0.05, paired, 100 tasks)
  flip_types_by_factor.csv         flips split into sign reversals and boundary crossings
  failure_types_by_model_protocol.csv
  _numbers.json                    everything the report quotes

Run from the repo root:  python analysis/exploratory/phase1_power_and_failures.py
"""

from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
OUT = Path(__file__).resolve().parent

from vdanalysis.config import load_config  # noqa: E402
from vdanalysis.engine import Analysis  # noqa: E402

Z_ALPHA = 1.959964      # two-sided alpha 0.05
Z_POWER = 0.841621      # power 0.80
N_TASKS = 100

CFG_PATH = REPO / "configs" / "analysis_official_folders.yaml"
RESULTS_V2 = REPO / "results_v2"


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict]) -> None:
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- decisions + MDE
def decisions_and_mde(cfg) -> dict:
    dec = read_csv(REPO / "analysis_out" / "decisions_D.csv")
    rows = []
    for r in dec:
        lo, hi, d = float(r["ci_lo"]), float(r["ci_hi"]), float(r["stress_diff"])
        rows.append({"pair": r["pair"], "suite": r["suite"], "stress_diff": round(d, 4), "ci_lo": round(lo, 4),
                     "ci_hi": round(hi, 4), "ci_half_width": round((hi - lo) / 2, 4),
                     "label_point": r["label_point"], "label_ci": r["label_ci"], "n_tasks": r["n_tasks"],
                     "n_records": r["n_records"]})
    write_csv(OUT / "decisions_D_halfwidth.csv", rows)

    an = Analysis(cfg, with_ci=False)
    stress = list(cfg.stress_conditions) if hasattr(cfg, "stress_conditions") else ["schema_drift", "fault_reporting"]
    mde_rows = []
    max_dev = 0.0
    for pair in cfg.pairs:
        for suite in cfg.suites:
            old = an.run_for("D", pair["old"], suite)
            new = an.run_for("D", pair["new"], suite)
            keys = [k for k in set(old.keys) & set(new.keys) if k[1] in stress]
            per_task: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
            for k in keys:
                per_task[k[0]][k[1]].append(new.keys[k][0] - old.keys[k][0])
            d_t = []
            for t, byc in per_task.items():
                d_t.append(statistics.fmean(statistics.fmean(v) for v in byc.values()))
            sd = statistics.stdev(d_t)
            mean_dt = statistics.fmean(d_t)
            ref = next(float(x["stress_diff"]) for x in dec if x["pair"] == cfg.pair_name(pair) and x["suite"] == suite)
            max_dev = max(max_dev, abs(mean_dt - ref))
            mde_rows.append({"pair": cfg.pair_name(pair), "suite": suite, "n_tasks": len(d_t), "mean_task_diff": round(mean_dt, 4),
                             "sd_task_diff": round(sd, 4),
                             "mde_80": round((Z_ALPHA + Z_POWER) * sd / math.sqrt(N_TASKS), 4)})
    write_csv(OUT / "mde_by_pair.csv", mde_rows)
    by_suite = []
    for suite in cfg.suites:
        rs = [r for r in mde_rows if r["suite"] == suite]
        pooled_sd = math.sqrt(statistics.fmean(r["sd_task_diff"] ** 2 for r in rs))
        by_suite.append({"suite": suite, "n_pairs": len(rs), "pooled_sd_task_diff": round(pooled_sd, 4),
                         "mde_80_pooled": round((Z_ALPHA + Z_POWER) * pooled_sd / math.sqrt(N_TASKS), 4),
                         "mde_min_pair": min(r["mde_80"] for r in rs), "mde_max_pair": max(r["mde_80"] for r in rs)})
    write_csv(OUT / "mde_by_suite.csv", by_suite)
    return {"decisions": rows, "mde_by_pair": mde_rows, "mde_by_suite": by_suite, "max_dev_mean_vs_stress_diff": max_dev}


# ---------------------------------------------------------------- flip types
def flip_types(cfg) -> list[dict]:
    flips = read_csv(REPO / "analysis_out" / "factor_flips_long.csv")
    out = []
    for fac in cfg.factors:
        rows_f = [r for r in flips if r["factor"] == fac]
        min_changed = int(cfg.factors[fac].get("main_min_changed", 0))
        for variant in ("main", "all"):
            sel = [r for r in rows_f if (variant == "all") or (not r["confounding"] and int(r["n_models_changed"]) >= min_changed)]
            fl = [r for r in sel if r["flipped"] == "True"]
            sign = [r for r in fl if {r["d_label"], r["factor_label"]} == {"harmful", "beneficial"}]
            bnd = [r for r in fl if "neutral" in (r["d_label"], r["factor_label"])]
            to_neutral = [r for r in bnd if r["factor_label"] == "neutral"]
            from_neutral = [r for r in bnd if r["d_label"] == "neutral"]
            out.append({"factor": fac, "variant": variant, "n_decisions": len(sel), "n_flips": len(fl),
                        "sign_reversals_harmful_beneficial": len(sign), "boundary_crossings_via_neutral": len(bnd),
                        "of_which_D_label_to_neutral": len(to_neutral), "of_which_neutral_to_nonneutral": len(from_neutral)})
    write_csv(OUT / "flip_types_by_factor.csv", out)
    return out


# ---------------------------------------------------------------- failure types
TOOL_CALL = ("baseline", "schema_drift")


def run_dir(proto: str, model: str, suite: str) -> Path | None:
    folder = "F3_rerun" if (proto == "F3" and model == "granite30") else proto
    d = RESULTS_V2 / folder / model / suite
    if not (d / "_status.json").exists():
        return None
    try:
        if not json.loads((d / "_status.json").read_text(encoding="utf-8")).get("completed"):
            return None
    except Exception:  # noqa: BLE001
        return None
    cands = [p for p in d.iterdir() if p.is_dir() and (p / "parsed_results.jsonl").exists()]
    return cands[0] if len(cands) == 1 else None


def classify_tool_call(m: dict) -> str | None:
    if float(m.get("score", 0)) == 1.0:
        return None
    if not m.get("parse_ok"):
        return "malformed_unparsed"
    if not m.get("tool_name_ok"):
        return "wrong_tool_name"
    if not m.get("args_intent_match") or not m.get("args_valid_under_drift"):
        return "wrong_or_invalid_args"
    if not m.get("executor_ok"):
        return "executor_fail"
    return "other"


def classify_fault(m: dict) -> str | None:
    if float(m.get("score", 0)) == 1.0:
        return None
    if not m.get("parse_ok"):
        return "malformed_unparsed"
    if not m.get("status_ok"):
        return "wrong_status"
    if not m.get("no_fabrication", True):
        return "fabricated_answer"
    return "other"


def failure_types() -> list[dict]:
    protos = sorted(p.name for p in RESULTS_V2.iterdir()
                    if p.is_dir() and not p.name.startswith("_") and p.name not in ("KAGGLE_HWCHECK", "F3_rerun"))
    models = sorted(p.name for p in (RESULTS_V2 / "D").iterdir() if p.is_dir())
    rows, skipped = [], []
    for proto in protos:
        for model in models:
            if not (RESULTS_V2 / ("F3_rerun" if (proto == "F3" and model == "granite30") else proto) / model).exists():
                continue
            tc = defaultdict(int)
            fr = defaultdict(int)
            n_suites = 0
            for suite in ("synthetic", "bfcl_simple", "bfcl_multiple"):
                rd = run_dir(proto, model, suite)
                if rd is None:
                    skipped.append(f"{proto}/{model}/{suite}")
                    continue
                n_suites += 1
                with open(rd / "parsed_results.jsonl", encoding="utf-8") as fh:
                    for line in fh:
                        r = json.loads(line)
                        m = r["metrics"]
                        if r["condition"] in TOOL_CALL:
                            tc["n"] += 1
                            c = classify_tool_call(m)
                            if c:
                                tc[c] += 1
                        elif r["condition"] == "fault_reporting":
                            fr["n"] += 1
                            c = classify_fault(m)
                            if c:
                                fr[c] += 1
            if not n_suites:
                continue
            row = {"protocol": proto, "model": model, "n_suites": n_suites, "tool_call_records": tc["n"]}
            for k in ("malformed_unparsed", "wrong_tool_name", "wrong_or_invalid_args", "executor_fail", "other"):
                row[f"tc_{k}"] = tc[k]
            row["tc_fail_total"] = sum(tc[k] for k in ("malformed_unparsed", "wrong_tool_name", "wrong_or_invalid_args", "executor_fail", "other"))
            row["fault_reporting_records"] = fr["n"]
            for k in ("malformed_unparsed", "wrong_status", "fabricated_answer", "other"):
                row[f"fr_{k}"] = fr[k]
            row["fr_fail_total"] = sum(fr[k] for k in ("malformed_unparsed", "wrong_status", "fabricated_answer", "other"))
            rows.append(row)
    write_csv(OUT / "failure_types_by_model_protocol.csv", rows)
    (OUT / "_skipped_runs.txt").write_text("\n".join(skipped), encoding="utf-8")
    return rows


def main() -> None:
    cfg = load_config(CFG_PATH)
    nums = {"decisions_mde": decisions_and_mde(cfg), "flip_types": flip_types(cfg), "failures": failure_types()}
    (OUT / "_numbers.json").write_text(json.dumps(nums, indent=1), encoding="utf-8")
    print("max |mean per-task diff - stress diff| =", nums["decisions_mde"]["max_dev_mean_vs_stress_diff"])
    print("failure rows:", len(nums["failures"]))


if __name__ == "__main__":
    main()
