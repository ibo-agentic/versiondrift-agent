"""Config loading and validation.

One YAML file (configs/analysis_official_folders.yaml for the real study)
declares the models, pairs, protocol -> folder mapping, the official-folder
overrides from DEVIATIONS.md, controls, and the robust-protocol (R) names.
Nothing about folders or pairs is hard-coded in the analysis code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED_KEYS = (
    "results_root", "rescored_root", "suites", "expected_records_per_run",
    "stress_conditions", "baseline_condition", "gate", "models", "pairs",
    "base_protocol", "protocols", "factors",
)
FORBIDDEN_WRITE_DIRS = ("results", "results_smoke", "results_v2")


class Config:
    def __init__(self, raw: dict[str, Any], base_dir: Path | None = None):
        missing = [k for k in REQUIRED_KEYS if k not in raw]
        if missing:
            raise ValueError(f"config is missing required keys: {missing}")
        self.raw = raw
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.suites: list[str] = list(raw["suites"])
        self.expected_records = int(raw["expected_records_per_run"])
        self.stress: tuple[str, ...] = tuple(raw["stress_conditions"])
        self.baseline_condition: str = raw["baseline_condition"]
        self.threshold = float(raw["gate"]["threshold"])
        self.reps = int(raw["gate"]["reps"])
        self.seed = int(raw["gate"]["seed"])
        self.models: dict[str, dict] = raw["models"]
        self.pairs: list[dict] = raw["pairs"]
        self.base_protocol: str = raw["base_protocol"]
        self.protocols: dict[str, dict] = raw["protocols"]
        self.factors: dict[str, dict] = raw["factors"]
        self.groups: dict[str, list[str]] = raw.get("factor_groups", {})
        self.overrides: list[dict] = raw.get("overrides", [])
        self.audit_only: list[str] = [_norm(p) for p in raw.get("audit_only_folders", [])]
        self.sampling_changed: set[str] = set(raw.get("sampling_changed_models", []))
        self.controls: list[dict] = raw.get("controls", [])
        self.robust: dict[str, Any] = raw.get("robust", {})
        self.ceiling = float(raw.get("ceiling_threshold", 0.97))
        self.truncation_limit = float(raw.get("truncation_limit", 0.02))
        self._validate()

    def _validate(self) -> None:
        for p in self.pairs:
            for side in ("old", "new"):
                if p[side] not in self.models:
                    raise ValueError(f"pair {p} references unknown model {p[side]!r}")
        if self.base_protocol not in self.protocols:
            raise ValueError("base_protocol must be listed under protocols")
        for fname, f in self.factors.items():
            if f.get("kind", "run") == "run" and f["protocol"] not in self.protocols:
                raise ValueError(f"factor {fname} uses unknown protocol {f['protocol']!r}")
        for o in self.overrides:
            if o["protocol"] not in self.protocols:
                raise ValueError(f"override for unknown protocol: {o}")

    def pair_name(self, p: dict) -> str:
        return f"{p['old']}->{p['new']}"

    def is_size_changing(self, p: dict) -> bool:
        return bool(p.get("size_changing", False))

    def f6_changed(self, p: dict) -> bool:
        return p["old"] in self.sampling_changed or p["new"] in self.sampling_changed

    def protocol_models(self, protocol: str) -> list[str] | None:
        return self.protocols[protocol].get("models")


def _norm(path: str) -> str:
    return str(path).replace("\\", "/").strip("/")


def load_config(path: str | Path, results_root: str | Path | None = None) -> Config:
    path = Path(path)
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if results_root is not None:
        raw["results_root"] = str(results_root)
    return Config(raw, base_dir=path.parent)


def assert_safe_output_dir(out_dir: str | Path) -> Path:
    """Refuse to write anywhere inside the protected results folders."""
    out = Path(out_dir).resolve()
    for part in out.parts:
        if part in FORBIDDEN_WRITE_DIRS:
            raise ValueError(f"refusing to write inside protected folder {part!r}: {out}")
    return out
