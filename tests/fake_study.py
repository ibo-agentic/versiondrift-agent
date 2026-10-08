"""FAKE results with known answers, for testing vdanalysis. Never touches real
results: everything is written under a caller-supplied (tmp) directory.

Layout mirrors the real one:
  <root>/<protocol folder>/<model>/<suite>/<run_id>/{parsed_results.jsonl,
  raw_outputs.jsonl, run_manifest.json}

Each fake run has N_TASKS tasks x 3 conditions x 3 trials = 180 records, 120
of them stress records (schema_drift + fault_reporting, 6 per task). Baseline
always succeeds. A "failure spec" makes ALL 6 stress records of a task fail
(or a chosen subset), so every paired difference is known exactly:

  pair    old fails    new fails     D stress diff   D point / CI label
  harm    -            tasks 0-5     -0.30           harmful / harmful
  neut    -            -              0.00           neutral / neutral
  ben     tasks 0-7    -             +0.40           beneficial / beneficial
  line    -            task 0        -0.05 exactly   neutral / neutral (not < -0.05)
  over    -            task 0 + 1    -7/120=-0.0583  harmful / neutral (CI touches 0)
  qwk     -            -              0.00           neutral (size-changing, "qwen-like")
  samp    -            -              0.00           neutral (new model's sampling changed)

Factor changes from D (everything else equals D):
  F1:  harm's new model passes            -> harm flips harmful->neutral
  F3:  neut's new model fails tasks 0-5   -> neut flips neutral->harmful
       (b_new's F3 data in the AUDIT-ONLY folder is all-fail; F3_rerun is clean)
  F4_json: qwk's new model fails 0-5      -> qwk flips, but is labeled "grammar+thinking_blocked"
  F6:  samp's new model fails 0-5         -> samp flips (the only sampling-changed pair)
  F2:  Qwen-like new model only, thinking off: no failures
  R*:  all clean except the qwk new model under the R variants (grammar) - same labels throughout
Controls: aa_ok (R vs R_AA identical), aa_bad (R_AA fails 8 tasks -> false alarm),
          pc_a / pc_b (R_PC_Q2K fails 12 tasks -> harmful).
"""

from __future__ import annotations

import json
from pathlib import Path

N_TASKS = 20
SUITES = ["s1", "s2"]
CONDS = ("baseline", "schema_drift", "fault_reporting")
FAULTS = [None, "timeout", "partial_result", "empty_result"]
STRESS = ("schema_drift", "fault_reporting")

PAIRS = [
    {"old": "h_old", "new": "h_new", "family": "fh", "split": "design"},
    {"old": "n_old", "new": "n_new", "family": "fn", "split": "held-out"},
    {"old": "b_old", "new": "b_new", "family": "fb", "split": "held-out"},
    {"old": "l_old", "new": "l_new", "family": "fl", "split": "design"},
    {"old": "x_old", "new": "x_new", "family": "fx", "split": "design"},
    {"old": "q_old", "new": "q_new", "family": "fq", "split": "held-out", "size_changing": True},
    {"old": "s_old", "new": "s_new", "family": "fs", "split": "design"},
]
CONTROL_MODELS = ["aa_ok", "aa_bad", "pc_a", "pc_b"]
MODELS = sorted({m for p in PAIRS for m in (p["old"], p["new"])} | set(CONTROL_MODELS))
RECORDS_PER_RUN = N_TASKS * 3 * 3


