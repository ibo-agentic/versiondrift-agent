"""Shared helpers for the exploratory (post hoc, not pre-registered) analyses in scripts/exploratory/.

Rules every script here follows:
  * it reads existing data only (results_v2, results_v3, rescored_v3, analysis_out_v3*, data/); it never reruns a model;
  * it writes only into the output folder given with ``--out`` and refuses a folder inside a protected result folder;
  * every stress diff is rounded to 9 decimals before it is compared with a gate threshold (``rd`` and the helpers
    below), so that an exact +/-0.05 (or +/-0.03, +/-0.07) is never decided by floating-point noise: an exact boundary
    value counts as neutral (strict inequality), as the gates define it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DELTA = 0.05
DECIMALS = 9
SEED = 1234
BOOT_REPS = 10_000
SEPARATE_PAIR = "qwen25->qwen3"
CONFIG = REPO_ROOT / "configs" / "analysis_phase2.yaml"
ADDENDUM_DIR = REPO_ROOT / "analysis_out_v3" / "addendum"          # S1 per-decision noise, S3 classes (read only)
P7_DIR = REPO_ROOT / "analysis_out_v3_p7"                          # the Phase 2 tables (read only)
TEXT_DIR = Path(__file__).resolve().parent / "_text"               # hand-written paragraphs kept verbatim, see static()
PROTECTED = ("results", "results_smoke", "results_v2", "results_v3", "rescored", "rescored_v3", "analysis_out", "analysis_out_v3",
             "analysis_out_v3_p7", "data", "configs")
HEAD = ("**EXPLORATORY, post hoc. Not pre-registered. Existing data only (analysis at tag pre-analysis-v2.3, commit 73a9017); "
        "descriptive; feeds no gate, verdict or hypothesis.**\n\n")


# ---------------------------------------------------------------- rounding-safe gate comparisons
def rd(x: float) -> float:
    """Round a diff to 9 decimals (removes float noise such as 0.030000000000000002)."""
    return round(float(x), DECIMALS)


def rd_array(a) -> np.ndarray:
    return np.round(np.asarray(a, dtype=float), DECIMALS)


def point_label(diff: float, delta: float = DELTA) -> str:
    d = rd(diff)
    return "harmful" if d < -delta else "beneficial" if d > delta else "neutral"


def point_code(diffs, delta: float = DELTA) -> np.ndarray:
    """-1 harmful, 0 neutral, +1 beneficial, on rounded diffs (vectorised)."""
    d = rd_array(diffs)
    return np.where(d < -delta, -1, np.where(d > delta, 1, 0))


def ci_gate(diff: float, lo: float, hi: float, delta: float = DELTA) -> str:
    from upgradecanary.gates import ci_gate as gate
    return gate(rd(diff), lo, hi, delta)


def classify(point: float, lo90: float, hi90: float, label_ci: str, delta: float = DELTA) -> str:
    from vdanalysis.phase2.addendum.s3_fourclass import classify as four_class
    return four_class(rd(point), lo90, hi90, label_ci, delta)


# ---------------------------------------------------------------- output folder
def check_out_dir(out: str | Path) -> Path:
    p = Path(out).resolve()
    for name in PROTECTED:
        prot = (REPO_ROOT / name).resolve()
        if p == prot or prot in p.parents:
            raise SystemExit(f"refusing to write into the protected folder {prot} (use a scratch or temp folder)")
    p.mkdir(parents=True, exist_ok=True)
    return p


def parse_out(description: str, argv: list[str] | None = None) -> Path:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--out", required=True, help="output folder (created; must not be a protected result folder)")
    return check_out_dir(ap.parse_args(argv).out)


def static(name: str) -> str:
    """A hand-written paragraph kept verbatim in scripts/exploratory/_text/<name>.md (not recomputed)."""
    return (TEXT_DIR / f"{name}.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------- shared Phase 2 objects (loaded once per process)
_cache: dict = {}


def load_phase2():
    """(cfg, an, cx, flips): the Phase 2 analysis object (with CIs), the addendum context and the flip table."""
    if "p2" not in _cache:
        from vdanalysis.phase2.addendum.run_addendum import Ctx
        from vdanalysis.phase2.analysis import Phase2Analysis
        from vdanalysis.phase2.config import load_phase2_config
        cfg = load_phase2_config(str(CONFIG))
        an = Phase2Analysis(cfg, with_ci=True, allow_missing=True)
        _cache["p2"] = (cfg, an, Ctx(an), an.flip_table())
    return _cache["p2"]


def pct(x: float) -> str:
    return f"{100 * x:.1f}"
