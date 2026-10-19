"""Read-only: numbers for COMPUTE_ESTIMATE.md. Hours = sum of Phase 1 _status.json elapsed_seconds, scaled."""
import glob, json, collections
from pathlib import Path

el = {}
for f in glob.glob("results_v2/*/*/*/_status.json"):
    p = f.replace("\\", "/").split("/")
    el[(p[1], p[2], p[3])] = json.load(open(f))["elapsed_seconds"]
kaggle = {json.loads(l)["run"] for l in open("results_v2/_kaggle_import_log.jsonl")}
H = lambda s: s / 3600
SUITES = ["synthetic", "bfcl_simple", "bfcl_multiple"]
SAME = ["mistral_v01", "mistral_v02", "mistral_v03", "phi3_mini", "phi35_mini", "phi4_mini", "granite30", "granite31",
        "granite32", "gemma2_2b"]
out = {}

# Q2: W1 laptop minus F6 runs that equal D (all F6 runs are laptop)
f6_same = sum(el[("F6", m, s)] for m in SAME for s in SUITES)
f6_all = sum(v for (p, m, s), v in el.items() if p == "F6")
out["q2"] = {"F6_all_phase1_h": H(f6_all), "F6_equal_D_phase1_h": H(f6_same), "F6_equal_D_runs": len(SAME) * 3,
             "F6_changed_phase1_h": H(f6_all - f6_same), "F6_changed_runs": 18,
             "F6_w1_h_before": H(f6_all) * 7 / 3, "F6_w1_h_after": H(f6_all - f6_same) * 7 / 3,
             "saved_h": H(f6_same) * 7 / 3}


def folder(pr):
    items = {(m, s): e for (p, m, s), e in el.items() if p == pr}
    if pr == "F3":
        for k in [k for k in items if k[0] == "granite30"]:
            del items[k]
        items.update({(m, s): e for (p, m, s), e in el.items() if p == "F3_rerun"})
    return items


W1 = ["D", "R", "F1", "F2", "F3", "F4_json", "F5", "F6"]
lap = kag = 0.0
rows = []
for pr in W1:
    for (m, s), e in folder(pr).items():
        on_k = f"{pr}/{m}/{s}" in kaggle
        if pr == "F6" and m in SAME:
            continue
        if on_k:
            kag += H(e) * 10 / 3
        else:
            lap += H(e) * 7 / 3
K11 = ["granite30", "granite31", "granite32", "llama3", "llama31", "mistral_v01", "mistral_v02", "mistral_v03", "qwen2",
       "qwen25", "qwen3"]
K5 = ["granite30", "granite31", "granite32", "llama3", "llama31"]
kD = sum(H(el[("F5", m, s)]) for m in K11 for s in SUITES) * 10 / 3
kR = sum(H(el[("R_F5", m, s)]) for m in K5 for s in SUITES) * 10 / 3
out["q2"]["W1_laptop_h_recomputed"] = lap
out["q2"]["W1_kaggle_h_F5_rows"] = kag
out["q2"]["W1_kaggle_h_new_D_baselines"] = kD
out["q2"]["W1_kaggle_h_new_R_baselines"] = kR
out["q2"]["W1_kaggle_h_total"] = kag + kD + kR

# Q3: W2 arm 2, 10 fresh trials, laptop, 16 models x 3 suites
rR = sum(v for (p, m, s), v in el.items() if p == "R")
rD = sum(v for (p, m, s), v in el.items() if p == "D")
out["q3"] = {"R_phase1_h": H(rR), "R_runs": sum(1 for k in el if k[0] == "R"), "W2_R_h": H(rR) * 10 / 3,
             "D_phase1_h": H(rD), "D_runs": sum(1 for k in el if k[0] == "D"), "W2_D_h": H(rD) * 10 / 3,
             "R_qwen3_phase1_h": H(sum(v for (p, m, s), v in el.items() if p == "R" and m == "qwen3")),
             "D_qwen3_phase1_h": H(sum(v for (p, m, s), v in el.items() if p == "D" and m == "qwen3")),
             "greedy_trial_share_of_10": 0.1}

# Q4: W3, added tasks only. frac = added/100; hours = Phase 1 elapsed * frac * 10/3
ADD = {"synthetic": 200, "bfcl_simple": 91, "bfcl_multiple": 9}
q4 = {}
for pr in ("D", "R"):
    per = {s: 0.0 for s in SUITES}
    for (p, m, s), e in el.items():
        if p == pr:
            per[s] += H(e) * ADD[s] / 100 * 10 / 3
    q4[pr] = {"per_suite_h": per, "total_h": sum(per.values())}
# optional: Kaggle same-hardware baselines for W3 (D: 11 models via F5 proxy; R: 5 models via R_F5 proxy)
kd3 = sum(H(el[("F5", m, s)]) * ADD[s] / 100 * 10 / 3 for m in K11 for s in SUITES)
kr3 = sum(H(el[("R_F5", m, s)]) * ADD[s] / 100 * 10 / 3 for m in K5 for s in SUITES)
q4["optional_kaggle_D_baselines_h"] = kd3
q4["optional_kaggle_R_baselines_h"] = kr3
q4["runs_added"] = {"D": 48, "R": 48}
out["q4"] = q4

# Q5 totals
tot = {"W1": {"laptop": lap, "kaggle": kag + kD + kR},
       "W2_R": {"laptop": out["q3"]["W2_R_h"], "kaggle": 0.0},
       "W2_D": {"laptop": out["q3"]["W2_D_h"], "kaggle": 0.0},
       "W3": {"laptop": q4["D"]["total_h"] + q4["R"]["total_h"], "kaggle": 0.0}}
tot["all"] = {"laptop": sum(v["laptop"] for v in tot.values()), "kaggle": sum(v["kaggle"] for v in tot.values())}
tot["W3_optional_extra_kaggle_h"] = kd3 + kr3
out["q5"] = tot
Path("results_v3/W0_determinism/compute_estimate_numbers.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