def fake_config_dict(root: Path, rescored_root: Path | None = None) -> dict:
    protocols = {
        "D": {"folder": "D"},
        "F1": {"folder": "F1", "expect_manifest": {"F1_max_tokens": 1024}},
        "F2": {"folder": "F2", "models": ["q_new"]},
        "F3": {"folder": "F3"},
        "F4_json": {"folder": "F4_json", "confounded_models": {"q_new": "grammar+thinking_blocked"}},
        "F5": {"folder": "F5"},
        "F6": {"folder": "F6"},
        "R": {"folder": "R", "confounded_models": {"q_new": "grammar+thinking_blocked"}},
        "R_F3": {"folder": "R_F3", "confounded_models": {"q_new": "grammar+thinking_blocked"}},
        "R_F5": {"folder": "R_F5", "confounded_models": {"q_new": "grammar+thinking_blocked"}},
        "R_F6": {"folder": "R_F6", "confounded_models": {"q_new": "grammar+thinking_blocked"}},
        "R_AA": {"folder": "R_AA", "control_only": True},
        "R_PC_Q2K": {"folder": "R_PC_Q2K", "control_only": True},
    }
    return {
        "results_root": str(root),
        "rescored_root": str(rescored_root or root / "_rescored"),
        "expected_records_per_run": RECORDS_PER_RUN,
        "stress_conditions": list(STRESS),
        "baseline_condition": "baseline",
        "gate": {"threshold": 0.05, "reps": 1000, "seed": 1234},
        "suites": SUITES,
        "models": {m: {"family": m.split("_")[0], "split": _model_split(m)} for m in MODELS},
        "pairs": PAIRS,
        "sampling_changed_models": ["s_new"],
        "base_protocol": "D",
        "protocols": protocols,
        "overrides": [{"protocol": "F3", "model": "b_new", "folder": "F3_rerun"}],
        "audit_only_folders": ["F3/b_new"],
        "factors": {
            "F1": {"protocol": "F1", "level": "1024"},
            "F2": {"protocol": "F2", "level": "thinking off"},
            "F3": {"protocol": "F3", "level": "native"},
            "F4": {"protocol": "F4_json", "level": "generic json"},
            "F5": {"protocol": "F5", "level": "q8"},
            "F6": {"protocol": "F6", "level": "recommended", "main_filter": "f6_sampling_changed"},
            "F9": {"kind": "gate", "level": "CI gate"},
        },
        "factor_groups": {
            "h1": ["F1", "F2", "F3", "F4", "F5", "F6", "F9"],
            "format": ["F1", "F2", "F4"],
            "other": ["F3", "F5", "F6"],
            "nuisance": ["F3", "F5", "F6"],
        },
        "robust": {"base": "R", "nuisance": {"F3": "R_F3", "F5": "R_F5", "F6": "R_F6"}},
        "qwen3_study": {"model": "q_new", "thinking_off": "F2", "grammar": "F4_json"},
        "controls": [
            {"name": "AA_R", "kind": "aa", "protocol_a": "R", "protocol_b": "R_AA", "gate": "ci",
             "h5": True, "models": ["aa_ok", "aa_bad"]},
            {"name": "PC_Q2K_R", "kind": "pc", "protocol_a": "R", "protocol_b": "R_PC_Q2K", "gate": "ci",
             "h5": True, "models": ["pc_a", "pc_b"]},
        ],
    }


def _model_split(m: str) -> str:
    held = {"n_old", "n_new", "b_old", "b_new", "q_old", "q_new", "aa_ok", "aa_bad", "pc_a", "pc_b"}
    return "held-out" if m in held else "design"


# ---- failure profiles: (protocol, model) -> list of failing task indices ----
def failing_tasks(protocol: str, model: str) -> list[int]:
    six = list(range(6))
    if model == "h_new" and protocol in ("D", "F3", "F4_json", "F5", "F6"):
        return six
    if model == "b_old":
        return list(range(8))
    if model == "l_new":
        return [0]
    if model == "x_new":
        return [0]  # plus one extra record, see _extra_fail
    if model == "n_new" and protocol == "F3":
        return six
    if model == "q_new" and protocol == "F4_json":
        return six
    if model == "s_new" and protocol == "F6":
        return six
    if model == "aa_bad" and protocol == "R_AA":
        return list(range(8))
    if model in ("pc_a", "pc_b") and protocol == "R_PC_Q2K":
        return list(range(12))
    if protocol == "F3" and model == "b_new":
        return list(range(N_TASKS))  # the audit-only (pre-fix) data
    return []


def _extra_fail(protocol: str, model: str) -> set[tuple]:
    """One extra failing record: task 1, schema_drift, trial 0 (makes 'over' 7/120)."""
    if model == "x_new":
        return {(1, "schema_drift", 0)}
    return set()


