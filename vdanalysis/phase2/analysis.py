"""Phase 2 version of the decision engine.

``Phase2Analysis`` is the Phase 1 ``Analysis`` with four additions, none of
which changes what the Phase 1 code does when they are switched off (which is
exactly what mode ``phase1`` does):

* runs come from the merged store (``merge.py``);
* **F6 trimming** (PLAN_PHASE2.md W1): for the models whose F6 sampling equals
  D's, the F6 run is the D run;
* **view_of** protocols (F10 = D's greedy trial) need no files;
* **same-hardware rule** (section 5): a factor run on a given hardware is
  compared against a baseline run on that hardware (F5 / R_F5 of the Kaggle
  models against the Kaggle D / R baselines);
* **views**: the same analysis can be run on the greedy trial only, on the
  sampled trials only, or on a subset of tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..engine import Analysis
from .config import Phase2Config
from .merge import MergedRun, MergedStore


@dataclass(frozen=True)
class ViewSpec:
    trials: str = "all"                       # all | greedy | sampled
    tasks: frozenset | None = None            # restrict to these task ids

    @property
    def name(self) -> str:
        return self.trials if self.tasks is None else f"{self.trials}+tasks"


class Phase2Analysis(Analysis):
    def __init__(self, cfg: Phase2Config, store: MergedStore | None = None, with_ci: bool = True,
                 allow_missing: bool = False, view: ViewSpec | None = None):
        super().__init__(cfg, store or MergedStore(cfg), with_ci=with_ci, allow_missing=allow_missing)
        self.cfg: Phase2Config = cfg
        self.view = view or ViewSpec()
        self._views: dict[tuple, MergedRun] = {}

    def with_view(self, view: ViewSpec) -> "Phase2Analysis":
        """Same store (records are loaded once), different view."""
        return Phase2Analysis(self.cfg, self.store, self.with_ci, self.allow_missing, view)

    # ---- run access ------------------------------------------------------
    def _apply_view(self, run: MergedRun | None, extra: str = "all") -> MergedRun | None:
        if run is None:
            return None
        trials = self.view.trials
        if extra == "greedy":                    # protocol-level view (F10): greedy only
            if trials == "sampled":
                raise ValueError("a 'greedy only' protocol cannot be viewed as sampled-only")
            trials = "greedy"
        if trials == "all" and self.view.tasks is None:
            return run
        key = (id(run), trials, self.view.tasks)
        if key not in self._views:
            self._views[key] = run.view(trials, self.view.tasks)
        return self._views[key]

    def run_for(self, protocol: str, model: str, suite: str):
        spec = self.cfg.protocol_p2(protocol) if self.cfg.mode == "phase2" else {}
        if spec.get("view_of"):
            base = spec["view_of"]
            run = Analysis.run_for(self, base, model, suite)
            return self._apply_view(run, spec.get("trials", "all"))
        trim = self.cfg.p2.get("f6_trim") if self.cfg.mode == "phase2" else None
        if trim and protocol == trim["protocol"] and model in self.cfg.f6_trim_models():
            protocol = trim["base"]
        return self._apply_view(Analysis.run_for(self, protocol, model, suite))

    # ---- same-hardware baselines ------------------------------------------
    def baseline_protocol_for(self, factor_protocol: str, pair: dict, default: str | None = None) -> str:
        """The protocol whose label a factor run is compared with. D (or the
        config's base protocol; ``default`` for the R side) unless the
        same-hardware rule names another."""
        default = default or self.cfg.base_protocol
        sh = self.cfg.same_hardware_for(factor_protocol)
        if not sh:
            return default
        on = [m in sh["models"] for m in (pair["old"], pair["new"])]
        if all(on):
            return sh["baseline"]
        if any(on):
            raise ValueError(f"pair {self.cfg.pair_name(pair)} mixes hardware under {factor_protocol}: "
                             "same-hardware comparison is not defined for it")
        return default

    def flip_table(self, factors: list[str] | None = None) -> list[dict[str, Any]]:
        """Phase 1's flip table, with each factor run compared against the
        baseline on its own hardware. Identical to ``Analysis.flip_table``
        when no same-hardware rule applies."""
        out = []
        for fname in factors or list(self.cfg.factors):
            f = self.cfg.factors[fname]
            kind = f.get("kind", "run")
            if kind == "gate" and not self.with_ci:
                continue
            for key, frow in self.factor_rows(fname).items():
                pair_cfg = next(x for x in self.cfg.pairs if self.cfg.pair_name(x) == frow["pair"])
                bproto = (self.cfg.base_protocol if kind == "gate"
                          else self.baseline_protocol_for(f["protocol"], pair_cfg))
                d = self.rows(bproto).get(key)
                if d is None:
                    continue
                d_label = d["label_point"]
                f_label = self.label_of(frow, kind)
                dd = d["stress_diff"]
                df = frow["stress_diff"]
                delta = df - dd
                from_fmt = -(frow["fmt_fail_change"] - d["fmt_fail_change"])
                from_sem = -(frow["sem_fail_change"] - d["sem_fail_change"])
                row = {
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
                }
                if self.cfg.mode == "phase2":
                    row["baseline_protocol"] = bproto
                out.append(row)
        return out
