"""Controls for Phase 2: legacy A/A, the new same-prompt A/A, positive
controls, and the secondary full-score gate (PLAN_PHASE2.md W2, W4).

Control kinds
-------------
aa    Phase 1's A/A: arm 2 is a rerun with a *different run seed*. Records are
      matched on (task, condition, drift type, fault type, trial) exactly as
      in Phase 1 (so only records whose drift/fault types agree are compared).
aa2   Phase 2's A/A: arm 2 keeps the run seed (so prompts are identical) and
      changes only the trial seeds. The code asserts that the prompts are
      identical for every (task, condition) and that *every* record of the two
      arms is matched; a violation raises ``ControlDesignError`` instead of
      producing a number.
pc    positive control: a model against a damaged copy of itself; correct
      label is harmful.

The secondary gate (W4) scores the full suite, baseline plus stress, with the
same rule and thresholds as the primary gate: the mean paired difference is
the equal-weight average over the three conditions (the same convention as the
stress diff, which averages its two conditions), a point label uses +-0.05, a
CI label also needs the task-cluster bootstrap CI to clear zero. The primary
gate columns are never touched; the secondary ones are extra columns.
"""

from __future__ import annotations

from typing import Any

from ..engine import Analysis
from ..loader import MissingRun, Run
from ..stats import compare
from .stats2 import clopper_pearson

EXPECTED = {"aa": "neutral", "aa2": "neutral", "pc": "harmful"}


class ControlDesignError(AssertionError):
    """An A/A (or other control) that does not have the design it is supposed to have."""


def full_score_columns(an: Analysis, old: Run, new: Run) -> dict[str, Any]:
    c = an.cfg
    conds = [c.baseline_condition, *c.stress]
    cmp = compare(old, new, conds, c.threshold, c.reps, c.seed, with_ci=an.with_ci)
    if cmp is None:
        return {"full_n_records": 0, "full_diff": None, "full_ci_lo": None, "full_ci_hi": None,
                "full_label_point": None, "full_label_ci": None}
    return {"full_n_records": cmp.n_records, "full_diff": cmp.diff, "full_ci_lo": cmp.ci_lo,
            "full_ci_hi": cmp.ci_hi, "full_label_point": cmp.label_point, "full_label_ci": cmp.label_ci}


def check_same_design(old: Run, new: Run, tag: str) -> None:
    """The aa2 assertions: identical prompts, every record matched."""
    po, pn = getattr(old, "prompts", None), getattr(new, "prompts", None)
    if not po or not pn:
        raise ControlDesignError(f"{tag}: prompts are not available for both arms, cannot verify the A/A design")
    if set(po) != set(pn):
        raise ControlDesignError(f"{tag}: the arms cover different (task, condition) sets")
    diff = [k for k in po if po[k] != pn[k]]
    if diff:
        raise ControlDesignError(f"{tag}: prompts differ between arms for {len(diff)} (task, condition) pairs, "
                                 f"e.g. {diff[0]}")
    if set(old.keys) != set(new.keys):
        only_old = len(set(old.keys) - set(new.keys))
        only_new = len(set(new.keys) - set(old.keys))
        raise ControlDesignError(f"{tag}: not every record is matched ({only_old} only in arm 1, {only_new} only in arm 2)")


def _greedy_scores_identical(old: Run, new: Run) -> bool | None:
    greedy = getattr(old, "greedy_trials", None)
    if greedy is None:
        return None
    gt = old.greedy_trials()
    keys = [k for k in old.keys if k[4] in gt and k in new.keys]
    return all(old.keys[k][0] == new.keys[k][0] for k in keys) if keys else None


def control_rows2(an: Analysis, secondary: bool = False, controls: list[dict] | None = None) -> list[dict[str, Any]]:
    """Rows for ``controls`` (default: the config's ``controls``)."""
    cfg = an.cfg
    out = []
    for ctl in (cfg.controls if controls is None else controls):
        kind = ctl["kind"]
        if kind not in EXPECTED:
            raise ValueError(f"control {ctl['name']}: unknown kind {kind!r}")
        label_key = "label_ci" if ctl.get("gate", "ci") == "ci" else "label_point"
        for model in ctl["models"]:
            pair = {"old": model, "new": model}
            for suite in cfg.suites:
                try:
                    old = an.run_for(ctl["protocol_a"], model, suite)
                    new = an.run_for(ctl["protocol_b"], model, suite)
                except FileNotFoundError as exc:
                    if not an.allow_missing:
                        raise
                    an.missing.append(f"control {ctl['name']}: {exc}")
                    continue
                if old is None or new is None:
                    continue
                if kind == "aa2":
                    check_same_design(old, new, f"{ctl['name']} {model}/{suite}")
                row = an.row_from_runs(ctl["protocol_b"], pair, suite, old, new, confound="")
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
                if secondary:
                    full = full_score_columns(an, old, new)
                    row.update(full)
                    fl = full["full_label_ci" if ctl.get("gate", "ci") == "ci" else "full_label_point"]
                    row["full_label"] = fl
                    row["full_correct"] = fl == EXPECTED[kind]
                if kind == "aa2":
                    row["greedy_scores_identical"] = _greedy_scores_identical(old, new)
                out.append(row)
    return out


def _bad(kind: str, label: str | None) -> bool:
    return label != "neutral" if kind in ("aa", "aa2") else label == "harmful"


def per_control_summary2(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per control: n, rate (false-alarm for A/A, detection for positive
    controls), exact Clopper-Pearson 95% CI, and the same for the secondary gate.
    The 3 suites of a model are not independent; ``n_models`` and
    ``n_models_with_flag`` give the cluster view."""
    out = []
    for name in sorted({r["control"] for r in rows}):
        sel = [r for r in rows if r["control"] == name]
        kind = sel[0]["kind"]
        rate_name = "false_alarm_rate" if kind in ("aa", "aa2") else "detection_rate"
        k = sum(_bad(kind, r["label"]) for r in sel)
        lo, hi = clopper_pearson(k, len(sel))
        models = {r["old"] for r in sel}
        row = {
            "control": name, "kind": kind, "gate": sel[0]["gate"], "h5": sel[0]["h5"],
            "n_decisions": len(sel), "n_flagged": k, rate_name: k / len(sel), "ci95_lo": lo, "ci95_hi": hi,
            "n_models": len(models),
            "n_models_with_flag": len({r["old"] for r in sel if _bad(kind, r["label"])}),
        }
        if "full_label" in sel[0]:
            kf = sum(_bad(kind, r["full_label"]) for r in sel)
            flo, fhi = clopper_pearson(kf, len(sel))
            row.update({"full_n_flagged": kf, f"full_{rate_name}": kf / len(sel),
                        "full_ci95_lo": flo, "full_ci95_hi": fhi,
                        "full_n_models_with_flag": len({r["old"] for r in sel if _bad(kind, r["full_label"])})})
        out.append(row)
    return out
