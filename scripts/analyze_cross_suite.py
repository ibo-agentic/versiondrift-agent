"""Cross-suite analysis: BFCL public suite paired analysis, synthetic-vs-BFCL
comparison, and release-gate hypothesis validation (H1-H5 + cross-suite
transfer). Read-only; uses existing run folders only.

Usage:
    python scripts/analyze_cross_suite.py

Run folders are configured in BFCL_RUNS / SYN_RUNS below (defaults match the
2026-09-29/2026-10-01 experiments). Prints concise tables per part.
"""

from __future__ import annotations

import json
import os
import random
from collections import defaultdict

BOOT_REPS = 10000
BOOT_SEED = 1234
GATE_T = 0.05
KS = [10, 20, 30, 40]
STRESS = ("schema_drift", "runtime_fault")
CONDITIONS = ["baseline", "schema_drift", "runtime_fault"]
DRIFT_TYPES = ["field_rename", "field_drop", "type_mutation", "unexpected_field", "enum_drift"]
FAULT_TYPES = ["timeout", "tool_exception", "empty_result", "stale_result", "partial_result"]

MODELS = ["m1", "m2", "m3", "q25", "q3"]
MODEL_NAME = {"m1": "Mistral v0.1", "m2": "Mistral v0.2", "m3": "Mistral v0.3",
              "q25": "Qwen2.5", "q3": "Qwen3"}
DECISIONS = [("v0.1->v0.2", "m1", "m2"), ("v0.2->v0.3", "m2", "m3"),
             ("v0.1->v0.3", "m1", "m3"), ("Qwen2.5->Qwen3", "q25", "q3")]

BFCL_RUNS = {
    "m1": r"results\upgradecanary-bfcl-trials-itlwas-v0.1_seed1234_20261001T042558Z",
    "m2": r"results\upgradecanary-bfcl-trials-itlwas-v0.2_seed1234_20261001T045510Z",
    "m3": r"results\upgradecanary-bfcl-trials-itlwas-v0.3_seed1234_20261001T051347Z",
    "q25": r"results\upgradecanary-bfcl-trials-qwen25_seed1234_20261001T053040Z",
    "q3": r"results\upgradecanary-bfcl-trials-qwen3_seed1234_20261001T054551Z",
}
SYN_RUNS = {
    "m1": r"results\upgradecanary-real-trials-itlwas-v0.1_seed1234_20260929T120210Z",
    "m2": r"results\upgradecanary-real-trials-itlwas-v0.2_seed1234_20260929T121701Z",
    "m3": r"results\upgradecanary-real-trials-itlwas-v0.3_seed1234_20260929T192811Z",
    "q25": r"results\upgradecanary-real-trials-qwen25_seed1234_20260929T222007Z",
    "q3": r"results\upgradecanary-real-trials-qwen3_seed1234_20260929T230135Z",
}


