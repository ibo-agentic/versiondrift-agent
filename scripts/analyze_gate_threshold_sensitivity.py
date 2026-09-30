"""Release-gate threshold sensitivity and canary calibration.

Uses existing runs only. Records matched on (task_id, condition, drift type,
fault type, trial_index). Four upgrade decisions are evaluated:
Mistral v0.1->v0.2, v0.2->v0.3, v0.1->v0.3, and Qwen2.5->Qwen3.

For each decision and canary size k, the canary is selected by cross-pair
informativeness (mean |task stress diff| over the OTHER decisions, with a
category-coverage pass) — never using the decision being evaluated. For each
decision threshold t in THRESHOLDS the full-suite diff of that decision is
the truth label (harmful < -t / beneficial > +t / neutral otherwise) and the
canary diff is the prediction. Aggregates over the four decisions: accuracy,
sign accuracy, false-accept, false-reject, neutral-call rate, and the
overflag rate of borderline-neutral truths.

Calibration: full_suite_diff ~ alpha * canary_diff (least squares through
the origin). Leave-one-upgrade-out and family-transfer (Mistral<->Qwen)
validation; reports magnitude MAE and decision accuracy with raw vs
calibrated predictions.

Usage:
    python scripts/analyze_gate_threshold_sensitivity.py [RUN_DIR ...]

With no arguments the five known run folders are used.
"""

from __future__ import annotations

import json
import os
import sys

KS = [10, 20, 30, 40, 50]
THRESHOLDS = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]
STRESS = ("schema_drift", "runtime_fault")

DEFAULT_RUNS = {
    "m1": r"results\upgradecanary-real-trials-itlwas-v0.1_seed1234_20260929T120210Z",
    "m2": r"results\upgradecanary-real-trials-itlwas-v0.2_seed1234_20260929T121701Z",
    "m3": r"results\upgradecanary-real-trials-itlwas-v0.3_seed1234_20260929T192811Z",
    "q25": r"results\upgradecanary-real-trials-qwen25_seed1234_20260929T222007Z",
    "q3": r"results\upgradecanary-real-trials-qwen3_seed1234_20260929T230135Z",
}
DECISIONS = [
    ("M v0.1->v0.2", "m1", "m2"),
    ("M v0.2->v0.3", "m2", "m3"),
    ("M v0.1->v0.3", "m1", "m3"),
    ("Qwen2.5->Qwen3", "q25", "q3"),
]


def load_run(run_dir: str) -> dict:
    for name in ("parsed_results_corrected.jsonl", "parsed_results.jsonl"):
        path = os.path.join(run_dir, name)
        if os.path.exists(path):
            recs = {}
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    p = json.loads(line)
                    key = (
                        p["task_id"], p["condition"],
                        (p["drift"] or {}).get("type"), (p["fault"] or {}).get("type"),
                        p.get("trial_index", 0),
                    )
                    recs[key] = p
            return recs
    raise FileNotFoundError(f"no parsed results in {run_dir}")


def functional(m: dict) -> float:
    return 1.0 if (m["parse_ok"] and m["tool_name_ok"] and m["args_intent_match"]
                   and m["args_valid_under_drift"] and m["executor_ok"]) else 0.0


def sc(rec: dict) -> float:
    return functional(rec["metrics"])


def subset_diff(ra: dict, rb: dict, keys: list) -> float:
    return sum(sc(rb[k]) - sc(ra[k]) for k in keys) / len(keys)


def gate_label(d: float, t: float) -> str:
    if d < -t:
        return "harmful"
    if d > t:
        return "beneficial"
    return "neutral"


def select_canary(ranked: list, categories: dict, k: int) -> list:
    selected, covered = [], set()
    for task in ranked:
        if len(selected) >= k:
            break
        if categories[task] - covered:
            selected.append(task)
            covered |= categories[task]
    for task in ranked:
        if len(selected) >= k:
            break
        if task not in selected:
            selected.append(task)
    return selected


def fit_alpha(full_diffs: list, canary_diffs: list) -> float:
    denom = sum(c * c for c in canary_diffs)
    return sum(f * c for f, c in zip(full_diffs, canary_diffs)) / denom if denom else 0.0


