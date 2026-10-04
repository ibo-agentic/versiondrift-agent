"""Orchestrator for PLAN.md 10.2 smoke tests (2026-10-04): runs
scripts/smoke_one_model.py as a separate subprocess for each of the 16
models, sequentially (one GPU, one model loaded at a time). Resumable: a
model already having results_smoke/<model_key>/model_result.json is
skipped, so re-running this script after an interruption only does the
remaining models.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.smoke_models import MODEL_REGISTRY  # noqa: E402

OUT_ROOT = REPO_ROOT / "results_smoke"


def _already_done(model_key: str) -> bool:
    """True only for a genuine completion -- a `load_error` (e.g. the GGUF
    not downloaded yet) must NOT count as done, so re-running this
    orchestrator after more downloads land retries it instead of skipping
    it forever."""
    result_path = OUT_ROOT / model_key / "model_result.json"
    if not result_path.exists():
        return False
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return "load_error" not in data and bool(data.get("configs"))


def main() -> None:
    for model_key in MODEL_REGISTRY:
        if _already_done(model_key):
            print(f"[{model_key}] already has a complete result, skipping.", flush=True)
            continue
        print(f"\n=== {model_key} ===", flush=True)
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "smoke_one_model.py"), model_key],
            cwd=str(REPO_ROOT),
        )
        print(f"[{model_key}] subprocess exit code: {proc.returncode}", flush=True)

    print("\nAll models attempted.", flush=True)


if __name__ == "__main__":
    main()