def load_run(d: str) -> dict:
    for name in ("parsed_results_corrected.jsonl", "parsed_results.jsonl"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            recs = {}
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    r = json.loads(line)
                    key = (r["task_id"], r["condition"], (r["drift"] or {}).get("type"),
                           (r["fault"] or {}).get("type"), r.get("trial_index", 0))
                    recs[key] = r
            return recs
    raise FileNotFoundError(d)


def functional(m: dict) -> float:
    return 1.0 if (m["parse_ok"] and m["tool_name_ok"] and m["args_intent_match"]
                   and m["args_valid_under_drift"] and m["executor_ok"]) else 0.0


def sc(r: dict) -> float:
    return functional(r["metrics"])


def diff(ra: dict, rb: dict, keys: list) -> float:
    return sum(sc(rb[k]) - sc(ra[k]) for k in keys) / len(keys)


def label(d: float, t: float = GATE_T) -> str:
    if d < -t:
        return "harmful"
    if d > t:
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


def fit_alpha(fs, cs):
    den = sum(c * c for c in cs)
    return sum(f * c for f, c in zip(fs, cs)) / den if den else 0.0


def suite_context(runs):
    common = sorted(set.intersection(*(set(r) for r in runs.values())))
    tasks = sorted({k[0] for k in common})
    by_task = {t: [k for k in common if k[0] == t] for t in tasks}
    stress = [k for k in common if k[1] in STRESS]
    by_task_stress = {t: [k for k in stress if k[0] == t] for t in tasks}
    categories = {t: {k[2] for k in ks if k[1] == "schema_drift"}
                  | {k[3] for k in ks if k[1] == "runtime_fault"}
                  for t, ks in by_task.items()}
    return common, tasks, by_task, stress, by_task_stress, categories


def main() -> None:
    rng = random.Random(BOOT_SEED)
    print("loading runs...")
    bfcl = {m: load_run(d) for m, d in BFCL_RUNS.items()}
    syn = {m: load_run(d) for m, d in SYN_RUNS.items()}
    (b_common, b_tasks, b_by_task, b_stress, b_by_task_stress, b_cat) = suite_context(bfcl)
    (s_common, s_tasks, s_by_task, s_stress, s_by_task_stress, s_cat) = suite_context(syn)
    print(f"BFCL matched: {len(b_common)} | synthetic matched: {len(s_common)}")

    # ---------- PART 1: BFCL paired analysis ----------
    print("\n===== PART 1: BFCL paired analysis =====")
    print("\nper-condition functional scores (pooled over trials):")
    for c in CONDITIONS:
        cells = [f"{MODEL_NAME[m]}={sum(sc(bfcl[m][k]) for k in b_common if k[1]==c)/sum(1 for k in b_common if k[1]==c):.2f}" for m in MODELS]
        print(f"  {c}: " + "  ".join(cells))
    print("stress (mean of drift,fault): " + "  ".join(
        f"{MODEL_NAME[m]}={sum(sc(bfcl[m][k]) for k in b_stress)/len(b_stress):.2f}" for m in MODELS))

    print("\nupgrade decisions (diff = B - A; CI on stress, task-cluster bootstrap):")
    dec = {}
    for name, a, b in DECISIONS:
        ra, rb = bfcl[a], bfcl[b]
        d_base = diff(ra, rb, [k for k in b_common if k[1] == "baseline"])
        d_drift = diff(ra, rb, [k for k in b_common if k[1] == "schema_drift"])
        d_fault = diff(ra, rb, [k for k in b_common if k[1] == "runtime_fault"])
        d_stress = diff(ra, rb, b_stress)
        neg = sum(1 for k in b_stress if sc(ra[k]) == 1 and sc(rb[k]) == 0)
        pos = sum(1 for k in b_stress if sc(ra[k]) == 0 and sc(rb[k]) == 1)
        lo, hi = cluster_ci(ra, rb, b_stress, rng)
        dec[name] = d_stress
        print(f"  {name}: base {d_base:+.3f} drift {d_drift:+.3f} fault {d_fault:+.3f} "
              f"STRESS {d_stress:+.3f} ({label(d_stress)}) neg={neg} pos={pos} CI=[{lo:+.3f},{hi:+.3f}]")

    print("\nschema_drift by drift type (A->B pooled scores, neg/pos):")
    for name, a, b in DECISIONS:
        rows = []
        for dt in DRIFT_TYPES:
            keys = [k for k in b_common if k[1] == "schema_drift" and k[2] == dt]
            if not keys:
                continue
            neg = sum(1 for k in keys if sc(bfcl[a][k]) == 1 and sc(bfcl[b][k]) == 0)
            pos = sum(1 for k in keys if sc(bfcl[a][k]) == 0 and sc(bfcl[b][k]) == 1)
            rows.append(f"{dt} {diff(bfcl[a],bfcl[b],keys):+.2f}({neg}/{pos})")
        print(f"  {name}: " + "  ".join(rows))
    print("runtime_fault by fault type (A->B, neg/pos):")
    for name, a, b in DECISIONS:
        rows = []
        for ft in FAULT_TYPES:
            keys = [k for k in b_common if k[1] == "runtime_fault" and k[3] == ft]
            if not keys:
                continue
            neg = sum(1 for k in keys if sc(bfcl[a][k]) == 1 and sc(bfcl[b][k]) == 0)
            pos = sum(1 for k in keys if sc(bfcl[a][k]) == 0 and sc(bfcl[b][k]) == 1)
            rows.append(f"{ft} {diff(bfcl[a],bfcl[b],keys):+.2f}({neg}/{pos})")
        print(f"  {name}: " + "  ".join(rows))

    print("\nconsistency (per task x condition unit, 3 trials):")
    b_cons = {}
    for m in MODELS:
        units = sorted({(k[0], k[1]) for k in b_common})
        all_s = all_f = 0
        ranges = []
        for u in units:
            s = [sc(bfcl[m][k]) for k in b_common if k[0] == u[0] and k[1] == u[1]]
            ranges.append(max(s) - min(s))
            if sum(s) == len(s):
                all_s += 1
            if sum(s) == 0:
                all_f += 1
        b_cons[m] = sum(ranges) / len(ranges)
        print(f"  {MODEL_NAME[m]}: all-success {all_s}/300 all-fail {all_f}/300 mean range {b_cons[m]:.3f}")

    # ---------- PART 2: synthetic vs BFCL ----------
    print("\n===== PART 2: synthetic vs BFCL cross-suite =====")
    print(f"{'model':<14}{'suite':<10}{'baseline':>9}{'drift':>8}{'fault':>8}{'stress':>8}{'mean range':>11}")
    s_cons = {}
    table = {}
    for m in MODELS:
        for suite_name, runs, common, stress, cat in (("synthetic", syn, s_common, s_stress, None), ("BFCL", bfcl, b_common, b_stress, None)):
            base = sum(sc(runs[m][k]) for k in common if k[1] == "baseline") / sum(1 for k in common if k[1] == "baseline")
            dr = sum(sc(runs[m][k]) for k in common if k[1] == "schema_drift") / sum(1 for k in common if k[1] == "schema_drift")
            fa = sum(sc(runs[m][k]) for k in common if k[1] == "runtime_fault") / sum(1 for k in common if k[1] == "runtime_fault")
            st = sum(sc(runs[m][k]) for k in stress) / len(stress)
            units = sorted({(k[0], k[1]) for k in common})
            ranges = [max(sc(runs[m][k]) for k in common if k[0] == u[0] and k[1] == u[1])
                      - min(sc(runs[m][k]) for k in common if k[0] == u[0] and k[1] == u[1]) for u in units]
            mr = sum(ranges) / len(ranges)
            if suite_name == "synthetic":
                s_cons[m] = mr
            table[(m, suite_name)] = (base, dr, fa, st, mr)
            print(f"{MODEL_NAME[m]:<14}{suite_name:<10}{base:>9.2f}{dr:>8.2f}{fa:>8.2f}{st:>8.2f}{mr:>11.3f}")
    print("\nranking correlation (Spearman-ish check): synthetic stress order vs BFCL stress order")
    syn_rank = sorted(MODELS, key=lambda m: -table[(m, 'synthetic')][3])
    bfcl_rank = sorted(MODELS, key=lambda m: -table[(m, 'BFCL')][3])
    print(f"  synthetic: {[MODEL_NAME[m] for m in syn_rank]}")
    print(f"  BFCL:      {[MODEL_NAME[m] for m in bfcl_rank]}")
    agree = sum(1 for a, b in zip(syn_rank, bfcl_rank) if a == b)
    print(f"  exact position agreement: {agree}/5")

    # ---------- PART 3: gate validation on BFCL ----------
    print("\n===== PART 3: release-gate validation on BFCL =====")
    truths = {n: label(d) for n, d in dec.items()}
    print("H1 non-monotonic:", f"v0.1->v0.2 {dec['v0.1->v0.2']:+.3f} ({truths['v0.1->v0.2']})",
          f"vs v0.2->v0.3 {dec['v0.2->v0.3']:+.3f} ({truths['v0.2->v0.3']})")
    print("H2 neutral-with-swap check:")
    for name, a, b in DECISIONS:
        if truths[name] == "neutral":
            cats = []
            for dt in DRIFT_TYPES:
                keys = [k for k in b_common if k[1] == "schema_drift" and k[2] == dt]
                if keys:
                    d = diff(bfcl[a], bfcl[b], keys)
                    if abs(d) >= 0.2:
                        cats.append(f"{dt} {d:+.2f}")
            for ft in FAULT_TYPES:
                keys = [k for k in b_common if k[1] == "runtime_fault" and k[3] == ft]
                if keys:
                    d = diff(bfcl[a], bfcl[b], keys)
                    if abs(d) >= 0.2:
                        cats.append(f"{ft} {d:+.2f}")
            print(f"  {name}: neutral with strong categories: {cats if cats else 'none'}")

    # per-decision task informativeness (LOO) and canary evaluation
    def canary_eval(runs, tasks, by_task_stress, cat, info_source, k):
        # info_source: dict task -> informativeness (higher = more informative)
        ranked = sorted(tasks, key=lambda t: info_source[t], reverse=True)
        out = {}
        for name, a, b in DECISIONS:
            canary = select_canary(ranked, cat, k)
            out[name] = diff(runs[a], runs[b], [key for t in canary for key in by_task_stress[t]])
        return out

    def loo_info(runs, tasks, by_task_stress, exclude=None):
        info = {t: 0.0 for t in tasks}
        n = 0
        for name, a, b in DECISIONS:
            if name == exclude:
                continue
            for t in tasks:
                info[t] += abs(diff(runs[a], runs[b], by_task_stress[t]))
            n += 1
        return {t: v / n for t, v in info.items()} if n else info

    print("\nH3 canary transfer across families (BFCL only), accuracy over 4 decisions:")
    for k in KS:
        accs = []
        for name, a, b in DECISIONS:
            # mean |task diff| over the OTHER decisions (leave-one-out selection)
            info = {t: sum(abs(diff(bfcl[x], bfcl[y], b_by_task_stress[t])) for nn, x, y in DECISIONS if nn != name) / 3
                    for t in b_tasks}
            ranked = sorted(b_tasks, key=lambda t: info[t], reverse=True)
            canary = select_canary(ranked, b_cat, k)
            d = diff(bfcl[a], bfcl[b], [key for t in canary for key in b_by_task_stress[t]])
            accs.append(label(d) == truths[name])
        print(f"  k={k}: mean decision accuracy {sum(accs)/len(accs):.2f} ({sum(accs)}/{len(accs)})")

    print("\nH4 selected vs baselines (decision accuracy over 4 BFCL decisions):")
    def per_condition_info(cond):
        info = {t: 0.0 for t in b_tasks}
        for name, a, b in DECISIONS:
            for t in b_tasks:
                keys = [k for k in b_by_task[t] if k[1] == cond]
                info[t] += abs(diff(bfcl[a], bfcl[b], keys))
        return {t: v / len(DECISIONS) for t, v in info.items()}

    infos = {
        "selected(mixed)": None,  # filled per decision (LOO)
        "clean-only": per_condition_info("baseline"),
        "drift-only": per_condition_info("schema_drift"),
        "fault-only": per_condition_info("runtime_fault"),
    }
    for k in KS:
        cells = []
        for mode in ["selected(mixed)", "clean-only", "drift-only", "fault-only"]:
            accs = []
            for name, a, b in DECISIONS:
                if mode == "selected(mixed)":
                    info = {t: sum(abs(diff(bfcl[x], bfcl[y], b_by_task_stress[t])) for nn, x, y in DECISIONS if nn != name) / 3
                            for t in b_tasks}
                else:
                    info = infos[mode]
                ranked = sorted(b_tasks, key=lambda t: info[t], reverse=True)
                canary = select_canary(ranked, b_cat, k)
                d = diff(bfcl[a], bfcl[b], [key for t in canary for key in b_by_task_stress[t]])
                accs.append(label(d) == truths[name])
            cells.append(f"{mode}={sum(accs)/len(accs):.2f}")
        # random baseline
        rand_accs = []
        for name, a, b in DECISIONS:
            ok = 0
            rrng = random.Random(f"h4-{name}-{k}")
            for _ in range(200):
                sub = rrng.sample(b_tasks, k)
                d = diff(bfcl[a], bfcl[b], [key for t in sub for key in b_by_task_stress[t]])
                ok += label(d) == truths[name]
            rand_accs.append(ok / 200)
        cells.append(f"random={sum(rand_accs)/len(rand_accs):.2f}")
        print(f"  k={k}: " + "  ".join(cells))

    print("\nH5 calibration (full ~ alpha * canary, LOUO over 4 BFCL decisions):")
    for k in (20, 30, 40):
        cd = {}
        for name, a, b in DECISIONS:
            info = {t: sum(abs(diff(bfcl[x], bfcl[y], b_by_task_stress[t])) for nn, x, y in DECISIONS if nn != name) / 3
                    for t in b_tasks}
            ranked = sorted(b_tasks, key=lambda t: info[t], reverse=True)
            canary = select_canary(ranked, b_cat, k)
            cd[name] = diff(bfcl[a], bfcl[b], [key for t in canary for key in b_by_task_stress[t]])
        alphas = {}
        preds = {}
        for name, _, _ in DECISIONS:
            train = [n for n, _, _ in DECISIONS if n != name]
            alphas[name] = fit_alpha([dec[n] for n in train], [cd[n] for n in train])
            preds[name] = alphas[name] * cd[name]
        mae_raw = sum(abs(cd[n] - dec[n]) for n, _, _ in DECISIONS) / 4
        mae_cal = sum(abs(preds[n] - dec[n]) for n, _, _ in DECISIONS) / 4
        accs = []
        for t in (0.03, 0.05, 0.08):
            a_raw = sum(label(cd[n], t) == label(dec[n], t) for n, _, _ in DECISIONS) / 4
            a_cal = sum(label(preds[n], t) == label(dec[n], t) for n, _, _ in DECISIONS) / 4
            accs.append(f"t={t}: raw {a_raw:.2f} cal {a_cal:.2f}")
        print(f"  k={k}: alpha~{sum(alphas.values())/4:.2f} MAE raw={mae_raw:.3f} cal={mae_cal:.3f} | " + " | ".join(accs))

    # ---------- cross-suite gate transfer (category-level) ----------
    print("\n===== cross-suite transfer (category-level; task sets are disjoint) =====")
    def cat_info(runs, tasks, by_task_stress):
        scores = defaultdict(list)
        for name, a, b in DECISIONS:
            for t in tasks:
                d = diff(runs[a], runs[b], by_task_stress[t])
                for c in ({k[2] for k in by_task_stress[t]} | {k[3] for k in by_task_stress[t]}):
                    scores[c].append(abs(d))
        return {c: sum(v) / len(v) for c, v in scores.items()}

    def eval_with_catinfo(eval_runs, eval_tasks, eval_by_task_stress, eval_cat, catinfo, k, truths_map):
        info = {t: sum(catinfo.get(c, 0.0) for c in eval_cat[t]) for t in eval_tasks}
        ranked = sorted(eval_tasks, key=lambda t: info[t], reverse=True)
        accs = []
        for name, a, b in DECISIONS:
            canary = select_canary(ranked, eval_cat, k)
            d = diff(eval_runs[a], eval_runs[b], [key for t in canary for key in eval_by_task_stress[t]])
            accs.append(label(d) == truths_map[name])
        return sum(accs) / len(accs)

    syn_truths = {}
    for name, a, b in DECISIONS:
        syn_truths[name] = label(diff(syn[a], syn[b], s_stress))
    bfcl_truths = truths

    syn_catinfo = cat_info(syn, s_tasks, s_by_task_stress)
    bfcl_catinfo = cat_info(bfcl, b_tasks, b_by_task_stress)
    for k in (10, 20, 30):
        a1 = eval_with_catinfo(bfcl, b_tasks, b_by_task_stress, b_cat, syn_catinfo, k, bfcl_truths)
        a2 = eval_with_catinfo(syn, s_tasks, s_by_task_stress, s_cat, bfcl_catinfo, k, syn_truths)
        print(f"  k={k}: synthetic-categories -> BFCL Qwen/Mistral decisions acc={a1:.2f} | "
              f"BFCL-categories -> synthetic decisions acc={a2:.2f}")


if __name__ == "__main__":
    main()
