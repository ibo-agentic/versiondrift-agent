"""Phase 2 configuration (PLAN_PHASE2.md).

A Phase 2 config is the official Phase 1 config plus a ``phase2:`` block.
It is written as a small YAML file that says ``extends: <parent.yaml>``; the
parent is loaded first and the child's top-level keys are laid over it (dict
values are merged one level deep, everything else is replaced). Nothing about
folders, trial layouts, model sets or thresholds is hard-coded in Python.

The ``phase2`` block (all keys optional, shown with their meaning):

    mode: phase2 | phase1         phase1 = reproduce Phase 1 exactly (regression check)
    roots: {name: path}           named result roots, relative to the config file
    n_trials: 10                  expected trials per (task, condition); null = infer
    model_sets: {name: [models]}  reusable lists, referred to by name below
    default_parts: [part, ...]    parts for any protocol without its own entry
    protocols: {PROTO: {parts: [...], seed_base: 1234, view_of: D, trials: greedy}}
    f6_trim: {protocol: F6, base: D, models: <set>}
    same_hardware: {F5: {baseline: D_KAGGLE, models: <set>}, ...}
    hypotheses: {p1_threshold: 0.2, ...}
    controls: [...]               control definitions (kinds: aa, aa2, pc)

A *part* is one folder of records that belongs to a run. Records of all parts
of a (protocol, model, suite) are merged. A part is
``{root: <root name>, folder: <folder, default = protocol folder>,
trial_offset: <added to the part's trial_index>, overrides: <apply the
official-folder overrides of the parent config>, models/exclude_models: <set
name or list>}``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..config import Config


@dataclass(frozen=True)
class PartSpec:
    root: str
    folder: str | None = None
    trial_offset: int = 0
    overrides: bool = True
    require_prompts: bool | None = None  # None = True, except for rescored roots

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PartSpec":
        return cls(root=d["root"], folder=d.get("folder"), trial_offset=int(d.get("trial_offset", 0)),
                   overrides=bool(d.get("overrides", True)), require_prompts=d.get("require_prompts"))


def deep_merge_config(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    """Child top-level keys override the parent's; dict values merge one level deep."""
    out = copy.deepcopy(parent)
    for k, v in child.items():
        if k == "extends":
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            merged = dict(out[k])
            merged.update(copy.deepcopy(v))
            out[k] = merged
        else:
            out[k] = copy.deepcopy(v)
    return out


