"""A/A null pairs and positive controls (PLAN.md section 6, H5).

Each control entry in the config names two protocols and the models to
compare, e.g. {kind: aa, protocol_a: R, protocol_b: R_AA} compares each
model's R run against its own R_AA rerun (different sampling seed). A/A's
correct label is neutral; a positive control (kind: pc) compares a model
against a deliberately damaged copy and the correct label is harmful.
"""

from __future__ import annotations

from typing import Any

from .engine import Analysis

EXPECTED = {"aa": "neutral", "pc": "harmful"}


def control_rows(analysis: Analysis) -> list[dict[str, Any]]:
    cfg = analysis.cfg
    out = []
    for ctl in cfg.controls:
        kind = ctl["kind"]
        label_key = "label_ci" if ctl.get("gate", "ci") == "ci" else "label_point"
        for model in ctl["models"]:
            pair = {"old": model, "new": model}
            for suite in cfg.suites:
                try:
                    old = analysis.store.get(ctl["protocol_a"], model, suite)
                    new = analysis.store.get(ctl["protocol_b"], model, suite)
                except FileNotFoundError as exc:
                    if not analysis.allow_missing:
                        raise
                    analysis.missing.append(f"control {ctl['name']}: {exc}")
                    continue
                row = analysis.row_from_runs(ctl["protocol_b"], pair, suite, old, new, confound="")
                if row is None:
                    continue
                row["pair"] = f"{model}->{model}"
                label = row[label_key]
                row.update({
                    "control": ctl["name"], "kind": kind, "gate": ctl.get("gate", "ci"),
                    "h5": bool(ctl.get("h5", False)),
                    "model_split": cfg.models[model].get("split", ""),
                    "label": label, "expected": EXPECTED[kind], "correct": label == EXPECTED[kind],
                })
                out.append(row)
    return out


def control_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """H5 inputs: only controls flagged ``h5: true`` (the R-protocol ones)."""
    aa = [r for r in rows if r["kind"] == "aa" and r["h5"]]
    pc = [r for r in rows if r["kind"] == "pc" and r["h5"]]
    return {
        "n_aa": len(aa),
        "false_alarm_rate": (sum(1 for r in aa if r["label"] != "neutral") / len(aa)) if aa else None,
        "n_pc": len(pc),
        "detection_rate": (sum(1 for r in pc if r["label"] == "harmful") / len(pc)) if pc else None,
    }


def per_control_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for name in sorted({r["control"] for r in rows}):
        sel = [r for r in rows if r["control"] == name]
        kind = sel[0]["kind"]
        bad = sum(1 for r in sel if r["label"] != "neutral") if kind == "aa" else sum(1 for r in sel if r["label"] == "harmful")
        out.append({
            "control": name, "kind": kind, "gate": sel[0]["gate"], "h5": sel[0]["h5"],
            "n_models": len({r["old"] for r in sel}),
            "n_design_models": len({r["old"] for r in sel if r["model_split"] == "design"}),
            "n_held_out_models": len({r["old"] for r in sel if r["model_split"] == "held-out"}),
            "n_decisions": len(sel),
            "false_alarm_rate" if kind == "aa" else "detection_rate": bad / len(sel),
        })
    return out
