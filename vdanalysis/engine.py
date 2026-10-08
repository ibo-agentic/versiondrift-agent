"""Decision rows: one per (protocol/setup, adjacent pair, suite).

A decision's label comes from the stress diff (mean paired success
difference new - old over the stress conditions, PLAN.md section 4) under
both gates: ``label_point`` (D's +-0.05 rule) and ``label_ci`` (PLAN.md
section 8's cluster-bootstrap CI gate). Nothing here runs a model.
"""

from __future__ import annotations

from typing import Any

from .config import Config
from .loader import MissingRun, Run, Store
from .stats import compare


class Analysis:
    def __init__(self, cfg: Config, store: Store | None = None, with_ci: bool = True,
                 allow_missing: bool = False):
        self.cfg = cfg
        self.store = store or Store(cfg)
        self.with_ci = with_ci
        self.allow_missing = allow_missing
        self.missing: list[str] = []
        self._rows: dict[str, dict[tuple, dict]] = {}

    # ---- run access -----------------------------------------------------
    def run_for(self, protocol: str, model: str, suite: str) -> Run | None:
        """The run for ``model`` under ``protocol``, falling back to the base
        protocol when the protocol does not cover that model (e.g. F2 is
        Qwen3-only, so the Qwen2.5 side of Qwen2.5->Qwen3 comes from D)."""
        proto = protocol if self.store.applies(protocol, model) else self.cfg.base_protocol
        try:
            return self.store.get(proto, model, suite)
        except MissingRun as exc:
            if not self.allow_missing:
                raise
            self.missing.append(f"{proto}/{model}/{suite}: {exc}")
            return None

    def protocol_applies_to_pair(self, protocol: str, pair: dict) -> bool:
        return self.store.applies(protocol, pair["old"]) or self.store.applies(protocol, pair["new"])

    def confound_label(self, protocol: str, pair: dict) -> str:
        cm = self.cfg.protocols[protocol].get("confounded_models") or {}
        labels = sorted({cm[m] for m in (pair["old"], pair["new"]) if m in cm and self.store.applies(protocol, m)})
        return "+".join(labels)

    # ---- decision rows --------------------------------------------------
    def _row(self, protocol: str, pair: dict, suite: str) -> dict[str, Any] | None:
        old = self.run_for(protocol, pair["old"], suite)
        new = self.run_for(protocol, pair["new"], suite)
        if old is None or new is None:
            return None
        return self.row_from_runs(protocol, pair, suite, old, new)

    def row_from_runs(self, protocol: str, pair: dict, suite: str, old: Run, new: Run,
                      confound: str | None = None) -> dict[str, Any] | None:
        c = self.cfg
        cmp = compare(old, new, c.stress, c.threshold, c.reps, c.seed, with_ci=self.with_ci)
        if cmp is None:
            return None
        base = compare(old, new, [c.baseline_condition], c.threshold, c.reps, c.seed, with_ci=False)
        drift = compare(old, new, ["schema_drift"], c.threshold, c.reps, c.seed, with_ci=False)
        fault = compare(old, new, ["fault_reporting"], c.threshold, c.reps, c.seed, with_ci=False)
        b_old = base.mean_old if base else None
        b_new = base.mean_new if base else None
        return {
            "protocol": protocol,
            "pair": c.pair_name(pair),
            "old": pair["old"],
            "new": pair["new"],
            "family": pair.get("family", ""),
            "split": pair.get("split", ""),
            "size_changing": c.is_size_changing(pair),
            "f6_sampling_changed": c.f6_changed(pair),
            "suite": suite,
            "old_run": f"{old.protocol}/{old.model}",
            "new_run": f"{new.protocol}/{new.model}",
            "confounding": confound if confound is not None else self.confound_label(protocol, pair),
            "n_records": cmp.n_records,
            "n_tasks": cmp.n_tasks,
            "n_unmatched": max(cmp.n_old, cmp.n_new) - cmp.n_records,
            "stress_old": cmp.mean_old,
            "stress_new": cmp.mean_new,
            "stress_diff": cmp.diff,
            "ci_lo": cmp.ci_lo,
            "ci_hi": cmp.ci_hi,
            "label_point": cmp.label_point,
            "label_ci": cmp.label_ci,
            "baseline_old": b_old,
            "baseline_new": b_new,
            "baseline_diff": base.diff if base else None,
            "drift_diff": drift.diff if drift else None,
            "fault_diff": fault.diff if fault else None,
            "neg_flips": cmp.neg,
            "pos_flips": cmp.pos,
            "fmt_fail_change": cmp.fmt_diff,
            "sem_fail_change": cmp.sem_diff,
            "clean_uninformative": bool(
                b_old is not None and b_old >= c.ceiling and b_new >= c.ceiling
            ),
        }

    def rows(self, protocol: str) -> dict[tuple, dict]:
        """{(pair_name, suite): row} for every pair the protocol applies to."""
        if protocol in self._rows:
            return self._rows[protocol]
        out: dict[tuple, dict] = {}
        for pair in self.cfg.pairs:
            if not self.protocol_applies_to_pair(protocol, pair):
                continue
            for suite in self.cfg.suites:
                row = self._row(protocol, pair, suite)
                if row is not None:
                    out[(row["pair"], suite)] = row
        self._rows[protocol] = out
        return out

    # ---- factor-level view ---------------------------------------------
    def factor_rows(self, factor: str) -> dict[tuple, dict]:
        """Rows for a factor's alternative level. F9-style ``gate`` factors
        reuse the base rows (same data, CI gate instead of point gate)."""
        f = self.cfg.factors[factor]
        if f.get("kind", "run") == "gate":
            return self.rows(self.cfg.base_protocol)
        return self.rows(f["protocol"])

    @staticmethod
    def label_of(row: dict, factor_kind: str = "run") -> str:
        return row["label_ci"] if factor_kind == "gate" else row["label_point"]

    def flip_table(self, factors: list[str] | None = None) -> list[dict[str, Any]]:
        """Long table: every (factor, pair, suite) decision vs D's label."""
        base = self.rows(self.cfg.base_protocol)
        out = []
        for fname in factors or list(self.cfg.factors):
            f = self.cfg.factors[fname]
            kind = f.get("kind", "run")
            if kind == "gate" and not self.with_ci:
                continue
            for key, frow in self.factor_rows(fname).items():
                d = base.get(key)
                if d is None:
                    continue
                d_label = d["label_point"]
                f_label = self.label_of(frow, kind)
                dd = d["stress_diff"]
                df = frow["stress_diff"]
                delta = df - dd
                from_fmt = -(frow["fmt_fail_change"] - d["fmt_fail_change"])
                from_sem = -(frow["sem_fail_change"] - d["sem_fail_change"])
                pair_cfg = next(x for x in self.cfg.pairs if self.cfg.pair_name(x) == d["pair"])
                out.append({
                    "factor": fname,
                    "n_models_changed": self.cfg.n_changed(fname, pair_cfg),
                    "level": f.get("level", ""),
                    "pair": d["pair"], "suite": d["suite"], "family": d["family"], "split": d["split"],
                    "size_changing": d["size_changing"],
                    "f6_sampling_changed": d["f6_sampling_changed"],
                    "confounding": frow["confounding"] if kind == "run" else "",
                    "d_label": d_label, "factor_label": f_label,
                    "flipped": d_label != f_label,
                    "sign_flip": (dd > 0 and df < 0) or (dd < 0 and df > 0),
                    "d_diff": dd, "factor_diff": df, "delta_diff": delta,
                    "delta_from_format": from_fmt, "delta_from_semantic": from_sem,
                    "dominant_bucket": "format" if abs(from_fmt) > abs(from_sem) else "semantic",
                })
        return out
