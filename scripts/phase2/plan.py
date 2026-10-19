"""Phase 2 run plan (PLAN_PHASE2.md v4): one manifest per workstream.

    python -m scripts.phase2.plan                 # (re)write configs/phase2/*.json from results_v2 timings

A manifest lists every run: protocol folder, model, suite, hardware, run seed, trial seeds,
temperatures, output folder under results_v3/, estimated hours. The run configs themselves are
built from a manifest entry by ``scripts.phase2.build.build_run_config`` (the laptop's own
``scripts.real_run_one.build_config`` with only the trial keys, experiment name and output folder
changed), so nothing about prompts, sampling presets, max_tokens, grammars or perturbations can
differ from Phase 1 by accident.

Trial schemes (section 2):
  laptop add-on   trials 4-10 only: trial seeds 1237-1243, all sampled (temperature 0.7), stored by the
                  runner as trial_index 0-6; the analysis config merges them with Phase 1's trials 1-3
                  (``trial_offset: 3``). Phase 1's records are reused, not re-run.
  fresh           all 10 trials: trial seeds 1234-1243, trial 1 greedy. Kaggle runs (assuming no reuse until
                  W0 Part C says otherwise) and the A/A second arm (trial seeds 5678-5687).
Estimated hours = Phase 1 elapsed time of the same run x 7/3 (add-on) or x 10/3 (fresh); W3 runs x
(added tasks / 100) x 10/3.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.real_run_models import MODEL_ORDER, SUITES  # noqa: E402

PLAN_VERSION = "PLAN_PHASE2.md v4"
MANIFEST_DIR = REPO_ROOT / "configs" / "phase2"
V3 = "results_v3"
RUN_SEED = 1234
N_TRIALS = 10
ADDON_FIRST = 3                         # Phase 1 stored trials 0-2
GREEDY_SAMPLED = 0.7
AA2_SEED_BASE = 5678
CONDITIONS = 3
SUITE_ORDER = list(SUITES)
MODEL_KEYS = [m for m, _ in MODEL_ORDER]    # fast-to-slow, Qwen3 last
LAPTOP_GGUF = dict(MODEL_ORDER)

F6_CHANGED = ["qwen2", "qwen25", "qwen3", "llama3", "llama31", "gemma3_4b"]
KAGGLE_D_MODELS = ["granite30", "granite31", "granite32", "llama3", "llama31", "mistral_v01", "mistral_v02",
                   "mistral_v03", "qwen2", "qwen25", "qwen3"]
KAGGLE_R_MODELS = ["granite30", "granite31", "granite32", "llama3", "llama31"]
CONTROL_MODELS = ["mistral_v03", "qwen25", "llama31", "granite32"]
ADDED_TASKS = {"synthetic": 200, "bfcl_simple": 91, "bfcl_multiple": 9}
W3_SUITE_DATA = {s: f"data/phase2/w3_added_{s}.jsonl" for s in SUITES}     # produced by the W3 task generator
W3_DEADLINE = "2026-11-20"
GPU_DEADLINE = "2026-12-10"

# Phase 1 protocol whose build_config the run uses, per output folder.
CONFIG_PROTOCOL = {
    "D": "D", "R": "R", "F1": "F1", "F2": "F2", "F3": "F3", "F4_json": "F4_json", "F5": "F5", "F6": "F6",
    "R_PC_Q2K": "R_PC_Q2K", "R_PC_NODESC": "R_PC_NODESC",
    "D_KAGGLE": "D", "R_KAGGLE": "R", "D_AA2": "D", "R_AA2": "R", "W3_D": "D", "W3_R": "R",
}
# Phase 1 folder whose run time is the estimate's base.
TIMING_FOLDER = {"D_KAGGLE": "F5", "R_KAGGLE": "R_F5", "D_AA2": "D", "R_AA2": "R", "W3_D": "D", "W3_R": "R"}

WORKSTREAMS = ["W1_laptop", "W1_kaggle", "W2_R", "W2_D", "W2b", "W3"]
# laptop queue, highest priority first (section 6): W1 (D and R first, then factors) > W2 (R) > W2b > W2 (D) [> W3]
LAPTOP_PRIORITY = ["W1_laptop", "W2_R", "W2b", "W2_D", "W3"]
W1_FOLDER_ORDER = ["D", "R", "F1", "F2", "F3", "F4_json", "F5", "F6"]


# ------------------------------------------------------------------------------------ Phase 1 timings
class Phase1Timing:
    """Phase 1 run times (read-only) from <root>/<folder>/<model>/<suite>/_status.json."""

    def __init__(self, root: Path, kaggle_runs: set[str] | None = None):
        self.root = Path(root)
        self.kaggle = kaggle_runs if kaggle_runs is not None else self._import_log()

    def _import_log(self) -> set[str]:
        p = self.root / "_kaggle_import_log.jsonl"
        if not p.exists():
            return set()
        return {json.loads(l)["run"] for l in p.read_text(encoding="utf-8").splitlines() if l.strip()}

    def seconds(self, folder: str, model: str, suite: str) -> float:
        p = self.root / folder / model / suite / "_status.json"
        s = json.loads(p.read_text(encoding="utf-8"))
        if not s.get("completed", True):
            raise ValueError(f"Phase 1 run {folder}/{model}/{suite} is not complete")
        return float(s["elapsed_seconds"])

    def exists(self, folder: str, model: str, suite: str) -> bool:
        return (self.root / folder / model / suite / "_status.json").exists()

    def on_kaggle(self, folder: str, model: str, suite: str) -> bool:
        return f"{folder}/{model}/{suite}" in self.kaggle

    def models(self, folder: str) -> list[str]:
        return [m for m in MODEL_KEYS if all(self.exists(folder, m, s) for s in SUITE_ORDER)]


# ------------------------------------------------------------------------------------ entries
def task_count(suite: str, data: str | None = None) -> int:
    path = REPO_ROOT / (data or SUITES[suite])
    return sum(1 for l in path.read_text(encoding="utf-8").splitlines() if l.strip())


def trial_scheme(kind: str, seed_base: int = RUN_SEED, sampled_temp: float = GREEDY_SAMPLED
                 ) -> tuple[int, list[int], list[float]]:
    """(first merged trial index, trial seeds, temperatures) for 'addon' or 'fresh'.
    ``sampled_temp`` is 0.7 everywhere except F6, whose sampled trials use the model's own preset."""
    if kind == "addon":
        n = N_TRIALS - ADDON_FIRST
        return ADDON_FIRST, [seed_base + ADDON_FIRST + i for i in range(n)], [sampled_temp] * n
    if kind == "fresh":
        return 0, [seed_base + i for i in range(N_TRIALS)], [0.0] + [sampled_temp] * (N_TRIALS - 1)
    raise ValueError(kind)


