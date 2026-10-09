"""Locate and load one run's records.

Record format (from upgradecanary/runner.py, which writes it):
  <root>/<protocol folder>/<model>/<suite>/<run_id>/
      parsed_results.jsonl  one row per task x condition x trial:
          task_id, condition, trial_index, drift ({"type",...}|None),
          fault ({"type",...}|None), parsed_call, metrics{...}
      raw_outputs.jsonl     same rows plus prompt/raw_output/truncated
      run_manifest.json     includes run_factors (F1..F6, F11 levels)
      summary.json
Records are matched across runs on
(task_id, condition, drift type, fault type, trial_index), as in
scripts/analyze_version_trials.py.

Score: tool-call conditions use the functional formula recomputed from the
stored component metrics (parse_ok & tool_name_ok & args_intent_match &
args_valid_under_drift & executor_ok), so a rescored file stays consistent;
fault_reporting rows carry only parse_ok/status_ok/no_fabrication/score and
use ``score`` directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Config, _norm

_COMPONENTS = ("parse_ok", "tool_name_ok", "args_intent_match", "args_valid_under_drift", "executor_ok")


class MissingRun(FileNotFoundError):
    pass


def record_key(row: dict[str, Any]) -> tuple:
    return (
        row["task_id"],
        row["condition"],
        (row.get("drift") or {}).get("type"),
        (row.get("fault") or {}).get("type"),
        int(row.get("trial_index", 0)),
    )


def record_score(row: dict[str, Any]) -> float:
    m = row["metrics"]
    if all(k in m for k in _COMPONENTS):
        return 1.0 if all(m[k] for k in _COMPONENTS) else 0.0
    return float(m["score"])


def failure_bucket(row: dict[str, Any], score: float) -> str | None:
    """None for success; "format" when nothing parseable came out; else
    "semantic" (parsed fine but the call/report was wrong)."""
    if score >= 1.0:
        return None
    return "semantic" if row["metrics"].get("parse_ok") else "format"


@dataclass
class Run:
    protocol: str
    model: str
    suite: str
    path: Path
    keys: dict[tuple, tuple[float, str | None]] = field(default_factory=dict)  # key -> (score, bucket)
    strict: dict[tuple, float] = field(default_factory=dict)  # fault_reporting strict_score diagnostic
    manifest: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.keys)


class Store:
    """Caching loader that resolves (protocol, model, suite) -> official folder."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._cache: dict[tuple, Run] = {}

    def _root_for(self, protocol: str) -> Path:
        key = "rescored_root" if self.cfg.protocols[protocol].get("root") == "rescored" else "results_root"
        root = Path(self.cfg.raw[key])
        return root if root.is_absolute() else self.cfg.base_dir / root

    def folder_name(self, protocol: str, model: str) -> str:
        for o in self.cfg.overrides:
            if o["protocol"] == protocol and o["model"] == model:
                return o["folder"]
        return self.cfg.protocols[protocol].get("folder", protocol)

    def suite_dir(self, protocol: str, model: str, suite: str) -> Path:
        folder = self.folder_name(protocol, model)
        rel = _norm(f"{folder}/{model}")
        if rel in self.cfg.audit_only or _norm(f"{rel}/{suite}") in self.cfg.audit_only:
            raise ValueError(f"{rel} is audit-only and must not be used in analysis")
        return self._root_for(protocol) / folder / model / suite

    def applies(self, protocol: str, model: str) -> bool:
        models = self.cfg.protocol_models(protocol)
        return models is None or model in models

    def has(self, protocol: str, model: str, suite: str) -> bool:
        try:
            self._find_run_dir(self.suite_dir(protocol, model, suite))
            return True
        except MissingRun:
            return False

    @staticmethod
    def _find_run_dir(sdir: Path) -> Path:
        if (sdir / "parsed_results.jsonl").exists():
            return sdir
        cands = (
            sorted(d for d in sdir.glob("*") if d.is_dir() and (d / "parsed_results.jsonl").exists())
            if sdir.exists() else []
        )
        if not cands:
            raise MissingRun(f"no parsed_results.jsonl under {sdir}")
        if len(cands) > 1:
            raise ValueError(f"ambiguous: {len(cands)} run directories under {sdir}: {[c.name for c in cands]}")
        return cands[0]

    def get(self, protocol: str, model: str, suite: str) -> Run:
        ck = (protocol, model, suite)
        if ck in self._cache:
            return self._cache[ck]
        run_dir = self._find_run_dir(self.suite_dir(protocol, model, suite))
        run = Run(protocol, model, suite, run_dir)
        with open(run_dir / "parsed_results.jsonl", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                k = record_key(row)
                s = record_score(row)
                run.keys[k] = (s, failure_bucket(row, s))
                if row["condition"] == "fault_reporting" and "strict_score" in row["metrics"]:
                    run.strict[k] = float(row["metrics"]["strict_score"])
        mpath = run_dir / "run_manifest.json"
        if mpath.exists():
            run.manifest = json.loads(mpath.read_text(encoding="utf-8"))
        self._check(run)
        self._cache[ck] = run
        return run

    def _check(self, run: Run) -> None:
        p = self.cfg.protocols[run.protocol]
        expected = int(p.get("expected_records", self.cfg.expected_records))
        if len(run) != expected:
            run.warnings.append(f"{len(run)} records, expected {expected}")
        expect = p.get("expect_manifest") or {}
        factors = run.manifest.get("run_factors", {})
        for k, v in expect.items():
            if factors.get(k) != v:
                run.warnings.append(f"manifest run_factors[{k}]={factors.get(k)!r}, expected {v!r}")

    def truncation_rate(self, run: Run) -> float | None:
        """Share of records with truncated=True, from raw_outputs.jsonl if present."""
        path = run.path / "raw_outputs.jsonl"
        if not path.exists():
            return None
        n = t = 0
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                n += 1
                t += 1 if row.get("truncated") else 0
        return t / n if n else None

    def all_warnings(self) -> list[str]:
        return [f"{r.protocol}/{r.model}/{r.suite}: {w}" for r in self._cache.values() for w in r.warnings]