def main(argv: list[str]) -> None:
    recs = {label: load_run(d) for label, d in DEFAULT_RUNS.items()}
    common = sorted(set.intersection(*(set(r) for r in recs.values())))
    task_ids = sorted({k[0] for k in common})
    stress_keys = [k for k in common if k[1] in STRESS]
    by_task = {t: [k for k in stress_keys if k[0] == t] for t in task_ids}
    categories = {
        t: {k[2] for k in ks if k[1] == "schema_drift"}
        | {k[3] for k in ks if k[1] == "runtime_fault"}
        for t, ks in by_task.items()
    }
    print(f"matched stress records: {len(stress_keys)} across {len(task_ids)} tasks, {len(DECISIONS)} decisions")

    # Per-decision full diffs and per-task diffs (for cross-pair selection)
    full = {}
    task_diff = {}
    for name, a, b in DECISIONS:
        full[name] = subset_diff(recs[a], recs[b], stress_keys)
        task_diff[name] = {t: subset_diff(recs[a], recs[b], by_task[t]) for t in task_ids}
    print("\nfull-suite stress diffs:")
    for name, _, _ in DECISIONS:
        print(f"  {name}: {full[name]:+.3f} ({gate_label(full[name], 0.05)} at t=0.05)")

    dec_runs = {n: (a, b) for n, a, b in DECISIONS}
    for k in KS:
        print(f"\n=== k={k} ===")
        print("  thr   | acc  sign   FA    FR    neutral overflag")
        canary_diff = {}
        for name, _, _ in DECISIONS:
            others = [d for d, _, _ in DECISIONS if d != name]
            info = {t: sum(abs(task_diff[o][t]) for o in others) / len(others) for t in task_ids}
            ranked = sorted(task_ids, key=lambda t: info[t], reverse=True)
            canary = select_canary(ranked, categories, k)
            ra, rb = recs[dec_runs[name][0]], recs[dec_runs[name][1]]
            canary_diff[name] = subset_diff(ra, rb, [key for t in canary for key in by_task[t]])
        stable = []
        for t in THRESHOLDS:
            n = len(DECISIONS)
            acc = sign = fa = fr = neut = overflag = 0.0
            for name, _, _ in DECISIONS:
                pred = gate_label(canary_diff[name], t)
                truth = gate_label(full[name], t)
                acc += pred == truth
                sign += (canary_diff[name] > 0) == (full[name] > 0)
                fa += truth == "harmful" and pred != "harmful"
                fr += truth == "beneficial" and pred != "beneficial"
                neut += pred == "neutral"
                overflag += truth == "neutral" and pred != "neutral"
            acc, sign, fa, fr, neut, overflag = (x / n for x in (acc, sign, fa, fr, neut, overflag))
            print(f"  {t:.2f} | {acc:.2f} {sign:.2f}  {fa:.2f}  {fr:.2f}  {neut:.2f}   {overflag:.2f}")
            if acc == 1.0 and overflag == 0.0:
                stable.append(t)
        print(f"  stable region (acc=1, no overflag): {stable if stable else 'none'}")

        # Calibration: LOUO alpha and family transfer
        names = [d for d, _, _ in DECISIONS]
        loup_alphas, loup_pred = {}, {}
        for name in names:
            train = [x for x in names if x != name]
            alpha = fit_alpha([full[x] for x in train], [canary_diff[x] for x in train])
            loup_alphas[name] = alpha
            loup_pred[name] = alpha * canary_diff[name]
        fam_train_m = [x for x in names if x.startswith("M")]
        alpha_m = fit_alpha([full[x] for x in fam_train_m], [canary_diff[x] for x in fam_train_m])
        fam_pred_q = alpha_m * canary_diff["Qwen2.5->Qwen3"]
        fam_train_q = ["Qwen2.5->Qwen3"]
        alpha_q = fit_alpha([full[x] for x in fam_train_q], [canary_diff[x] for x in fam_train_q])
        fam_pred_m = {x: alpha_q * canary_diff[x] for x in fam_train_m}

        mae_raw = sum(abs(canary_diff[x] - full[x]) for x in names) / len(names)
        mae_loup = sum(abs(loup_pred[x] - full[x]) for x in names) / len(names)
        mae_fam = (sum(abs(fam_pred_m[x] - full[x]) for x in fam_train_m) + abs(fam_pred_q - full["Qwen2.5->Qwen3"])) / len(names)
        print(f"  calibration: LOUO alphas={ {x.split()[1]: round(loup_alphas[x], 2) for x in names} } "
              f"alpha(Mistral->Qwen)={alpha_m:.2f} alpha(Qwen->Mistral)={alpha_q:.2f}")
        print(f"  magnitude MAE: raw={mae_raw:.3f} LOUO-cal={mae_loup:.3f} family-cal={mae_fam:.3f}")
        for t in (0.03, 0.05, 0.08):
            acc_raw = sum(gate_label(canary_diff[x], t) == gate_label(full[x], t) for x in names) / len(names)
            acc_cal = sum(gate_label(loup_pred[x], t) == gate_label(full[x], t) for x in names) / len(names)
            print(f"  decision accuracy at t={t:.2f}: raw={acc_raw:.2f} calibrated={acc_cal:.2f}")


if __name__ == "__main__":
    main(sys.argv)
