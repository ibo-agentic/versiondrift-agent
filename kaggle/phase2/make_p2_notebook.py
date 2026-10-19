"""Builds kaggle/phase2/p2_runner.ipynb from kaggle/f5_runner.ipynb's own setup cells (repo, environment: the
same pinned llama-cpp-python 0.3.35 / Python 3.12.12 environment as Phase 1) plus the Phase 2 cells.
Nothing in the Phase 1 Kaggle code is modified.

    python kaggle/phase2/make_p2_notebook.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
src = json.loads((ROOT / "kaggle" / "f5_runner.ipynb").read_text(encoding="utf-8"))
cells = src["cells"]


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text.splitlines(True)}


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(True)}


intro = md("""# Phase 2 Kaggle runner (W1: F5, D and R baselines on 2x T4)

Runs ONE batch of `configs/phase2/W1_kaggle.json` (a batch = two lanes of at most ~9 h, one lane per T4),
all 10 trials fresh. Same code, configs, GGUF files (SHA-256 checked), llama-cpp-python 0.3.35 and
Python 3.12.12 as Phase 1; configs are built by `scripts/phase2/build.py` from the laptop's own
`build_config` with only the trial keys changed.

**Before running:** Settings -> Accelerator = *GPU T4 x2*, Internet = *On*. Add the code dataset
(`kaggle_repo.zip` from `kaggle/make_repo_archive.py`, made from the commit that holds `kaggle/phase2/`)
as an Input. To resume or continue, also attach earlier sessions' `p2__*.zip` outputs as Inputs.
Set `BATCH` below ("K01" ... or "next"), run all cells, download `/kaggle/working/export/p2__*.zip`, then on
the laptop: `python -m scripts.phase2.import_kaggle <folder with the zips> --apply`.
Nothing in this notebook contains a token.
""")
settings = code("""# ---- 1. Settings (edit here only) ------------------------------------------
BATCH = "next"                       # "K01" ... "K10", or "next" = first batch that is not complete
REPO_SOURCE = "dataset"              # "dataset" (recommended) or "github"
GITHUB_REPO = ""; GITHUB_REF = ""; GITHUB_SECRET_NAME = "GITHUB_RO_TOKEN"
SESSION_BUDGET_HOURS = 10.5          # no NEW run starts after this; running ones finish
PINNED_LLAMA_CPP = "0.3.35"          # same as Phase 1 (laptop run_manifest.json)
ALLOW_PYTHON_MISMATCH = False
""")
gpu = code("""# ---- 2. Hardware check: two Tesla T4 -----------------------------------------
import subprocess, time
SESSION_START = time.time()
gpus = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True).stdout
print(gpus)
lines = [l for l in gpus.strip().splitlines() if l.strip()]
assert len(lines) == 2 and all("T4" in l for l in lines), "need exactly 2 x Tesla T4 (Settings -> GPU T4 x2)"
""")
repo_cell = cells[3]
env_cell = cells[4]
extra = code("""# ---- 3b. Phase 2 helpers + version pin -----------------------------------------
sys.path.insert(0, str(REPO / "kaggle" / "phase2"))
import p2_session as p2
import kaggle_plan
assert kaggle_plan.LLAMA_CPP_PYTHON_VERSION == PINNED_LLAMA_CPP == "0.3.35", "llama-cpp-python pin must equal Phase 1's"
assert (REPO / "configs" / "phase2" / "W1_kaggle.json").exists(), "the code dataset predates configs/phase2"
batch = p2.pick_batch(REPO, BATCH)
print(p2.status_table(REPO, batch))
""")
restore = code("""# ---- 5. Restore runs finished in earlier sessions ---------------------------------
from pathlib import Path
EXPORT = Path("/kaggle/working/export"); STATE = Path("/kaggle/working/state")
MODELS = Path("/kaggle/temp/models") if Path("/kaggle/temp").exists() else Path("/tmp/models")
for line in p2.restore_from_inputs(REPO, EXPORT):
    print(line)
print(p2.status_table(REPO, batch))
""")
run = code("""# ---- 6. Run the batch: one worker per GPU (lane 0 on GPU 0, lane 1 on GPU 1) ----
deadline = SESSION_START + SESSION_BUDGET_HOURS * 3600
procs = p2.launch_workers(REPO, MODELS, STATE, EXPORT, batch["id"], deadline, REPO_COMMIT,
                          hard_limit_epoch=SESSION_START + 11.5 * 3600, python=ENV.python, extra_env=ENV.env)
p2.monitor(procs, STATE, every=120)
""")
summary = code("""# ---- 7. Summary ----------------------------------------------------------------
import json
print(p2.status_table(REPO, batch))
for f in sorted(EXPORT.glob("progress_gpu*.jsonl")):
    rows = [json.loads(l) for l in f.read_text().splitlines()]
    print(f.name, len(rows), "runs; actual vs estimated hours:",
          [(r["id"], round(r["elapsed_seconds"] / 3600, 2), r["estimated_hours"]) for r in rows])
print("\\nDownload every /kaggle/working/export/p2__*.zip (Output panel), then on the laptop:")
print("  python -m scripts.phase2.import_kaggle <folder with the zips> --apply")
""")
nb = {"cells": [intro, settings, gpu, repo_cell, extra, env_cell, restore, run, summary], "metadata": src["metadata"],
      "nbformat": src["nbformat"], "nbformat_minor": src["nbformat_minor"]}
out = ROOT / "kaggle" / "phase2" / "p2_runner.ipynb"
out.write_text(json.dumps(nb, indent=1), encoding="utf-8")
print("wrote", out)
