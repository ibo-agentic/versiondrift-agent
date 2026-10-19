"""W0 Part B: exact re-run of one Phase 1 D laptop run.
Config = the saved Phase 1 config, with ONLY output_dir changed (to results_v3/W0_determinism/runs/...).
Usage: python partB_rerun.py <model_key> <suite>
"""
import sys, time, json, yaml
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "analysis" / "audit"))
import _dll_preload; _dll_preload.preload()
from upgradecanary.runner import run
m, s = sys.argv[1], sys.argv[2]
src = REPO / f"results_v2/_generated_configs/{m}__{s}.yaml"
cfg = yaml.safe_load(open(src, encoding="utf-8"))
cfg["output_dir"] = f"results_v3/W0_determinism/runs/{m}/{s}"
dst = REPO / f"results_v3/W0_determinism/runs/{m}__{s}.config.yaml"
dst.parent.mkdir(parents=True, exist_ok=True)
yaml.safe_dump(cfg, open(dst, "w", encoding="utf-8"), sort_keys=False)
t0 = time.time()
summary = run(str(dst))
el = time.time() - t0
(REPO / f"results_v3/W0_determinism/runs/{m}__{s}.timing.json").write_text(json.dumps({"model": m, "suite": s, "elapsed_seconds": el}))
print(m, s, "elapsed", round(el, 1))
