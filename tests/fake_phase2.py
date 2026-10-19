"""FAKE Phase 1 + Phase 2 results with known answers, for testing vdanalysis.phase2.
Everything is written under a caller-supplied (tmp) directory; real results are never touched.

World: 8 models, 4 adjacent pairs, 2 suites, 20 tasks (t000-t019; W3 adds t020-t029), 3 conditions.
A run has 10 trials in total: Phase 1 stored trials 0-2 (results_v2, seeds 1234-1236); the laptop
add-on stores trials 3-9 (results_v3, trial_index 0-6, seeds 1237-1243); Kaggle runs store all 10
fresh in results_v3. A "failing task" fails all its stress records of the listed trials.

  models   a_old a_new | b_old b_new (Kaggle for F5) | c_old c_new (F6 sampling changed) | d_old d_new
  D        no failures anywhere -> every pair neutral
  F1       a_new fails t0-t5            -> pair a flips neutral->harmful
  F5       b_new fails t0-t5 (Kaggle), d_new fails t0-t5 (laptop)
           D_KAGGLE: b_new fails t0-t5  -> same-hardware: pair b does NOT flip; vs laptop D it would
  F6       c_new fails t0-t5            -> pair c flips (the only sampling-changed pair);
           a_new fails t0-t5 too, but a is in the trimmed set (F6 = D) -> must not flip
  F7/F10   same as D (no flips)
  A/A      D_AA2: c_old fails t0-t5 in sampled trials only (-0.27, point gate false alarm);
           R_AA2: a_old fails t0-t5 sampled only (false alarm), d_old fails t0-t1 sampled only (-0.09:
           point label harmful, CI label neutral)
  PC       R_PC_Q2K (W2b, 10 trials): a_new,c_new,d_new fail t0-t11, b_new fails t0-t1 (not detected by the CI gate)
           R_PC_NODESC (W2b): a_new,b_new baseline condition fails t0-t7 -> invisible to the stress gate
  W3       W3_D adds tasks t020-t029; a_new fails t020-t027 there -> pair a: neutral on the original
           tasks, harmful on the full set
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests.fake_study import CONDS, STRESS, _row

N_TASKS = 20
N_ADDED = 10
SUITES = ["s1", "s2"]
MODELS = ["a_old", "a_new", "b_old", "b_new", "c_old", "c_new", "d_old", "d_new"]
KAGGLE = ["b_old", "b_new"]
TRIM = ["a_old", "a_new", "b_old", "b_new", "c_old", "d_old", "d_new"]
PAIRS = [
    {"old": "a_old", "new": "a_new", "family": "fa", "split": "design"},
    {"old": "b_old", "new": "b_new", "family": "fb", "split": "held-out"},
    {"old": "c_old", "new": "c_new", "family": "fc", "split": "design"},
    {"old": "d_old", "new": "d_new", "family": "fd", "split": "held-out"},
]
SIX = set(range(6))
N_FULL = 10


def spec_table() -> dict[tuple, dict]:
    """(protocol, model) -> {tasks, conds, min_trial}; anything absent never fails."""
    def s(tasks, conds=STRESS, min_trial=0):
        return {"tasks": set(tasks), "conds": tuple(conds), "min_trial": min_trial}
    return {
        ("F1", "a_new"): s(SIX),
        ("F5", "b_new"): s(SIX), ("F5", "d_new"): s(SIX),
        ("D_KAGGLE", "b_new"): s(SIX),
        ("F6", "c_new"): s(SIX), ("F6", "a_new"): s(SIX),
        ("R_F5", "b_new"): s(SIX), ("R_KAGGLE", "b_new"): s(SIX),
        ("D_AA2", "c_old"): s(SIX, min_trial=1),
        ("R_AA2", "a_old"): s(SIX, min_trial=1), ("R_AA2", "d_old"): s({0, 1}, min_trial=1),
        ("R_PC_Q2K", "a_new"): s(range(12)), ("R_PC_Q2K", "c_new"): s(range(12)),
        ("R_PC_Q2K", "d_new"): s(range(12)), ("R_PC_Q2K", "b_new"): s({0, 1}),
        ("R_PC_NODESC", "a_new"): s(range(8), conds=("baseline",)),
        ("R_PC_NODESC", "b_new"): s(range(8), conds=("baseline",)),
        ("W3_D", "a_new"): s(range(20, 28)),
        # garbage in a place that must NOT be read (Kaggle models' Phase 1 F5 part is excluded)
        ("F5_v2_kaggle_garbage", "b_old"): s(range(N_TASKS)), ("F5_v2_kaggle_garbage", "b_new"): s(range(N_TASKS)),
    }


SPECS = spec_table()


def prompt_sha(run_seed: int, task: int, cond: str) -> str:
    return hashlib.sha256(f"{run_seed}|{task}|{cond}".encode()).hexdigest()


def _fails(protocol: str, model: str, task: int, cond: str, trial: int) -> bool:
    sp = SPECS.get((protocol, model))
    return bool(sp and task in sp["tasks"] and cond in sp["conds"] and trial >= sp["min_trial"])


def write_part(root: Path, folder: str, spec_key: str, model: str, suite: str, trials: range, offset: int,
               seed_base: int = 1234, run_seed: int = 1234, tasks=range(N_TASKS), raw: bool = True,
               run_id: str | None = None) -> Path:
    """One run directory holding merged trials ``trials`` (stored as trial_index = t - offset)."""
    run_dir = root / folder / model / suite / (run_id or f"fake-{folder}-{model}-{suite}-o{offset}")
    run_dir.mkdir(parents=True, exist_ok=True)
    parsed, raws = [], []
    for task in tasks:
        for cond in CONDS:
            for t in trials:
                row = _row(task, cond, t - offset, not _fails(spec_key, model, task, cond, t),
                           "format" if task % 2 == 0 else "semantic")
                row["seed"] = seed_base + t
                row["temperature"] = 0.0 if t == 0 else 0.7
                parsed.append(row)
                raws.append({"task_id": row["task_id"], "condition": cond, "trial_index": t - offset,
                             "prompt_sha256": prompt_sha(run_seed, task, cond), "raw_output": "{}", "truncated": False})
    with open(run_dir / "parsed_results.jsonl", "w", encoding="utf-8") as fh:
        fh.write("".join(json.dumps(r, sort_keys=True) + "\n" for r in parsed))
    if raw:
        with open(run_dir / "raw_outputs.jsonl", "w", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in raws))
    (run_dir / "run_manifest.json").write_text(json.dumps({"run_id": run_dir.name, "num_records": len(parsed),
                                                           "run_factors": {}}), encoding="utf-8")
    return run_dir


def phase1_reference_rows() -> list[dict]:
    def r(factor, pair, suite, d, f, n_changed=2):
        return {"factor": factor, "n_models_changed": n_changed, "level": "", "pair": pair, "suite": suite,
                "family": "", "split": "", "size_changing": "False", "f6_sampling_changed": "False",
                "confounding": "", "d_label": d, "factor_label": f, "flipped": str(d != f), "sign_flip": "False",
                "d_diff": 0, "factor_diff": 0, "delta_diff": 0, "delta_from_format": 0, "delta_from_semantic": 0,
                "dominant_bucket": "semantic"}
    return [
        r("F1", "a_old->a_new", "s1", "neutral", "harmful"),
        r("F1", "a_old->a_new", "s2", "neutral", "harmful"),
        r("F7", "a_old->a_new", "s2", "neutral", "harmful"),
        r("F5", "b_old->b_new", "s1", "neutral", "harmful"),
        r("F6", "c_old->c_new", "s1", "neutral", "beneficial", n_changed=1),
        r("F5", "d_old->d_new", "s2", "neutral", "harmful"),
        r("F1", "d_old->d_new", "s1", "neutral", "neutral"),        # not a flip: must be ignored
    ]


def build_phase2_world(root: Path) -> tuple[dict, dict[str, Path]]:
    """Write all fake data under ``root``; returns (config dict, paths)."""
    v2, v3, rs2, rs3 = root / "results_v2", root / "results_v3", root / "rescored", root / "rescored_v3"

    def laptop(protocol: str, models=MODELS):
        for m in models:
            for su in SUITES:
                write_part(v2, protocol, protocol, m, su, range(0, 3), 0)
                write_part(v3, protocol, protocol, m, su, range(3, 10), 3)

    for p in ("D", "R", "F1", "F6"):
        laptop(p)
    for m in MODELS:                                           # F5
        for su in SUITES:
            if m in KAGGLE:
                write_part(v3, "F5", "F5", m, su, range(0, 10), 0)
                write_part(v2, "F5", "F5_v2_kaggle_garbage", m, su, range(0, 3), 0)
            else:
                write_part(v2, "F5", "F5", m, su, range(0, 3), 0)
                write_part(v3, "F5", "F5", m, su, range(3, 10), 3)
    for m in MODELS:                                           # scoring-only F7: rescored trees, no raw outputs
        for su in SUITES:
            write_part(rs2, "F7", "D", m, su, range(0, 3), 0, raw=False)
            write_part(rs3, "F7", "D", m, su, range(3, 10), 3, raw=False)
    for m in KAGGLE:
        for su in SUITES:
            write_part(v3, "D_KAGGLE", "D_KAGGLE", m, su, range(0, 10), 0)
            write_part(v3, "R_KAGGLE", "R_KAGGLE", m, su, range(0, 10), 0)
    for m in MODELS:
        for su in SUITES:
            write_part(v3, "D_AA2", "D_AA2", m, su, range(0, 10), 0, seed_base=5678)
            write_part(v3, "R_AA2", "R_AA2", m, su, range(0, 10), 0, seed_base=5678)
    for m in ("b_old", "b_new", "d_old", "d_new"):             # R_F5: Phase 1 only (3 trials)
        for su in SUITES:
            write_part(v2, "R_F5", "R_F5", m, su, range(0, 3), 0)
    for m in ("a_new", "b_new", "c_new", "d_new"):             # W2b: Phase 1 trials 0-2 + new trials 3-9
        for su in SUITES:
            write_part(v2, "R_PC_Q2K", "R_PC_Q2K", m, su, range(0, 3), 0)
            write_part(v3, "R_PC_Q2K", "R_PC_Q2K", m, su, range(3, 10), 3)
    for m in ("a_new", "b_new"):
        for su in SUITES:
            write_part(v2, "R_PC_NODESC", "R_PC_NODESC", m, su, range(0, 3), 0)
            write_part(v3, "R_PC_NODESC", "R_PC_NODESC", m, su, range(3, 10), 3)
    for proto in ("D", "R"):                                   # W3 added tasks (separate runs, all 10 trials)
        for m in MODELS:
            for su in SUITES:
                write_part(v3, f"W3_{proto}", f"W3_{proto}", m, su, range(0, 10), 0, tasks=range(N_TASKS, N_TASKS + N_ADDED))
    paths = {"v2": v2, "v3": v3, "rescored": rs2, "rescored_v3": rs3}

    ref = root / "phase1_factor_flips_long.csv"
    rows = phase1_reference_rows()
    import csv
    with open(ref, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    paths["reference"] = ref
    orig = {}
    for su in SUITES:
        p = root / f"orig_{su}.jsonl"
        p.write_text("".join(json.dumps({"task_id": f"t{i:03d}"}) + "\n" for i in range(N_TASKS)), encoding="utf-8")
        orig[su] = str(p)

    allm = list(MODELS)
    laptop_w1 = [{"root": "results_root", "trial_offset": 0}, {"root": "v3", "trial_offset": 3, "overrides": False}]
    rescored_w1 = [{"root": "rescored_root", "trial_offset": 0}, {"root": "rescored_v3", "trial_offset": 3, "overrides": False}]
    cfg = {
        "results_root": str(v2), "rescored_root": str(rs2), "expected_records_per_run": 600,
        "stress_conditions": list(STRESS), "baseline_condition": "baseline",
        "gate": {"threshold": 0.05, "reps": 1000, "seed": 1234}, "suites": SUITES,
        "models": {m: {"family": m[0], "split": "design" if m[0] in "ac" else "held-out"} for m in MODELS},
        "pairs": PAIRS, "sampling_changed_models": ["c_new"], "base_protocol": "D",
        "protocols": {
            "D": {"folder": "D"}, "R": {"folder": "R"}, "F1": {"folder": "F1"}, "F5": {"folder": "F5"},
            "F6": {"folder": "F6"}, "F7": {"folder": "F7", "root": "rescored"}, "F10": {"folder": "F10"},
            "D_KAGGLE": {"folder": "D_KAGGLE", "control_only": True, "models": KAGGLE},
            "R_KAGGLE": {"folder": "R_KAGGLE", "control_only": True, "models": KAGGLE},
            "D_AA2": {"folder": "D_AA2", "control_only": True}, "R_AA2": {"folder": "R_AA2", "control_only": True},
            "R_PC_Q2K": {"folder": "R_PC_Q2K", "control_only": True},
            "R_PC_NODESC": {"folder": "R_PC_NODESC", "control_only": True},
            "R_P1": {"folder": "R", "control_only": True},
            "R_PC_Q2K_P1": {"folder": "R_PC_Q2K", "control_only": True},
            "R_PC_NODESC_P1": {"folder": "R_PC_NODESC", "control_only": True},
            "R_F5": {"folder": "R_F5", "models": ["b_old", "b_new", "d_old", "d_new"]},
            "D_W3": {"folder": "D", "control_only": True}, "R_W3": {"folder": "R", "control_only": True},
        },
        "overrides": [], "audit_only_folders": [],
        "factors": {
            "F1": {"protocol": "F1", "level": "1024"},
            "F5": {"protocol": "F5", "level": "q8"},
            "F6": {"protocol": "F6", "level": "recommended", "main_min_changed": 1, "changed_models": ["c_new"]},
            "F7": {"protocol": "F7", "level": "lenient"},
            "F9": {"kind": "gate", "level": "CI gate"},
            "F10": {"protocol": "F10", "level": "greedy only"},
        },
        "factor_groups": {"h1": ["F1", "F5", "F6", "F7", "F9", "F10"], "format": ["F1", "F7"],
                          "other": ["F5", "F6"], "nuisance": ["F5"]},
        "robust": {"base": "R", "nuisance": {"F5": "R_F5"}},
        "controls": [
            {"name": "AA2_R", "kind": "aa2", "protocol_a": "R", "protocol_b": "R_AA2", "gate": "ci", "models": allm},
            {"name": "AA2_D", "kind": "aa2", "protocol_a": "D", "protocol_b": "D_AA2", "gate": "point", "models": allm},
            {"name": "PC_Q2K_R", "kind": "pc", "protocol_a": "R", "protocol_b": "R_PC_Q2K", "gate": "ci",
             "models": ["a_new", "b_new", "c_new", "d_new"]},
            {"name": "PC_NODESC_R", "kind": "pc", "protocol_a": "R", "protocol_b": "R_PC_NODESC", "gate": "ci",
             "models": ["a_new", "b_new"]},
        ],
        "phase2": {
            "mode": "phase2", "roots": {"v3": str(v3), "rescored_v3": str(rs3)}, "n_trials": 10, "seed_base": 1234,
            "phase1_reference": str(ref),
            "decision_protocols": ["D", "R", "F1", "F5", "F6", "F7", "F10"],
            "model_sets": {"kaggle_d": KAGGLE, "kaggle_r": KAGGLE, "f6_equals_d": TRIM},
            "default_parts": [{"root": "auto"}],
            "protocols": {
                "D": {"parts": laptop_w1}, "R": {"parts": laptop_w1}, "F1": {"parts": laptop_w1},
                "F6": {"parts": laptop_w1},
                "F5": {"parts": [
                    {"root": "v3", "trial_offset": 0, "overrides": False, "models": "kaggle_d"},
                    {"root": "results_root", "trial_offset": 0, "exclude_models": "kaggle_d"},
                    {"root": "v3", "trial_offset": 3, "overrides": False, "exclude_models": "kaggle_d"}]},
                "F7": {"parts": rescored_w1},
                "D_KAGGLE": {"parts": [{"root": "v3", "trial_offset": 0, "overrides": False}]},
                "R_KAGGLE": {"parts": [{"root": "v3", "trial_offset": 0, "overrides": False}]},
                "D_AA2": {"parts": [{"root": "v3", "trial_offset": 0, "overrides": False}], "seed_base": 5678},
                "R_AA2": {"parts": [{"root": "v3", "trial_offset": 0, "overrides": False}], "seed_base": 5678},
                "D_W3": {"parts": [{"root": "results_root", "folder": "D", "trial_offset": 0},
                                   {"root": "v3", "folder": "D", "trial_offset": 3, "overrides": False},
                                   {"root": "v3", "folder": "W3_D", "trial_offset": 0, "overrides": False}]},
                "R_W3": {"parts": [{"root": "results_root", "folder": "R", "trial_offset": 0},
                                   {"root": "v3", "folder": "R", "trial_offset": 3, "overrides": False},
                                   {"root": "v3", "folder": "W3_R", "trial_offset": 0, "overrides": False}]},
                "F10": {"view_of": "D", "trials": "greedy"},
                "R_PC_Q2K": {"parts": laptop_w1}, "R_PC_NODESC": {"parts": laptop_w1},
                # Phase 1 records only (3 trials): for the descriptive secondary-gate table
                "R_P1": {"parts": [{"root": "results_root", "folder": "R"}], "n_trials": 3},
                "R_PC_Q2K_P1": {"parts": [{"root": "results_root", "folder": "R_PC_Q2K"}], "n_trials": 3},
                "R_PC_NODESC_P1": {"parts": [{"root": "results_root", "folder": "R_PC_NODESC"}], "n_trials": 3},
                "R_F5": {"n_trials": 3},
            },
            "f6_trim": {"protocol": "F6", "base": "D", "models": "f6_equals_d"},
            "same_hardware": {"F5": {"baseline": "D_KAGGLE", "models": "kaggle_d"},
                              "R_F5": {"baseline": "R_KAGGLE", "models": "kaggle_r"}},
            "hypotheses": {"p1_threshold": 0.20, "p2_min_replicated": 7, "p3_max": 0.05, "p4_min": 0.90,
                           "p6_min_replicated": 4},
            "descriptive_controls": [
                {"name": "P1_PC_Q2K_R", "kind": "pc", "protocol_a": "R_P1", "protocol_b": "R_PC_Q2K_P1", "gate": "ci",
                 "models": ["a_new", "b_new", "c_new", "d_new"]},
                {"name": "P1_PC_NODESC_R", "kind": "pc", "protocol_a": "R_P1", "protocol_b": "R_PC_NODESC_P1", "gate": "ci",
                 "models": ["a_new", "b_new"]}],
            "p3_control": "AA2_R", "p4_control": "PC_Q2K_R", "p5_control": "PC_NODESC_R", "f5_aa_control": "AA2_D",
            "w3": {"protocols": {"D": {"protocol": "D_W3", "gate": "point"}, "R": {"protocol": "R_W3", "gate": "ci"}},
                   "original_tasks": orig},
        },
    }
    return cfg, paths