def make_entry(workstream: str, folder: str, model: str, suite: str, hardware: str, kind: str, hours: float,
               phase1_hours: float, quant: str, gguf: str | None, seed_base: int = RUN_SEED,
               data: str | None = None, data_status: str = "ok", n_tasks: int | None = None,
               note: str = "", sampled_temp: float = GREEDY_SAMPLED) -> dict[str, Any]:
    first, seeds, temps = trial_scheme(kind, seed_base, sampled_temp)
    n_tasks = n_tasks if n_tasks is not None else task_count(suite, data)
    return {
        "id": f"{folder}/{model}/{suite}",
        "workstream": workstream,
        "folder": folder,
        "config_protocol": CONFIG_PROTOCOL[folder],
        "model": model,
        "suite": suite,
        "hardware": hardware,
        "quant": quant,
        "gguf": gguf,
        "run_seed": RUN_SEED,
        "trial_first_index": first,
        "n_trials": len(seeds),
        "trial_seeds": seeds,
        "temperatures": temps,
        "reuse": "Phase 1 trials 1-3 (results_v2) reused; trials 4-10 run" if kind == "addon" else "all 10 trials run",
        "data": data or SUITES[suite],
        "data_status": data_status,
        "n_tasks": n_tasks,
        "expected_records": n_tasks * CONDITIONS * len(seeds),
        "output_dir": f"{V3}/{folder}/{model}/{suite}",
        "phase1_hours": round(phase1_hours, 4),
        "estimated_hours": round(hours, 4),
        "note": note,
    }


