"""Generate paper assets from the corrected (post-fix) BFCL runs and the
synthetic-suite runs: CSV tables under tables/ and figures under figures/.

Run with the system Python (matplotlib is not installed in the project venv):
    python scripts/generate_paper_assets.py

Read-only with respect to run folders; overwrites tables/ and figures/ only.
"""

from __future__ import annotations

import csv
import json
import os
import random
from collections import defaultdict

BOOT_REPS = 10000
BOOT_SEED = 1234
GATE_T = 0.05
STRESS = ("schema_drift", "runtime_fault")
CONDITIONS = ["baseline", "schema_drift", "runtime_fault"]
KS = [10, 20, 30, 40]

MODELS = ["m1", "m2", "m3", "q25", "q3"]
MODEL_NAME = {"m1": "Mistral v0.1", "m2": "Mistral v0.2", "m3": "Mistral v0.3",
              "q25": "Qwen2.5", "q3": "Qwen3"}
DECISIONS = [("v0.1->v0.2", "m1", "m2"), ("v0.2->v0.3", "m2", "m3"),
             ("v0.1->v0.3", "m1", "m3"), ("Qwen2.5->Qwen3", "q25", "q3")]

RUNS = {
    "BFCL": {
        "m1": r"results\upgradecanary-bfcl-trials-itlwas-v0.1_seed1234_20261001T142620Z",
        "m2": r"results\upgradecanary-bfcl-trials-itlwas-v0.2_seed1234_20261001T151819Z",
        "m3": r"results\upgradecanary-bfcl-trials-itlwas-v0.3_seed1234_20261001T160749Z",
        "q25": r"results\upgradecanary-bfcl-trials-qwen25_seed1234_20261001T162536Z",
        "q3": r"results\upgradecanary-bfcl-trials-qwen3_seed1234_20261001T190657Z",
    },
    "synthetic": {
        "m1": r"results\upgradecanary-real-trials-itlwas-v0.1_seed1234_20260929T120210Z",
        "m2": r"results\upgradecanary-real-trials-itlwas-v0.2_seed1234_20260929T121701Z",
        "m3": r"results\upgradecanary-real-trials-itlwas-v0.3_seed1234_20260929T192811Z",
        "q25": r"results\upgradecanary-real-trials-qwen25_seed1234_20260929T222007Z",
        "q3": r"results\upgradecanary-real-trials-qwen3_seed1234_20260929T230135Z",
    },
}


