"""W0 Part A, breakdown by condition and by prompt identity (prompt_sha256 equal in both arms)."""
import glob, json, collections
from pathlib import Path
def L(d):
    return {(r["task_id"], r["condition"], r["trial_index"]): r
            for r in map(json.loads, open(glob.glob(d)[0] + "/raw_outputs.jsonl", encoding="utf-8"))}
models = ["mistral_v02", "qwen2", "qwen25", "llama31", "phi35_mini", "granite31"]
suites = ["synthetic", "bfcl_simple", "bfcl_multiple"]
c = collections.defaultdict(lambda: [0, 0])
for m in models:
    for s in suites:
        a = L(f"results_v2/R/{m}/{s}/upgradecanary-*"); b = L(f"results_v2/R_AA/{m}/{s}/upgradecanary-*")
        for k in a:
            kind = "greedy" if a[k]["temperature"] == 0 else "sampled"
            same_p = a[k]["prompt_sha256"] == b[k]["prompt_sha256"]
            same = a[k]["raw_output"] == b[k]["raw_output"]
            for key in ((kind, "ALL"), (kind, k[1]), (kind, "same_prompt" if same_p else "diff_prompt")):
                c[key][0] += 1; c[key][1] += same
out = {f"{k[0]}|{k[1]}": {"n": v[0], "pct_raw_identical": round(100 * v[1] / v[0], 2)} for k, v in sorted(c.items())}
Path("results_v3/W0_determinism/partA_breakdown.json").write_text(json.dumps(out, indent=1))
for k, v in out.items(): print(k, v)