def _gguf(folder: str, model: str) -> str:
    from scripts.real_run_one import Q2K_MODEL_PATHS, Q8_0_MODEL_PATHS
    if folder == "R_PC_Q2K":
        return Q2K_MODEL_PATHS[model]
    if folder == "F5":
        return Q8_0_MODEL_PATHS[model]
    return LAPTOP_GGUF[model]


def _runs(models: Iterable[str]) -> list[tuple[str, str]]:
    return [(m, s) for m in MODEL_KEYS if m in set(models) for s in SUITE_ORDER]


def _phase1_scope(t: Phase1Timing, folder: str) -> list[str]:
    """Models that have a Phase 1 run of ``folder``; F3 uses F3 plus the granite30 re-run."""
    if folder == "F3":
        base = set(t.models("F3")) | set(t.models("F3_rerun"))
        return [m for m in MODEL_KEYS if m in base]
    return t.models(folder)


def _p1_seconds(t: Phase1Timing, folder: str, model: str, suite: str) -> float:
    if folder == "F3" and model == "granite30":
        return t.seconds("F3_rerun", model, suite)
    return t.seconds(folder, model, suite)


# ------------------------------------------------------------------------------------ manifests
def w1_laptop(t: Phase1Timing) -> list[dict]:
    out = []
    for folder in W1_FOLDER_ORDER:
        models = F6_CHANGED if folder == "F6" else _phase1_scope(t, folder)
        for model, suite in _runs(models):
            if folder == "F5" and t.on_kaggle("F5", model, suite):
                continue                                           # Kaggle: W1_kaggle
            p1 = _p1_seconds(t, folder, model, suite) / 3600
            temp = GREEDY_SAMPLED
            if folder == "F6":
                from scripts.real_run_one import F6_RECOMMENDED_SAMPLING
                temp = F6_RECOMMENDED_SAMPLING[model]["temperature"]
            out.append(make_entry("W1_laptop", folder, model, suite, "laptop", "addon", p1 * 7 / 3, p1,
                                  "Q8_0" if folder == "F5" else "Q4_K_M", _gguf(folder, model), sampled_temp=temp))
    return out


def _fresh_laptop(t: Phase1Timing, ws: str, folder: str, timing_folder: str, seed_base: int, models: list[str],
                  note: str = "") -> list[dict]:
    out = []
    for model, suite in _runs(models):
        p1 = t.seconds(timing_folder, model, suite) / 3600
        out.append(make_entry(ws, folder, model, suite, "laptop", "fresh", p1 * 10 / 3, p1, "Q4_K_M",
                              LAPTOP_GGUF[model], seed_base=seed_base, note=note))
    return out


def w2_r(t: Phase1Timing) -> list[dict]:
    return _fresh_laptop(t, "W2_R", "R_AA2", "R", AA2_SEED_BASE, t.models("R"),
                         "A/A arm 2 under R: run seed 1234 (same prompts), trial seeds 5678-5687")


def w2_d(t: Phase1Timing) -> list[dict]:
    return _fresh_laptop(t, "W2_D", "D_AA2", "D", AA2_SEED_BASE, t.models("D"),
                         "A/A arm 2 under D: run seed 1234 (same prompts), trial seeds 5678-5687")


def w2b(t: Phase1Timing) -> list[dict]:
    out = []
    for folder in ("R_PC_Q2K", "R_PC_NODESC"):
        for model, suite in _runs(CONTROL_MODELS):
            p1 = t.seconds(folder, model, suite) / 3600
            out.append(make_entry("W2b", folder, model, suite, "laptop", "addon", p1 * 7 / 3, p1,
                                  "Q2_K" if folder == "R_PC_Q2K" else "Q4_K_M", _gguf(folder, model)))
    return out


