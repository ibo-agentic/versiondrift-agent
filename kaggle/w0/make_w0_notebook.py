"""Builds kaggle/w0/w0_rerun.ipynb from kaggle/f5_runner.ipynb's own setup cells (repo, environment)
plus one run cell that executes ONLY Phase 1's F5 / qwen25 / synthetic run again.
Nothing in the existing kaggle/ code is modified."""
import json
from pathlib import Path

src = json.loads(Path("kaggle/f5_runner.ipynb").read_text(encoding="utf-8"))
cells = src["cells"]


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text.splitlines(True)}


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(True)}


intro = md("""# W0 Part C: exact re-run of ONE Phase 1 Kaggle F5 run (qwen25 / Q8_0 / synthetic)

Re-runs `F5 / qwen25 / synthetic` with the same code commit (ab758f8), config, GGUF files (SHA-256 verified),
seeds (1234/1235/1236), temperatures (0.0/0.7/0.7), llama-cpp-python 0.3.35, Python 3.12.12 as Phase 1.
Settings -> Accelerator = *GPU T4 x2* (as in Phase 1; only GPU 0 is used), Internet = *On*.
Output: `/kaggle/working/export/w0_rerun__F5__qwen25__synthetic.zip`. Do NOT import it with
`import_kaggle_results.py`; use `results_v3/W0_determinism/partC_compare.py`.
""")

settings = code("""# ---- 1. Settings -----------------------------------------------------------
REPO_SOURCE = "dataset"
GITHUB_REPO = ""; GITHUB_REF = ""; GITHUB_SECRET_NAME = "GITHUB_RO_TOKEN"
PINNED_LLAMA_CPP = "0.3.35"
ALLOW_PYTHON_MISMATCH = False
PHASES = ["F5"]
""")
gpu = code("""# ---- 2. Hardware check -----------------------------------------------------
import subprocess, time
SESSION_START = time.time()
gpus = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout
print(gpus)
assert len(gpus.strip().splitlines()) >= 1 and "T4" in gpus, "expected a Tesla T4 (Phase 1 hardware)"
""")
run = code('''# ---- 5. Run ONLY F5 / qwen25 / synthetic on GPU 0 ------------------------------------
import os, sys, subprocess, shutil, json
from pathlib import Path
EXPORT = Path("/kaggle/working/export"); STATE = Path("/kaggle/working/state")
MODELS = Path("/kaggle/temp/models") if Path("/kaggle/temp").exists() else Path("/tmp/models")
assert not (REPO / "results_v2" / "F5" / "qwen25" / "synthetic").exists(), "stale results in repo copy"
WRAP = Path("/kaggle/working/w0_worker.py")
WRAP.write_text("""
import sys
from pathlib import Path
sys.path.insert(0, sys.argv.pop(1))   # REPO/kaggle
import kaggle_plan as plan
_orig = plan.build_bundles
def one(phases=("hwcheck", "F5", "R_F5")):
    out = []
    for b in _orig(("F5",)):
        if b.model_key == "qwen25":
            out.append(type(b)(name=b.name, model_key=b.model_key, quant=b.quant, files=b.files, jobs=(("F5", "synthetic"),)))
    assert len(out) == 1 and out[0].jobs == (("F5", "synthetic"),)
    return out
plan.build_bundles = one
plan.all_jobs = lambda phases=("F5",): [("F5", "qwen25", "synthetic")]
import kaggle_worker
sys.exit(kaggle_worker.main())
""")
STATE.mkdir(parents=True, exist_ok=True); EXPORT.mkdir(parents=True, exist_ok=True)
cmd = [ENV.python, str(WRAP), str(REPO / "kaggle"), "--repo", str(REPO), "--models-dir", str(MODELS),
       "--state-dir", str(STATE), "--export-dir", str(EXPORT), "--phases", "F5", "--repo-commit", REPO_COMMIT]
t0 = time.time()
r = subprocess.run(cmd, env=dict(os.environ, **ENV.env, CUDA_VISIBLE_DEVICES="0"), cwd=str(REPO))
wall = time.time() - t0
print("worker exit", r.returncode, "wall-clock incl. model download/verify: %.0f s" % wall)
''')
summary = code('''# ---- 6. Rename + summary ----------------------------------------------------
z = EXPORT / "kaggle__F5__qwen25__synthetic.zip"
assert z.exists(), "run did not finish; see /kaggle/working/state/worker_gpu0.log"
out = EXPORT / "w0_rerun__F5__qwen25__synthetic.zip"
z.rename(out)
for f in EXPORT.glob("progress_gpu*.jsonl"):
    print(f.name, f.read_text())
print("Download:", out, "(", out.stat().st_size // 1_000_000, "MB )")
''')
nb = {"cells": [intro, settings, gpu, cells[3], cells[4], run, summary], "metadata": src["metadata"],
      "nbformat": src["nbformat"], "nbformat_minor": src["nbformat_minor"]}
Path("kaggle/w0/w0_rerun.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")
print("wrote kaggle/w0/w0_rerun.ipynb")
