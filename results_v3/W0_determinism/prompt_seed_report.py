"""Read-only analysis for results_v3/W0_determinism/PROMPT_SEED_REPORT.md (questions 2-5)."""
import collections, glob, json, sys
from pathlib import Path
sys.path.insert(0, ".")
from vdanalysis.loader import record_score


def rd(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def run_dir(proto, m, s):
    g = glob.glob(f"results_v2/{proto}/{m}/{s}/upgradecanary-*")
    assert len(g) == 1, (proto, m, s, g)
    return g[0]


MODELS = ["mistral_v01", "mistral_v02", "mistral_v03", "qwen2", "qwen25", "qwen3", "llama3", "llama31", "phi3_mini",
          "phi35_mini", "phi4_mini", "granite30", "granite31", "granite32", "gemma2_2b", "gemma3_4b"]
SUITES = ["synthetic", "bfcl_simple", "bfcl_multiple"]
out = {}

# ---- Q2: do trials 0/1/2 see the same stress prompt? (all 48 D runs)
groups = diff_groups = 0
per_cond = collections.Counter()
per_cond_diff = collections.Counter()
for m in MODELS:
    for s in SUITES:
        g = collections.defaultdict(set)
        for r in rd(run_dir("D", m, s) + "/raw_outputs.jsonl"):
            g[(r["task_id"], r["condition"])].add(r["prompt_sha256"])
        for (t, c), v in g.items():
            groups += 1
            per_cond[c] += 1
            if len(v) > 1:
                diff_groups += 1
                per_cond_diff[c] += 1
out["q2"] = {"task_condition_groups": groups, "groups_with_more_than_one_distinct_prompt_across_trials": diff_groups,
             "per_condition_[groups,groups_with_differing_prompts]": {c: [per_cond[c], per_cond_diff[c]] for c in per_cond}}

# ---- Q3: old vs new model, same protocol D: byte-identical prompts per record?
pairs = [("mistral_v01", "mistral_v02"), ("mistral_v02", "mistral_v03"), ("qwen2", "qwen25"), ("qwen25", "qwen3"),
         ("llama3", "llama31"), ("phi3_mini", "phi35_mini"), ("phi35_mini", "phi4_mini"), ("granite30", "granite31"),
         ("granite31", "granite32"), ("gemma2_2b", "gemma3_4b")]
q3 = []
for a, b in pairs:
    for s in SUITES:
        ra = {(r["task_id"], r["condition"], r["trial_index"]): r for r in rd(run_dir("D", a, s) + "/raw_outputs.jsonl")}
        rb = {(r["task_id"], r["condition"], r["trial_index"]): r for r in rd(run_dir("D", b, s) + "/raw_outputs.jsonl")}
        keys = set(ra) & set(rb)
        same = sum(ra[k]["prompt"] == rb[k]["prompt"] for k in keys)
        q3.append({"pair": f"{a}->{b}", "suite": s, "n_a": len(ra), "n_b": len(rb), "matched": len(keys),
                   "prompt_byte_identical": same})
out["q3"] = q3

# ---- Q4: llama31 / bfcl_multiple, R (arm 1) vs R_AA (arm 2)
stress = ("schema_drift", "fault_reporting")


def load(proto):
    d = run_dir(proto, "llama31", "bfcl_multiple")
    raw = {(r["task_id"], r["condition"], r["trial_index"]): r["prompt_sha256"] for r in rd(d + "/raw_outputs.jsonl")}
    rows = {}
    for r in rd(d + "/parsed_results.jsonl"):
        k3 = (r["task_id"], r["condition"], r["trial_index"])
        rows[k3] = {"score": record_score(r), "drift": (r.get("drift") or {}).get("type"),
                    "fault": (r.get("fault") or {}).get("type"), "sha": raw[k3]}
    return rows


A, B = load("R"), load("R_AA")


def summarize(pairs_):
    res = {}
    for label, sel in (("identical_prompt", lambda p: p[1]), ("different_prompt", lambda p: not p[1]), ("all", lambda p: True)):
        rows = [p for p in pairs_ if sel(p)]
        percond = {}
        for c in stress:
            x = [p for p in rows if p[0] == c]
            percond[c] = {"n": len(x), "mean_diff": (sum(p[3] - p[2] for p in x) / len(x)) if x else None}
        vals = [v["mean_diff"] for v in percond.values() if v["mean_diff"] is not None]
        res[label] = {"n": len(rows),
                      "mean_diff_record_level": (sum(p[3] - p[2] for p in rows) / len(rows)) if rows else None,
                      "equal_weight_over_conditions": (sum(vals) / len(vals)) if vals else None,
                      "per_condition": percond}
    return res


a_pairs = []
for k, ra in A.items():
    if k[1] not in stress:
        continue
    rb = B.get(k)
    if rb and (ra["drift"], ra["fault"]) == (rb["drift"], rb["fault"]):
        a_pairs.append((k[1], ra["sha"] == rb["sha"], ra["score"], rb["score"]))
b_pairs = [(k[1], A[k]["sha"] == B[k]["sha"], A[k]["score"], B[k]["score"]) for k in A if k[1] in stress and k in B]
out["q4"] = {"analysis_matched_(task,cond,drift_type,fault_type,trial)": summarize(a_pairs),
             "all_stress_records_by_(task,cond,trial)": summarize(b_pairs)}

# ---- Q5: wall-clock
kaggle = {json.loads(l)["run"] for l in open("results_v2/_kaggle_import_log.jsonl")}
el = {}
for f in glob.glob("results_v2/*/*/*/_status.json"):
    p = f.replace("\\", "/").split("/")
    el[(p[1], p[2], p[3])] = json.load(open(f))["elapsed_seconds"]
tab = collections.defaultdict(lambda: {"laptop": [0, 0.0], "kaggle": [0, 0.0]})
for (pr, m, s), e in el.items():
    hw = "kaggle" if f"{pr}/{m}/{s}" in kaggle else "laptop"
    tab[pr][hw][0] += 1
    tab[pr][hw][1] += e
out["q5_phase1_by_folder"] = {pr: {hw: {"runs": v[hw][0], "hours": round(v[hw][1] / 3600, 2)} for hw in v}
                              for pr, v in sorted(tab.items())}


def folder_runs(pr):
    items = {(m, s): e for (p, m, s), e in el.items() if p == pr}
    if pr == "F3":  # official F3 = F3 without granite30 + F3_rerun
        for (m, s) in list(items):
            if m == "granite30":
                del items[(m, s)]
        items.update({(m, s): e for (p, m, s), e in el.items() if p == "F3_rerun"})
    return items


W1 = ["D", "R", "F1", "F2", "F3", "F4_json", "F5", "F6"]
rows = []
tot = {"laptop": 0.0, "kaggle": 0.0}
ph1 = {"laptop": 0.0, "kaggle": 0.0}
for pr in W1:
    for hw in ("laptop", "kaggle"):
        key_pr = "F3_rerun" if False else pr
        items = [(m, s, e) for (m, s), e in folder_runs(pr).items() if (f"{key_pr}/{m}/{s}" in kaggle) == (hw == "kaggle")]
        if not items:
            continue
        base = sum(e for _, _, e in items) / 3600
        factor = 10 / 3 if hw == "kaggle" else 7 / 3
        rows.append({"protocol": pr, "hardware": hw, "runs": len(items), "phase1_hours": round(base, 2),
                     "w1_new_hours": round(base * factor, 2),
                     "factor": "x10/3 (10 fresh)" if hw == "kaggle" else "x7/3 (7 new trials)"})
        tot[hw] += base * factor
        ph1[hw] += base
K11 = ["granite30", "granite31", "granite32", "llama3", "llama31", "mistral_v01", "mistral_v02", "mistral_v03", "qwen2",
       "qwen25", "qwen3"]
K5 = ["granite30", "granite31", "granite32", "llama3", "llama31"]
d_base = sum(el[("F5", m, s)] for m in K11 for s in SUITES) / 3600
r_base = sum(el[("R_F5", m, s)] for m in K5 for s in SUITES) / 3600
hw_ratio = {m: sum(el[("KAGGLE_HWCHECK", m, s)] for s in SUITES) / sum(el[("F5", m, s)] for s in SUITES)
            for m in ("llama3", "llama31")}
out["q5_w1"] = {
    "rows": rows,
    "new_kaggle_D_baselines": {"runs": 33, "proxy_phase1_hours(F5 same model/suite)": round(d_base, 2),
                               "w1_hours_x10/3": round(d_base * 10 / 3, 2)},
    "new_kaggle_R_baselines": {"runs": 15, "proxy_phase1_hours(R_F5 same model/suite)": round(r_base, 2),
                               "w1_hours_x10/3": round(r_base * 10 / 3, 2)},
    "hwcheck_Q4_over_F5_Q8_elapsed_ratio": {m: round(v, 3) for m, v in hw_ratio.items()},
    "totals": {"laptop_hours": round(tot["laptop"], 2), "kaggle_protocol_rows_hours": round(tot["kaggle"], 2),
               "kaggle_with_new_baselines_hours": round(tot["kaggle"] + (d_base + r_base) * 10 / 3, 2),
               "phase1_laptop_hours_in_W1_rows": round(ph1["laptop"], 2),
               "phase1_kaggle_hours_in_W1_rows": round(ph1["kaggle"], 2)}}
Path("results_v3/W0_determinism/prompt_seed_numbers.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps(out, indent=1))