def w3(t: Phase1Timing, root: Path = REPO_ROOT) -> list[dict]:
    """Added tasks only. A suite's entries are 'ok' once its added-task file exists in the repo (the task count is then
    read from the file), else 'pending'."""
    out = []
    for folder, base in (("W3_D", "D"), ("W3_R", "R")):
        for model, suite in _runs(t.models(base)):
            p1 = t.seconds(base, model, suite) / 3600
            data = W3_SUITE_DATA[suite]
            have = (root / data).exists()
            n_added = task_count(suite, data) if have else ADDED_TASKS[suite]
            out.append(make_entry("W3", folder, model, suite, "laptop", "fresh", p1 * n_added / 100 * 10 / 3, p1,
                                  "Q4_K_M", LAPTOP_GGUF[model], data=data, data_status="ok" if have else "pending",
                                  n_tasks=n_added,
                                  note=f"added tasks only ({n_added}); merged with the W1 D/R records for the "
                                       "original 100." + ("" if have else " Task file not generated yet (pending).")))
    return out


def w1_kaggle(t: Phase1Timing) -> tuple[list[dict], list[dict]]:
    """Kaggle runs (all 10 trials fresh; may change after W0 Part C) and their batches."""
    out = []
    for model, suite in _runs(KAGGLE_D_MODELS):                  # F5, Q8_0
        p1 = t.seconds("F5", model, suite) / 3600
        out.append(make_entry("W1_kaggle", "F5", model, suite, "kaggle", "fresh", p1 * 10 / 3, p1, "Q8_0", None))
    for model, suite in _runs(KAGGLE_D_MODELS):                  # D on Kaggle, Q4_K_M (timing proxy: F5 on Kaggle)
        p1 = t.seconds("F5", model, suite) / 3600
        out.append(make_entry("W1_kaggle", "D_KAGGLE", model, suite, "kaggle", "fresh", p1 * 10 / 3, p1, "Q4_K_M",
                              None, note="timing proxy: the Q8_0 Kaggle run of the same model and suite"))
    for model, suite in _runs(KAGGLE_R_MODELS):                  # R on Kaggle (timing proxy: R_F5 on Kaggle)
        p1 = t.seconds("R_F5", model, suite) / 3600
        out.append(make_entry("W1_kaggle", "R_KAGGLE", model, suite, "kaggle", "fresh", p1 * 10 / 3, p1, "Q4_K_M",
                              None, note="timing proxy: the Q8_0 Kaggle R_F5 run of the same model and suite"))
    return out, kaggle_batches(out)


# ------------------------------------------------------------------------------------ Kaggle batches
LANE_CAP_HOURS = 9.0                 # "max ~9 h": a lane may exceed it by up to OVERSIZE_TOLERANCE before it is flagged
OVERSIZE_TOLERANCE = 0.5
ITEM_OVERHEAD_HOURS = 0.1            # model download + SHA-256 check per bundle chunk


def kaggle_bundles(entries: list[dict]) -> list[dict]:
    """Group runs that use the same model file (model, quant); split a bundle that would not fit a lane."""
    groups: dict[tuple, list[dict]] = {}
    for e in entries:
        groups.setdefault((e["model"], e["quant"]), []).append(e)
    bundles = []
    for (model, quant), runs in groups.items():
        chunk: list[dict] = []
        hours = ITEM_OVERHEAD_HOURS
        for r in sorted(runs, key=lambda r: (W1_FOLDER_ORDER.index(r["folder"]) if r["folder"] in W1_FOLDER_ORDER else 9,
                                              SUITE_ORDER.index(r["suite"]))):
            if chunk and hours + r["estimated_hours"] > LANE_CAP_HOURS:
                bundles.append({"model": model, "quant": quant, "runs": [x["id"] for x in chunk], "hours": hours})
                chunk, hours = [], ITEM_OVERHEAD_HOURS
            chunk.append(r)
            hours += r["estimated_hours"]
        bundles.append({"model": model, "quant": quant, "runs": [x["id"] for x in chunk], "hours": hours})
    return bundles


