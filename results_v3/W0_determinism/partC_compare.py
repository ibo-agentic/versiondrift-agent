"""W0 Part C comparison: Kaggle re-run of Phase 1 F5/qwen25/synthetic vs the Phase 1 run in results_v2.

usage (from repo root):
  python results_v3/W0_determinism/partC_compare.py <path to w0_rerun__F5__qwen25__synthetic.zip>
Extracts the zip under results_v3/W0_determinism/kaggle_rerun/ (never touches results_v2), compares record by record
per trial (byte-identical raw output, identical parsed call, identical strict score), prints 3 example diffs
and both wall-clock times, and writes partC_result.json next to this script.
"""
import glob, json, sys, zipfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from w0_compare import compare

zpath = Path(sys.argv[1])
dest = HERE / "kaggle_rerun"
dest.mkdir(exist_ok=True)
with zipfile.ZipFile(zpath) as zf:
    zf.extractall(dest)
new_runs = glob.glob(str(dest / "results_v2/F5/qwen25/synthetic/upgradecanary-*"))
old_runs = glob.glob("results_v2/F5/qwen25/synthetic/upgradecanary-*")
assert len(new_runs) == 1 and len(old_runs) == 1, (new_runs, old_runs)
new, old = new_runs[0], old_runs[0]
res = compare(old, new, "F5/qwen25/synthetic (Phase 1 Kaggle vs W0 Kaggle re-run)")
mo, mn = (json.load(open(p + "/run_manifest.json")) for p in (old, new))
so, sn = (json.load(open(Path(p).parent / "_status.json")) for p in (old, new))
res["provenance"] = {
    "phase1": {"repo_commit": mo["kaggle"]["repo_commit"], "gpu": mo["hardware"].get("gpu"), "elapsed_seconds": so["elapsed_seconds"],
               "llama_cpp": mo["model_backend"]["llama_cpp_python_version"], "python": mo["python"]},
    "rerun": {"repo_commit": mn["kaggle"]["repo_commit"], "gpu": mn["hardware"].get("gpu"), "elapsed_seconds": sn["elapsed_seconds"],
              "llama_cpp": mn["model_backend"]["llama_cpp_python_version"], "python": mn["python"]},
    "sha256_phase1": [f["sha256_actual"] for f in mo["kaggle"]["model_files"]],
    "sha256_rerun": [f["sha256_actual"] for f in mn["kaggle"]["model_files"]],
}
(HERE / "partC_result.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
for g, v in res["trials"].items():
    print(f"{g:12s} n={v['n']:5d} raw={v['pct_raw_identical']:.2f}% parsed={v['pct_parsed_identical']:.2f}% score={v['pct_score_identical']:.2f}%")
for ex in res["examples"]:
    print("DIFF", ex["key"], "\n  A:", repr(ex["raw_a"])[:300], "\n  B:", repr(ex["raw_b"])[:300])
print(json.dumps(res["provenance"], indent=1))