def _row(task: int, cond: str, trial: int, success: bool, kind: str) -> dict:
    drift = {"type": "field_rename", "tool": "t", "field": "f", "params": {}} if cond == "schema_drift" else None
    fault_type = FAULTS[task % 4] if cond == "fault_reporting" else None
    fault = {"type": fault_type, "params": {}} if fault_type else None
    if cond == "fault_reporting":
        ok = success
        metrics = {"parse_ok": ok or kind == "semantic", "status_ok": ok, "no_fabrication": True,
                   "score": float(ok), "strict_score": float(ok)}
    else:
        if success:
            metrics = {"parse_ok": True, "tool_name_ok": True, "args_exact": True, "args_intent_match": True,
                       "args_valid_under_drift": True, "executor_ok": True, "score": 1.0}
        elif kind == "format":
            metrics = {"parse_ok": False, "tool_name_ok": False, "args_exact": False, "args_intent_match": False,
                       "args_valid_under_drift": False, "executor_ok": False, "score": 0.0}
        else:
            metrics = {"parse_ok": True, "tool_name_ok": True, "args_exact": False, "args_intent_match": False,
                       "args_valid_under_drift": True, "executor_ok": True, "score": 0.0}
    return {"task_id": f"t{task:03d}", "condition": cond, "trial_index": trial,
            "temperature": 0.0 if trial == 0 else 0.7, "seed": 1234 + trial,
            "drift": drift, "fault": fault, "parsed_call": None, "exec_result": None, "metrics": metrics}


def run_rows(protocol: str, model: str) -> list[dict]:
    fails = set(failing_tasks(protocol, model))
    extra = _extra_fail(protocol, model)
    rows = []
    for task in range(N_TASKS):
        for cond in CONDS:
            for trial in range(3):
                failed = cond in STRESS and (task in fails or (task, cond, trial) in extra)
                # alternate failure kind so both buckets are exercised
                kind = "format" if task % 2 == 0 else "semantic"
                rows.append(_row(task, cond, trial, not failed, kind))
    # A/A rerun: sampled trial 1 of task 3 differs in one record, both ways cancel out
    if protocol == "R_AA" and model == "aa_ok":
        for r in rows:
            if r["task_id"] == "t003" and r["condition"] == "schema_drift" and r["trial_index"] == 1:
                r["metrics"] = _row(3, "schema_drift", 1, False, "semantic")["metrics"]
    return rows


def write_run(root: Path, folder: str, protocol: str, model: str, suite: str, *, data_from: str | None = None,
              truncated_fraction: float = 0.0, manifest_factors: dict | None = None) -> Path:
    run_dir = root / folder / model / suite / f"fake-{protocol}-{model}-{suite}"
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = run_rows(data_from or protocol, model)
    with open(run_dir / "parsed_results.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    n_trunc = int(len(rows) * truncated_fraction)
    with open(run_dir / "raw_outputs.jsonl", "w", encoding="utf-8") as fh:
        for i, r in enumerate(rows):
            fh.write(json.dumps({"task_id": r["task_id"], "condition": r["condition"],
                                 "trial_index": r["trial_index"], "raw_output": "{}",
                                 "truncated": i < n_trunc}) + "\n")
    factors = {"F1_max_tokens": 1024 if protocol == "F1" else 256}
    factors.update(manifest_factors or {})
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": run_dir.name, "num_records": len(rows), "run_factors": factors}), encoding="utf-8")
    return run_dir


def build_fake_results(root: Path, cfg_dict: dict | None = None) -> dict:
    cfg_dict = cfg_dict or fake_config_dict(root)
    for protocol, spec in cfg_dict["protocols"].items():
        models = spec.get("models") or MODELS
        if spec.get("control_only"):
            models = CONTROL_MODELS
        for model in models:
            for suite in SUITES:
                folder = spec["folder"]
                if protocol == "F3" and model == "b_new":
                    # audit-only original (all-fail) and the official rerun (clean = D)
                    write_run(root, "F3", "F3", model, suite)
                    write_run(root, "F3_rerun", "D", model, suite)
                    continue
                write_run(root, folder, protocol, model, suite,
                          truncated_fraction=0.05 if (protocol == "R" and model == "x_new") else 0.0)
    return cfg_dict
