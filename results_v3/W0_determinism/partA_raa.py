"""W0 Part A: Phase 1 R (arm 1, seeds 1234-1236) vs R_AA (arm 2, seeds 5678-5680). No GPU."""
import glob, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from w0_compare import compare
models = ["mistral_v02", "qwen2", "qwen25", "llama31", "phi35_mini", "granite31"]
suites = ["synthetic", "bfcl_simple", "bfcl_multiple"]
rows, agg = [], {"greedy": [0, 0, 0, 0], "sampled": [0, 0, 0, 0]}
for m in models:
    for s in suites:
        a = glob.glob(f"results_v2/R/{m}/{s}/upgradecanary-*")[0]
        b = glob.glob(f"results_v2/R_AA/{m}/{s}/upgradecanary-*")[0]
        r = compare(a, b, f"{m}/{s}")
        rows.append(r)
        for g, k in (("greedy_all", "greedy"), ("sampled_all", "sampled")):
            t = r["trials"][g]; n = t["n"]
            agg[k][0] += n
            agg[k][1] += round(t["pct_raw_identical"] * n / 100)
            agg[k][2] += round(t["pct_parsed_identical"] * n / 100)
            agg[k][3] += round(t["pct_score_identical"] * n / 100)
summary = {k: {"n_records": v[0], "pct_raw_identical": 100 * v[1] / v[0], "pct_parsed_identical": 100 * v[2] / v[0],
               "pct_score_identical": 100 * v[3] / v[0]} for k, v in agg.items()}
Path("results_v3/W0_determinism/partA_raa.json").write_text(json.dumps({"summary": summary, "pairs": rows}, indent=1))
print(json.dumps(summary, indent=1))
for r in rows:
    print(r["label"], "greedy raw %.2f%%" % r["trials"]["greedy_all"]["pct_raw_identical"], "sampled raw %.2f%%" % r["trials"]["sampled_all"]["pct_raw_identical"], "matched", r["n_matched"])
