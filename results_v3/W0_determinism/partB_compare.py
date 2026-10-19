"""W0 Part B: compare each laptop re-run to its Phase 1 D run. Writes partB_result.json."""
import glob, json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from w0_compare import compare
picks = [("gemma2_2b", "synthetic"), ("phi3_mini", "bfcl_simple"), ("gemma3_4b", "bfcl_multiple")]
out = []
for m, s in picks:
    t = Path(f"results_v3/W0_determinism/runs/{m}__{s}.timing.json")
    if not t.exists():
        continue
    old = glob.glob(f"results_v2/D/{m}/{s}/upgradecanary-*")[0]
    new = glob.glob(f"results_v3/W0_determinism/runs/{m}/{s}/upgradecanary-*")[0]
    r = compare(old, new, f"{m}/{s}")
    r["phase1_elapsed_seconds"] = json.load(open(Path(old).parent / "_status.json"))["elapsed_seconds"]
    r["rerun_elapsed_seconds"] = json.load(open(t))["elapsed_seconds"]
    out.append(r)
    print(r["label"], "matched", r["n_matched"], "| phase1 %.0fs rerun %.0fs" % (r["phase1_elapsed_seconds"], r["rerun_elapsed_seconds"]))
    for g, v in r["trials"].items():
        print(f"  {g:12s} n={v['n']:4d} raw={v['pct_raw_identical']:.2f}% parsed={v['pct_parsed_identical']:.2f}% score={v['pct_score_identical']:.2f}%")
    for ex in r["examples"]:
        print("  DIFF", ex["key"], "\n    old:", repr(ex["raw_a"])[:250], "\n    new:", repr(ex["raw_b"])[:250])
Path("results_v3/W0_determinism/partB_result.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
