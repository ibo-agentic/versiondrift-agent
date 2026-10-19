"""Build a Phase 2 run config from a manifest entry.

The config is the laptop's own ``scripts.real_run_one.build_config`` for the entry's Phase 1 protocol
(so prompts, grammars, max_tokens, perturbations, sampling presets can only be what Phase 1 used), with
exactly these keys replaced: experiment, output_dir, trials, trial_temperatures, trial_seeds, and the
per-trial sampling lists of F6 (cut to the trials that are run). ``diff_against_phase1`` proves it.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

TRIAL_LISTS = ("trial_top_p", "trial_top_k", "trial_min_p", "trial_repeat_penalty")
# keys a Phase 2 config may differ in from its Phase 1 counterpart
ALLOWED_DIFF = {"experiment", "output_dir", "trials", "trial_temperatures", "trial_seeds", *TRIAL_LISTS}


class ManifestError(ValueError):
    pass


def build_run_config(entry: dict[str, Any], gguf: str | None = None) -> dict[str, Any]:
    from scripts.real_run_one import build_config

    path = gguf or entry.get("gguf")
    if not path:
        raise ManifestError(f"{entry['id']}: no GGUF path (Kaggle runs must pass the downloaded file)")
    if not entry["output_dir"].startswith("results_v3/"):
        raise ManifestError(f"{entry['id']}: output_dir {entry['output_dir']!r} is not under results_v3/")
    cfg = build_config(entry["model"], path, entry["suite"], entry["data"], protocol=entry["config_protocol"],
                       output_dir=entry["output_dir"])
    base_temps = cfg["trial_temperatures"]                      # [greedy, sampled, sampled]
    sampled = base_temps[1]
    temps = list(entry["temperatures"])
    want = [0.0 if t == 0.0 else sampled for t in temps]
    if temps != want:
        raise ManifestError(f"{entry['id']}: manifest temperatures {temps} disagree with the Phase 1 config "
                            f"(sampled trials use {sampled})")
    if cfg["seed"] != entry["run_seed"] or cfg["model"]["seed"] != entry["run_seed"]:
        raise ManifestError(f"{entry['id']}: run seed {cfg['seed']} in the Phase 1 config, {entry['run_seed']} in the manifest")
    if len(temps) != entry["n_trials"] or len(entry["trial_seeds"]) != entry["n_trials"]:
        raise ManifestError(f"{entry['id']}: n_trials does not match the temperature/seed lists")
    apply_trials(cfg, list(entry["trial_seeds"]), temps)
    cfg["experiment"] = f"upgradecanary-real-{entry['folder']}-{entry['model']}-{entry['suite']}"
    return cfg


def apply_trials(cfg: dict[str, Any], seeds: list[int], temps: list[float]) -> dict[str, Any]:
    """Replace the trial keys of a Phase 1 config in place: trials, trial_seeds, trial_temperatures and the
    per-trial sampling lists of F6 (greedy trials keep the greedy value, sampled trials the sampled one)."""
    if len(seeds) != len(temps):
        raise ManifestError("trial seeds and temperatures differ in length")
    for key in TRIAL_LISTS:
        if key in cfg:
            greedy_value, sampled_value = cfg[key][0], cfg[key][1]
            cfg[key] = [greedy_value if t == 0.0 else sampled_value for t in temps]
    cfg["trials"] = len(seeds)
    cfg["trial_temperatures"] = list(temps)
    cfg["trial_seeds"] = list(seeds)
    return cfg


def phase1_config_path(entry: dict[str, Any], phase1_root: Path) -> Path | None:
    """Phase 1's generated config for the same (protocol, model, suite), if it exists."""
    gen = Path(phase1_root) / "_generated_configs"
    proto = entry["config_protocol"]
    if proto == "F3" and entry["model"] == "granite30":
        proto = "F3_rerun"                                        # the official granite30 F3 run
    stem = f"{entry['model']}__{entry['suite']}" if proto == "D" else f"{proto}__{entry['model']}__{entry['suite']}"
    for name in (f"{stem}.yaml", f"{stem}__half1.yaml"):
        if (gen / name).exists():
            return gen / name
    return None


def diff_against_phase1(entry: dict[str, Any], cfg: dict[str, Any], phase1_root: Path) -> list[str] | None:
    """Keys (outside the allowed trial/name/output keys) in which the Phase 2 config differs from Phase 1's.
    None when Phase 1 has no generated config to compare with. A Kaggle run's GGUF path is allowed to differ."""
    p = phase1_config_path(entry, phase1_root)
    if p is None:
        return None
    old = yaml.safe_load(p.read_text(encoding="utf-8"))
    new = copy.deepcopy(cfg)
    allowed = set(ALLOWED_DIFF)
    if p.stem.endswith("__half1") or entry["folder"].startswith("W3_"):
        allowed.add("data")      # Phase 1 ran this one as two halves of the task file / W3 runs the added tasks
    out = []
    for k in sorted(set(old) | set(new)):
        if k in allowed:
            continue
        if k == "model":
            a, b = dict(old[k]), dict(new[k])
            for d in (a, b):                                      # older Phase 1 configs omit the default explicitly
                if d.get("thinking") == "default":
                    d.pop("thinking")
            if entry["hardware"] == "kaggle":
                a.pop("path", None)
                b.pop("path", None)
            if a != b:
                out.append("model: " + ", ".join(sorted(f for f in set(a) | set(b) if a.get(f) != b.get(f))))
        elif old.get(k) != new.get(k):
            out.append(k)
    return out


def write_config(cfg: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False)
    return path
