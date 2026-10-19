"""Merging the parts of a run (PLAN_PHASE2.md section 2 and W1/W3).

A Phase 2 run for one (protocol, model, suite) can be stored in several
folders ("parts"): Phase 1's trials 0-2 under results_v2 plus the new trials
under results_v3, or the original tasks plus the added tasks (W3). This module
reads all parts, puts them on one trial axis and checks that they really
belong together:

* no duplicate (task, condition, trial);
* every record of a (task, condition) carries the same prompt, across trials
  and across parts (byte identity is checked through the stored SHA-256 of the
  prompt text; a part without raw_outputs.jsonl is an error unless it is
  explicitly allowed to have none);
* the same drift type and fault type for a (task, condition) in every part;
* the same temperature for a given trial index in every part;
* (optional) the trial seed recorded in each row equals ``seed_base`` plus the
  merged trial index, so a part with a wrong ``trial_offset`` cannot slip in.

The expected size of a run is never hard-coded. A run is complete when every
(task, condition) it contains has every expected trial; the expected trial
count comes from the config (or is inferred). Gaps are warnings.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..loader import MissingRun, Run, Store, failure_bucket, record_key, record_score
from .config import PartSpec, Phase2Config


class MergeError(ValueError):
    """Parts that cannot be merged safely."""


def _sha(row: dict[str, Any]) -> str | None:
    if row.get("prompt_sha256"):
        return row["prompt_sha256"]
    if row.get("prompt") is not None:
        return hashlib.sha256(row["prompt"].encode("utf-8")).hexdigest()
    return None


@dataclass
class MergedRun(Run):
    parts: list[Path] = field(default_factory=list)
    prompts: dict[tuple, str] = field(default_factory=dict)          # (task, condition) -> prompt sha256
    trial_info: dict[int, tuple] = field(default_factory=dict)       # merged trial -> (temperature, seed)
    drift_fault: dict[tuple, tuple] = field(default_factory=dict)    # (task, condition) -> (drift type, fault type)

    # ---- trial / task bookkeeping ------------------------------------
    @property
    def trials(self) -> list[int]:
        return sorted({k[4] for k in self.keys})

    @property
    def tasks(self) -> set[str]:
        return {k[0] for k in self.keys}

    @property
    def conditions(self) -> set[str]:
        return {k[1] for k in self.keys}

    def greedy_trials(self) -> set[int]:
        out = set()
        for t in self.trials:
            temp = self.trial_info.get(t, (None, None))[0]
            if temp == 0.0 or (temp is None and t == 0):
                out.add(t)
        return out

    def view(self, trials: str = "all", tasks: Iterable[str] | None = None) -> "MergedRun":
        """A filtered copy: ``trials`` is all | greedy | sampled; ``tasks`` an optional task-id set."""
        if trials not in ("all", "greedy", "sampled"):
            raise ValueError(f"unknown trial view {trials!r}")
        if trials == "all" and tasks is None:
            return self
        greedy = self.greedy_trials()
        task_set = None if tasks is None else set(tasks)

        def keep(k: tuple) -> bool:
            if trials == "greedy" and k[4] not in greedy:
                return False
            if trials == "sampled" and k[4] in greedy:
                return False
            return task_set is None or k[0] in task_set

        keys = {k: v for k, v in self.keys.items() if keep(k)}
        kept_tasks = {k[0] for k in keys}
        kept_trials = {k[4] for k in keys}
        return MergedRun(
            protocol=self.protocol, model=self.model, suite=self.suite, path=self.path, keys=keys,
            strict={k: v for k, v in self.strict.items() if k in keys}, manifest=self.manifest,
            warnings=list(self.warnings), parts=list(self.parts),
            prompts={k: v for k, v in self.prompts.items() if k[0] in kept_tasks},
            trial_info={t: i for t, i in self.trial_info.items() if t in kept_trials},
            drift_fault={k: v for k, v in self.drift_fault.items() if k[0] in kept_tasks},
        )


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def merge_parts(protocol: str, model: str, suite: str, parts: list[tuple[Path, PartSpec, bool]],
                seed_base: int | None = None, expected_trials: int | None = None,
                expect_manifest: dict[str, Any] | None = None) -> MergedRun:
    """``parts`` = [(run directory, part spec, prompts required)]."""
    tag = f"{protocol}/{model}/{suite}"
    run = MergedRun(protocol, model, suite, parts[0][0], parts=[p[0] for p in parts])
    seen: dict[tuple, Path] = {}               # (task, cond, merged trial) -> part
    prompt_seen: dict[tuple, str] = {}         # (task, cond) -> sha
    temps: dict[int, set] = {}                 # merged trial -> temperatures
    seeds: dict[int, set] = {}
    manifests = []
    for run_dir, spec, need_prompts in parts:
        raw_sha: dict[tuple, str | None] = {}
        raw_path = run_dir / "raw_outputs.jsonl"
        if raw_path.exists():
            for r in _read_jsonl(raw_path):
                raw_sha[(r["task_id"], r["condition"], int(r.get("trial_index", 0)))] = _sha(r)
        elif need_prompts:
            raise MergeError(f"{tag}: {run_dir} has no raw_outputs.jsonl, cannot verify prompts")
        for row in _read_jsonl(run_dir / "parsed_results.jsonl"):
            t_in = int(row.get("trial_index", 0))
            t = t_in + spec.trial_offset
            task, cond = row["task_id"], row["condition"]
            tc = (task, cond)
            if (task, cond, t) in seen:
                raise MergeError(f"{tag}: duplicate record (task={task}, condition={cond}, trial={t}) in "
                                 f"{seen[(task, cond, t)]} and {run_dir}")
            seen[(task, cond, t)] = run_dir
            if seed_base is not None and row.get("seed") is not None and int(row["seed"]) != seed_base + t:
                raise MergeError(f"{tag}: {run_dir} trial {t_in}(+{spec.trial_offset}) has seed {row['seed']}, "
                                 f"expected {seed_base + t}; check trial_offset / seed_base")
            dt = (row.get("drift") or {}).get("type")
            ft = (row.get("fault") or {}).get("type")
            if run.drift_fault.setdefault(tc, (dt, ft)) != (dt, ft):
                raise MergeError(f"{tag}: drift/fault type of {tc} differs between parts "
                                 f"({run.drift_fault[tc]} vs {(dt, ft)})")
            sha = raw_sha.get((task, cond, t_in))
            if sha is None:
                if need_prompts:
                    raise MergeError(f"{tag}: {run_dir} has no prompt for (task={task}, condition={cond}, "
                                     f"trial={t_in})")
            elif prompt_seen.setdefault(tc, sha) != sha:
                raise MergeError(f"{tag}: prompts for {tc} are not byte-identical across trials/parts")
            temps.setdefault(t, set()).add(row.get("temperature"))
            seeds.setdefault(t, set()).add(row.get("seed"))
            k = (task, cond, dt, ft, t)
            s = record_score(row)
            run.keys[k] = (s, failure_bucket(row, s))
            if cond == "fault_reporting" and "strict_score" in row["metrics"]:
                run.strict[k] = float(row["metrics"]["strict_score"])
        mp = run_dir / "run_manifest.json"
        if mp.exists():
            manifests.append(json.loads(mp.read_text(encoding="utf-8")))
    run.prompts = prompt_seen
    for t, tv in temps.items():
        if len(tv) != 1:
            raise MergeError(f"{tag}: trial {t} has several temperatures across tasks/parts: {sorted(map(str, tv))}")
        sv = seeds[t]
        run.trial_info[t] = (next(iter(tv)), next(iter(sv)) if len(sv) == 1 else None)
    run.manifest = manifests[0] if manifests else {}
    _check_complete(run, expected_trials)
    for k, v in (expect_manifest or {}).items():
        for m in manifests:
            got = m.get("run_factors", {}).get(k)
            if got != v:
                run.warnings.append(f"manifest run_factors[{k}]={got!r}, expected {v!r}")
    return run


def _check_complete(run: MergedRun, expected_trials: int | None) -> None:
    trials = run.trials
    want = set(range(expected_trials)) if expected_trials else (set(range(trials[-1] + 1)) if trials else set())
    if not trials:
        run.warnings.append("no records")
        return
    per_tc: dict[tuple, set] = {}
    for k in run.keys:
        per_tc.setdefault((k[0], k[1]), set()).add(k[4])
    bad = {tc: want - ts for tc, ts in per_tc.items() if want - ts}
    extra = {tc: ts - want for tc, ts in per_tc.items() if ts - want}
    if bad:
        run.warnings.append(f"{len(bad)} of {len(per_tc)} (task, condition) groups miss trials "
                            f"(e.g. {next(iter(bad.items()))})")
    if extra:
        run.warnings.append(f"{len(extra)} (task, condition) groups have trials beyond the expected {len(want)}")


class MergedStore(Store):
    """Loader that resolves (protocol, model, suite) to merged runs."""

    def __init__(self, cfg: Phase2Config):
        super().__init__(cfg)
        self.cfg: Phase2Config = cfg

    def _part_dir(self, protocol: str, model: str, suite: str, spec: PartSpec) -> Path:
        if spec.overrides:
            folder = spec.folder or self.folder_name(protocol, model)
        else:
            folder = spec.folder or self.cfg.protocols[protocol].get("folder", protocol)
        rel = f"{folder}/{model}".strip("/")
        if rel in self.cfg.audit_only or f"{rel}/{suite}" in self.cfg.audit_only:
            raise ValueError(f"{rel} is audit-only and must not be used in analysis")
        return self.cfg.root_path(spec.root) / folder / model / suite

    def part_dirs(self, protocol: str, model: str, suite: str) -> list[tuple[Path, PartSpec]]:
        specs = self.cfg.parts_for(protocol, model)
        if not specs:
            raise MissingRun(f"{protocol}/{model}/{suite}: no parts configured for this model")
        return [(self._part_dir(protocol, model, suite, s), s) for s in specs]

    def has(self, protocol: str, model: str, suite: str) -> bool:
        try:
            for d, _ in self.part_dirs(protocol, model, suite):
                self._find_run_dir(d)
            return True
        except MissingRun:
            return False

    def expected_trials(self, protocol: str) -> int | None:
        spec = self.cfg.protocol_p2(protocol)
        if "n_trials" in spec:
            return spec["n_trials"]
        return self.cfg.n_trials

    def get(self, protocol: str, model: str, suite: str) -> MergedRun:
        ck = (protocol, model, suite)
        if ck in self._cache:
            return self._cache[ck]
        resolved = []
        for d, spec in self.part_dirs(protocol, model, suite):
            run_dir = self._find_run_dir(d)
            need = spec.require_prompts
            if need is None:
                need = not spec.root.startswith("rescored")
            resolved.append((run_dir, spec, need))
        run = merge_parts(protocol, model, suite, resolved, self.cfg.seed_base(protocol),
                          self.expected_trials(protocol),
                          self.cfg.protocols[protocol].get("expect_manifest"))
        self._cache[ck] = run
        return run

    def truncation_rate(self, run: Run) -> float | None:
        paths = [p / "raw_outputs.jsonl" for p in getattr(run, "parts", [run.path])]
        if not all(p.exists() for p in paths):
            return None
        n = t = 0
        for p in paths:
            for row in _read_jsonl(p):
                n += 1
                t += 1 if row.get("truncated") else 0
        return t / n if n else None