def load_run(d: str) -> dict:
    recs = {}
    with open(os.path.join(d, "parsed_results.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            key = (r["task_id"], r["condition"], (r["drift"] or {}).get("type"),
                   (r["fault"] or {}).get("type"), r.get("trial_index", 0))
            recs[key] = r
    return recs


def sc(r: dict) -> float:
    m = r["metrics"]
    return 1.0 if (m["parse_ok"] and m["tool_name_ok"] and m["args_intent_match"]
                   and m["args_valid_under_drift"] and m["executor_ok"]) else 0.0


def diff(ra, rb, keys) -> float:
    return sum(sc(rb[k]) - sc(ra[k]) for k in keys) / len(keys)


def label(d: float) -> str:
    if d < -GATE_T:
        return "harmful"
    if d > GATE_T:
        return "beneficial"
    return "neutral"


def cluster_ci(ra, rb, keys, rng):
    tasks = sorted({k[0] for k in keys})
    by_task = {t: [k for k in keys if k[0] == t] for t in tasks}
    ds = []
    for _ in range(BOOT_REPS):
        ks = [k for t in (tasks[rng.randrange(len(tasks))] for _ in tasks) for k in by_task[t]]
        ds.append(diff(ra, rb, ks))
    ds.sort()
    return ds[250], ds[9749]


def select_canary(ranked, categories, k):
    sel, covered = [], set()
    for t in ranked:
        if len(sel) >= k:
            break
        if categories[t] - covered:
            sel.append(t)
            covered |= categories[t]
    for t in ranked:
        if len(sel) >= k:
            break
        if t not in sel:
            sel.append(t)
    return sel


def suite_data(runs):
    common = sorted(set.intersection(*(set(r) for r in runs.values())))
    tasks = sorted({k[0] for k in common})
    by_task = {t: [k for k in common if k[0] == t] for t in tasks}
    stress = [k for k in common if k[1] in STRESS]
    by_task_stress = {t: [k for k in stress if k[0] == t] for t in tasks}
    categories = {t: {k[2] for k in ks if k[1] == "schema_drift"}
                  | {k[3] for k in ks if k[1] == "runtime_fault"}
                  for t, ks in by_task.items()}
    return common, tasks, by_task, stress, by_task_stress, categories


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {path}")


def main() -> None:
    rng = random.Random(BOOT_SEED)
    os.makedirs("tables", exist_ok=True)
    os.makedirs("figures", exist_ok=True)

    data = {suite: suite_data({m: load_run(d) for m, d in dirs.items()}) for suite, dirs in RUNS.items()}
    runs = {suite: {m: load_run(d) for m, d in dirs.items()} for suite, dirs in RUNS.items()}

    # ---- Table 1: model scores by suite and condition ----
    rows = []
    for suite in ("synthetic", "BFCL"):
        common, tasks, by_task, stress, _, _ = data[suite]
        for m in MODELS:
            r = runs[suite][m]
            vals = [sum(sc(r[k]) for k in common if k[1] == c) / sum(1 for k in common if k[1] == c)
                    for c in CONDITIONS]
            st = sum(sc(r[k]) for k in stress) / len(stress)
            rows.append([suite, MODEL_NAME[m], *(f"{v:.3f}" for v in vals), f"{st:.3f}"])
    write_csv("tables/model_scores_by_suite.csv",
              ["suite", "model", "baseline", "schema_drift", "runtime_fault", "stress"], rows)

    # ---- Table 2+3+4: upgrade decisions, flips, bootstrap CIs ----
    rows = []
    for suite in ("synthetic", "BFCL"):
        common, tasks, by_task, stress, by_task_stress, _ = data[suite]
        for name, a, b in DECISIONS:
            ra, rb = runs[suite][a], runs[suite][b]
            d_base = diff(ra, rb, [k for k in common if k[1] == "baseline"])
            d_drift = diff(ra, rb, [k for k in common if k[1] == "schema_drift"])
            d_fault = diff(ra, rb, [k for k in common if k[1] == "runtime_fault"])
            d_stress = diff(ra, rb, stress)
            neg = sum(1 for k in stress if sc(ra[k]) == 1 and sc(rb[k]) == 0)
            pos = sum(1 for k in stress if sc(ra[k]) == 0 and sc(rb[k]) == 1)
            lo, hi = cluster_ci(ra, rb, stress, rng)
            rows.append([suite, name, f"{d_base:+.3f}", f"{d_drift:+.3f}", f"{d_fault:+.3f}",
                         f"{d_stress:+.3f}", label(d_stress), neg, pos, f"{lo:+.3f}", f"{hi:+.3f}"])
    write_csv("tables/upgrade_decisions.csv",
              ["suite", "decision", "d_baseline", "d_schema_drift", "d_runtime_fault",
               "d_stress", "gate_label", "neg_flips", "pos_flips", "ci95_lo", "ci95_hi"], rows)

    # ---- Table 5: consistency ----
    rows = []
    for suite in ("synthetic", "BFCL"):
        common, tasks, by_task, stress, _, _ = data[suite]
        for m in MODELS:
            units = sorted({(k[0], k[1]) for k in common})
            all_s = all_f = 0
            ranges = []
            for u in units:
                s = [sc(runs[suite][m][k]) for k in common if k[0] == u[0] and k[1] == u[1]]
                ranges.append(max(s) - min(s))
                if sum(s) == len(s):
                    all_s += 1
                if sum(s) == 0:
                    all_f += 1
            rows.append([suite, MODEL_NAME[m], all_s, all_f, f"{sum(ranges)/len(ranges):.3f}"])
    write_csv("tables/consistency.csv",
              ["suite", "model", "all_trial_success_300", "all_trial_fail_300", "mean_score_range"], rows)

    # ---- Table 6: gate accuracy (H4) ----
    rows = []
    for suite in ("synthetic", "BFCL"):
        common, tasks, by_task, stress, by_task_stress, categories = data[suite]
        r_ = runs[suite]
        truths = {n: label(diff(r_[a], r_[b], stress)) for n, a, b in DECISIONS}
        cond_info = {}
        for cond in CONDITIONS:
            info = {t: 0.0 for t in tasks}
            for n, a, b in DECISIONS:
                for t in tasks:
                    info[t] += abs(diff(r_[a], r_[b], [k for k in by_task[t] if k[1] == cond]))
            cond_info[cond] = info
        for k in KS:
            accs = defaultdict(list)
            for n, a, b in DECISIONS:
                others = [d for d in DECISIONS if d[0] != n]
                info_sel = {t: sum(abs(diff(r_[x], r_[y], by_task_stress[t])) for _, x, y in others) / len(others)
                            for t in tasks}
                for mode, info in (("selected", info_sel),
                                   ("clean_only", cond_info["baseline"]),
                                   ("drift_only", cond_info["schema_drift"]),
                                   ("fault_only", cond_info["runtime_fault"])):
                    ranked = sorted(tasks, key=lambda t: info[t], reverse=True)
                    canary = select_canary(ranked, categories, k)
                    d = diff(r_[a], r_[b], [key for t in canary for key in by_task_stress[t]])
                    accs[mode].append(label(d) == truths[n])
                ok = 0
                rrng = random.Random(f"fig4-{suite}-{n}-{k}")
                for _ in range(100):
                    sub = rrng.sample(tasks, k)
                    d = diff(r_[a], r_[b], [key for t in sub for key in by_task_stress[t]])
                    ok += label(d) == truths[n]
                accs["random"].append(ok / 100)
            rows.append([suite, k] + [f"{sum(accs[m])/len(accs[m]):.3f}" for m in
                                      ("selected", "random", "clean_only", "drift_only", "fault_only")])
    write_csv("tables/gate_accuracy.csv",
              ["suite", "k", "selected", "random", "clean_only", "drift_only", "fault_only"], rows)

    # ---- Figures ----
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available - figures skipped (tables written)")
        return

    short = {"Mistral v0.1": "M-v0.1", "Mistral v0.2": "M-v0.2", "Mistral v0.3": "M-v0.3",
             "Qwen2.5": "Q2.5", "Qwen3": "Q3"}

    # Figure 1: stress by model, grouped by suite
    stress_vals = defaultdict(dict)
    with open("tables/model_scores_by_suite.csv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            stress_vals[row["suite"]][row["model"]] = float(row["stress"])
    x = range(len(MODELS))
    width = 0.38
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([i - width / 2 for i in x], [stress_vals["synthetic"][MODEL_NAME[m]] for m in MODELS],
           width, label="Synthetic suite")
    ax.bar([i + width / 2 for i in x], [stress_vals["BFCL"][MODEL_NAME[m]] for m in MODELS],
           width, label="BFCL suite (corrected)")
    ax.set_xticks(list(x))
    ax.set_xticklabels([short[MODEL_NAME[m]] for m in MODELS])
    ax.set_ylabel("Stress score (mean of schema_drift, runtime_fault)")
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.set_title("Functional success under stress, by model and suite")
    fig.tight_layout()
    fig.savefig("figures/fig1_stress_by_suite.png", dpi=150)
    plt.close(fig)
    print("wrote figures/fig1_stress_by_suite.png")

    # Figure 2: decision effect sizes with CIs, panel per suite
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, suite in zip(axes, ("synthetic", "BFCL")):
        sub = [r for r in csv.DictReader(open("tables/upgrade_decisions.csv", encoding="utf-8"))
               if r["suite"] == suite]
        ys = list(range(len(sub)))[::-1]
        ax.errorbar([float(r["d_stress"]) for r in sub], ys,
                    xerr=[[float(r["d_stress"]) - float(r["ci95_lo"]) for r in sub],
                          [float(r["ci95_hi"]) - float(r["d_stress"]) for r in sub]],
                    fmt="o", capsize=4, color="tab:blue")
        ax.axvline(0, color="gray", lw=0.8)
        ax.axvline(-GATE_T, color="red", lw=0.8, ls="--")
        ax.axvline(GATE_T, color="green", lw=0.8, ls="--")
        ax.set_title(f"{suite} suite")
        ax.set_xlabel("Paired stress difference (B - A)")
        ax.set_yticks(ys)
        ax.set_yticklabels([r["decision"] for r in sub])
    axes[0].set_ylabel("Upgrade decision")
    fig.suptitle("Upgrade-decision effect sizes with task-cluster bootstrap 95% CIs")
    fig.tight_layout()
    fig.savefig("figures/fig2_decision_effects.png", dpi=150)
    plt.close(fig)
    print("wrote figures/fig2_decision_effects.png")

    # Figure 3: consistency (all-trial success bars + mean range line)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, suite in zip(axes, ("synthetic", "BFCL")):
        sub = [r for r in csv.DictReader(open("tables/consistency.csv", encoding="utf-8"))
               if r["suite"] == suite]
        xs = range(len(sub))
        ax.bar(xs, [int(r["all_trial_success_300"]) for r in sub], color="tab:blue", label="all-trials success (/300)")
        ax.set_xticks(list(xs))
        ax.set_xticklabels([short[r["model"]] for r in sub], rotation=20)
        ax.set_ylim(0, 320)
        ax2 = ax.twinx()
        ax2.plot(xs, [float(r["mean_score_range"]) for r in sub], "o-", color="tab:red", label="mean per-task range")
        ax2.set_ylabel("Mean per-task score range", color="tab:red")
        ax2.set_ylim(0, 0.45)
        ax.set_title(f"{suite} suite")
        ax.set_ylabel("Units succeeding on all 3 trials")
    fig.suptitle("Repeated-trial consistency")
    fig.tight_layout()
    fig.savefig("figures/fig3_consistency.png", dpi=150)
    plt.close(fig)
    print("wrote figures/fig3_consistency.png")

    # Figure 4: gate accuracy (selected vs baselines) by suite
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    styles = {"selected": ("o-", "tab:blue"), "random": ("s--", "gray"),
              "clean_only": ("^-", "tab:green"), "drift_only": ("v-", "tab:orange"),
              "fault_only": ("d-", "tab:purple")}
    for ax, suite in zip(axes, ("synthetic", "BFCL")):
        sub = [r for r in csv.DictReader(open("tables/gate_accuracy.csv", encoding="utf-8"))
               if r["suite"] == suite]
        xs = [int(r["k"]) for r in sub]
        for mode, (fmt, color) in styles.items():
            ax.plot(xs, [float(r[mode]) for r in sub], fmt, color=color, label=mode)
        ax.set_title(f"{suite} suite")
        ax.set_xlabel("Canary size k (tasks)")
        ax.set_xticks(xs)
        ax.axhline(0.95, color="red", ls=":", lw=0.8)
    axes[0].set_ylabel("Gate decision accuracy (4 decisions)")
    axes[0].legend(fontsize=8)
    fig.suptitle("Release-gate accuracy: selected mixed canary vs baselines")
    fig.tight_layout()
    fig.savefig("figures/fig4_gate_accuracy.png", dpi=150)
    plt.close(fig)
    print("wrote figures/fig4_gate_accuracy.png")


if __name__ == "__main__":
    main()
