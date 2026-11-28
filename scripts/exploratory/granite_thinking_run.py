"""Exploratory add-on (not pre-registered): granite32 with thinking ON. See analysis/exploratory/EXPLORATORY_PLAN_granite_thinking.md.

    python -m scripts.exploratory.granite_thinking_run --arm pilot            # 5 tasks per suite, 1 trial (greedy), 256 tokens
    python -m scripts.exploratory.granite_thinking_run --arm think256         # 10 trials, 256 tokens  (full plan; not run yet)
    python -m scripts.exploratory.granite_thinking_run --arm think1024        # 10 trials, 1024 tokens (full plan; not run yet)
    python -m scripts.exploratory.granite_thinking_run --arm think256 --trials 3   # the plan's first step: trials 0-2 only
    python -m scripts.exploratory.granite_thinking_run --arm pilot --configs-only

Each config is the main study's D config of granite32 for that suite (results_v3/_generated_configs/D__granite32__<suite>.yaml, which
check_configs proved equal to the Phase 1 config outside the trial keys) with only these changes: stress conditions only; the trial
keys (seeds 1234.. and temperatures 0.0, 0.7, ... as in the D main run); model.chat_template_kwargs {thinking: true} (the variable the
GGUF's own chat template reads); max_tokens per arm; parsing.thinking_policy: strict; output under results_exploratory/granite_thinking/.
Suites run one after another in this one process. Do not start it while any other runner (run_laptop, run_one, upgradecanary.runner)
is running.
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = REPO_ROOT / "results_exploratory" / "granite_thinking"
SUITES = ("synthetic", "bfcl_simple", "bfcl_multiple")
ARMS = {
    "pilot": {"trials": 1, "max_tokens": 256, "task_limit": 5},
    "think256": {"trials": 10, "max_tokens": 256, "task_limit": None},
    "think1024": {"trials": 10, "max_tokens": 1024, "task_limit": None},
}


def build_config(arm: str, suite: str, trials: int | None = None) -> dict:
    """``trials`` (optional) runs only the first N trials of the arm: the same seeds and temperatures as its first N trials."""
    spec = ARMS[arm]
    base = yaml.safe_load((REPO_ROOT / "results_v3" / "_generated_configs" / f"D__granite32__{suite}.yaml").read_text(encoding="utf-8"))
    cfg = copy.deepcopy(base)
    n = spec["trials"] if trials is None else trials
    if not 1 <= n <= spec["trials"]:
        raise ValueError(f"--trials must be between 1 and {spec['trials']} for arm {arm}")
    cfg["experiment"] = f"exploratory-granite32-thinking-{arm}-{suite}"
    cfg["output_dir"] = str((OUT_ROOT / arm / suite).relative_to(REPO_ROOT)).replace("\\", "/")
    cfg["conditions"] = ["schema_drift", "fault_reporting"]
    cfg["trials"] = n
    cfg["trial_seeds"] = [1234 + i for i in range(n)]
    cfg["trial_temperatures"] = [0.0] + [0.7] * (n - 1)
    cfg["model"]["max_tokens"] = spec["max_tokens"]
    cfg["model"]["chat_template_kwargs"] = {"thinking": True}
    cfg.setdefault("parsing", {})["thinking_policy"] = "strict"
    if spec["task_limit"]:
        cfg["task_limit"] = spec["task_limit"]
    assert base["model"]["path"].endswith("ibm-granite_granite-3.2-8b-instruct-Q4_K_M.gguf")
    return cfg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", required=True, choices=sorted(ARMS))
    ap.add_argument("--suites", nargs="*", default=list(SUITES))
    ap.add_argument("--trials", type=int, default=None, help="run only the first N trials of the arm (same seeds and temperatures)")
    ap.add_argument("--configs-only", action="store_true")
    args = ap.parse_args(argv)
    cfg_dir = OUT_ROOT / "_configs"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for suite in args.suites:
        p = cfg_dir / f"{args.arm}__{suite}.yaml"
        p.write_text(yaml.safe_dump(build_config(args.arm, suite, args.trials), sort_keys=False), encoding="utf-8")
        paths.append(p)
        print("config", p.relative_to(REPO_ROOT))
    if args.configs_only:
        return 0
    import os
    os.chdir(REPO_ROOT)                                          # the runner resolves data/output paths against the cwd
    sys.path.insert(0, str(REPO_ROOT / "analysis" / "audit"))
    import _dll_preload                                          # this machine's llama.dll workaround (as scripts/phase2/run_one.py)
    _dll_preload.preload()
    from upgradecanary.runner import run
    for p in paths:
        summary = run(str(p))
        print("done", p.name, {c: (v.get("n"), v.get("mean_score"), v.get("mean_parse_ok")) for c, v in summary.get("conditions", {}).items()}, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