def _load_raw(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    parent = raw.get("extends")
    if parent:
        ppath = Path(parent)
        if not ppath.is_absolute():
            ppath = path.parent / ppath
        raw = deep_merge_config(_load_raw(ppath), raw)
    return raw


BUILTIN_ROOTS = ("results_root", "rescored_root", "auto")


class Phase2Config(Config):
    def __init__(self, raw: dict[str, Any], base_dir: Path | None = None):
        super().__init__(raw, base_dir)
        p2 = raw.get("phase2") or {}
        self.p2: dict[str, Any] = p2
        self.mode: str = p2.get("mode", "phase2")
        if self.mode not in ("phase1", "phase2"):
            raise ValueError(f"phase2.mode must be phase1 or phase2, got {self.mode!r}")
        self.n_trials: int | None = p2.get("n_trials")
        self.model_sets: dict[str, list[str]] = {k: list(v) for k, v in (p2.get("model_sets") or {}).items()}
        self._validate_p2()

    # ---- validation ------------------------------------------------------
    def _validate_p2(self) -> None:
        roots = self.p2.get("roots") or {}
        for part in self._all_part_dicts():
            if part["root"] not in roots and part["root"] not in BUILTIN_ROOTS:
                raise ValueError(f"part {part} uses unknown root {part['root']!r}; roots: {list(roots)}")
            for key in ("models", "exclude_models"):
                v = part.get(key)
                if isinstance(v, str) and v not in self.model_sets:
                    raise ValueError(f"part {part} refers to unknown model set {v!r}")
        for name, spec in (self.p2.get("same_hardware") or {}).items():
            if spec["baseline"] not in self.protocols:
                raise ValueError(f"same_hardware[{name}] baseline {spec['baseline']!r} is not a protocol")
            self.resolve_models(spec["models"])
        trim = self.p2.get("f6_trim")
        if trim:
            if trim["protocol"] not in self.protocols or trim["base"] not in self.protocols:
                raise ValueError(f"f6_trim refers to unknown protocols: {trim}")
            self.resolve_models(trim["models"])

    def _all_part_dicts(self) -> list[dict[str, Any]]:
        out = list(self.p2.get("default_parts") or [])
        for spec in (self.p2.get("protocols") or {}).values():
            out += list(spec.get("parts") or [])
        return out

    # ---- helpers ---------------------------------------------------------
    def resolve_models(self, ref: Any) -> set[str]:
        """A model-set reference: a set name, or an explicit list."""
        if ref is None:
            return set()
        if isinstance(ref, str):
            if ref not in self.model_sets:
                raise ValueError(f"unknown model set {ref!r}")
            return set(self.model_sets[ref])
        unknown = [m for m in ref if m not in self.models]
        if unknown:
            raise ValueError(f"unknown models in {ref}: {unknown}")
        return set(ref)

    def root_path(self, name: str) -> Path:
        if name in ("results_root", "rescored_root"):
            raw = self.raw[name]
        else:
            raw = self.p2["roots"][name]
        p = Path(raw)
        return p if p.is_absolute() else self.base_dir / p

    def protocol_p2(self, protocol: str) -> dict[str, Any]:
        return (self.p2.get("protocols") or {}).get(protocol, {})

    def parts_for(self, protocol: str, model: str) -> list[PartSpec]:
        """The parts that make up (protocol, model). Entries are filtered by
        their ``models`` / ``exclude_models``; the first protocol-specific list
        wins, else ``default_parts``, else one part in the parent results root."""
        spec = self.protocol_p2(protocol)
        entries = spec.get("parts")
        if entries is None:
            entries = self.p2.get("default_parts")
        if entries is None:
            entries = [{"root": "auto"}]
        auto = "rescored_root" if self.protocols[protocol].get("root") == "rescored" else "results_root"
        out = []
        for e in entries:
            if "models" in e and model not in self.resolve_models(e["models"]):
                continue
            if "exclude_models" in e and model in self.resolve_models(e["exclude_models"]):
                continue
            e = dict(e, root=auto if e["root"] == "auto" else e["root"])
            out.append(PartSpec.from_dict(e))
        return out

    def seed_base(self, protocol: str) -> int | None:
        """Trial-seed of the first trial of a protocol (None = do not check seeds)."""
        spec = self.protocol_p2(protocol)
        if "seed_base" in spec:
            return None if spec["seed_base"] is None else int(spec["seed_base"])
        v = self.p2.get("seed_base")
        return None if v is None else int(v)

    def same_hardware_for(self, protocol: str) -> dict[str, Any] | None:
        if self.mode == "phase1":
            return None
        spec = (self.p2.get("same_hardware") or {}).get(protocol)
        if not spec:
            return None
        return {"baseline": spec["baseline"], "models": self.resolve_models(spec["models"])}

    def f6_trim_models(self) -> set[str]:
        trim = self.p2.get("f6_trim")
        if not trim or self.mode == "phase1":
            return set()
        return self.resolve_models(trim["models"])

    def threshold_p(self, name: str, default: Any) -> Any:
        return (self.p2.get("hypotheses") or {}).get(name, default)


def load_phase2_config(path: str | Path, mode: str | None = None) -> Phase2Config:
    path = Path(path)
    raw = _load_raw(path)
    if mode is not None:
        raw.setdefault("phase2", {})["mode"] = mode
    return Phase2Config(raw, base_dir=path.parent)