def kaggle_batches(entries: list[dict], cap: float = LANE_CAP_HOURS) -> list[dict]:
    """Pack bundles into lanes of at most ``cap`` hours (first fit, largest first), two lanes (one per T4) per
    batch. Q8_0 (F5) bundles come first. A single run longer than ``cap`` gets its own lane, flagged."""
    bundles = kaggle_bundles(entries)
    batches: list[dict] = []
    for klass in ("Q8_0", "Q4_K_M"):
        items = sorted((b for b in bundles if b["quant"] == klass), key=lambda b: -b["hours"])
        lanes: list[dict] = []
        for b in items:
            for lane in lanes:
                if lane["hours"] + b["hours"] <= cap:
                    lane["bundles"].append(b)
                    lane["hours"] += b["hours"]
                    break
            else:
                lanes.append({"bundles": [b], "hours": b["hours"]})
        lanes.sort(key=lambda l: -l["hours"])
        for i in range(0, len(lanes), 2):
            pair = lanes[i:i + 2]
            batches.append({"lanes": [{"runs": [r for b in l["bundles"] for r in b["runs"]],
                                       "bundles": [{"model": b["model"], "quant": b["quant"], "runs": b["runs"]}
                                                   for b in l["bundles"]],
                                       "estimated_hours": round(l["hours"], 3),
                                       "oversize": l["hours"] > cap + OVERSIZE_TOLERANCE} for l in pair]})
    for i, b in enumerate(batches, start=1):
        b["id"] = f"K{i:02d}"
        b["wall_hours"] = round(max(l["estimated_hours"] for l in b["lanes"]), 3)
    return batches


# ------------------------------------------------------------------------------------ assembly
def build_all(t: Phase1Timing) -> dict[str, dict]:
    kag, batches = w1_kaggle(t)
    runs = {"W1_laptop": w1_laptop(t), "W1_kaggle": kag, "W2_R": w2_r(t), "W2_D": w2_d(t), "W2b": w2b(t), "W3": w3(t)}
    out = {}
    for ws, entries in runs.items():
        for i, e in enumerate(entries):
            e["order"] = i
        hours = sum(e["estimated_hours"] for e in entries)
        m: dict[str, Any] = {
            "manifest": ws, "plan": PLAN_VERSION, "run_seed": RUN_SEED, "n_runs": len(entries),
            "estimated_hours": round(hours, 2),
            "hours_by_folder": {f: round(sum(e["estimated_hours"] for e in entries if e["folder"] == f), 2)
                                for f in dict.fromkeys(e["folder"] for e in entries)},
            "runs_by_folder": {f: sum(1 for e in entries if e["folder"] == f) for f in dict.fromkeys(e["folder"] for e in entries)},
        }
        if ws == "W1_kaggle":
            m["assumption"] = "all 10 trials fresh; changes if W0 Part C allows reuse of Phase 1's Kaggle trials"
            m["lane_cap_hours"] = LANE_CAP_HOURS
            m["batches"] = batches
        if ws == "W3":
            m["conditional"] = (f"runs only if W1, W2, W2b are complete by {W3_DEADLINE}; needs the added-task files "
                                "and the R split-equivalence check")
        m["runs"] = entries
        out[ws] = m
    return out


def write_manifests(manifests: dict[str, dict], out_dir: Path = MANIFEST_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, m in manifests.items():
        p = out_dir / f"{name}.json"
        p.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        paths.append(p)
    return paths


def load_manifest(name: str, directory: Path = MANIFEST_DIR) -> dict:
    return json.loads((Path(directory) / f"{name}.json").read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--phase1-root", default=str(REPO_ROOT / "results_v2"))
    ap.add_argument("--out", default=str(MANIFEST_DIR))
    args = ap.parse_args(argv)
    manifests = build_all(Phase1Timing(Path(args.phase1_root)))
    write_manifests(manifests, Path(args.out))
    for name, m in manifests.items():
        print(f"{name:10s} {m['n_runs']:4d} runs  {m['estimated_hours']:8.2f} h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
