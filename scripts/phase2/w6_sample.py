"""W6 human labels: the sampling frame, the allocation and the draw (PLAN_PHASE2.md W6; DEVIATIONS.md 2026-11-14, entry l).

    python -m scripts.phase2.w6_sample --config configs/analysis_phase2.yaml --out w6_labels/sample.json

Frame: D and R main runs, stress conditions only, all suites and models, all 10 trials (Phase 1 trials 0-2 from
results_v2 + Phase 2 trials 3-9 from results_v3, merged the way the analysis config merges them). Strata: suite x
verdict (pass/fail, ``vdanalysis.loader.record_score``). 200 records, 33/33/33/33/34/34 (the two largest strata get
34), simple random sampling inside each stratum with seed 20261020. A stratum that is short is taken whole and the
shortfall is topped up from the largest stratum. Nothing here reads the model output text; the labeling files are
built from the draw by a separate step.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from vdanalysis.loader import MissingRun, record_score  # noqa: E402
from vdanalysis.phase2.config import load_phase2_config  # noqa: E402
from vdanalysis.phase2.merge import MergedStore  # noqa: E402

SEED = 20261020
TOTAL = 200
PROTOCOLS = ("D", "R")
VERDICTS = ("fail", "pass")


@dataclass(frozen=True)
class Cand:
    """One record in the frame. ``part`` is the run folder, ``line`` the 0-based line in parsed_results.jsonl
    (and raw_outputs.jsonl); ``trial`` is the merged trial index 0-9."""
    protocol: str
    model: str
    suite: str
    condition: str
    task_id: str
    trial: int
    verdict: str
    part: str
    line: int

    def sort_key(self) -> tuple:
        return (self.protocol, self.model, self.suite, self.condition, self.task_id, self.trial, self.part)

    @property
    def stratum(self) -> tuple[str, str]:
        return (self.suite, self.verdict)


def build_frame(cfg, protocols=PROTOCOLS) -> tuple[list[Cand], list[str]]:
    """Every stress-condition record of the D / R main runs. Returns (candidates, notes)."""
    store = MergedStore(cfg)
    stress = set(cfg.stress)
    out: list[Cand] = []
    notes: list[str] = []
    n_runs = 0
    for protocol in protocols:
        for model in cfg.models:
            for suite in cfg.suites:
                try:
                    parts = store.part_dirs(protocol, model, suite)
                    n_runs += 1
                except MissingRun as exc:
                    notes.append(f"skipped {protocol}/{model}/{suite}: {exc}")
                    continue
                for d, spec in parts:
                    run_dir = store._find_run_dir(d)
                    with open(run_dir / "parsed_results.jsonl", encoding="utf-8") as fh:
                        for line_no, line in enumerate(fh):
                            if not line.strip():
                                continue
                            row = json.loads(line)
                            if row["condition"] not in stress:
                                continue
                            out.append(Cand(protocol, model, suite, row["condition"], row["task_id"],
                                            int(row.get("trial_index", 0)) + spec.trial_offset,
                                            "pass" if record_score(row) >= 1.0 else "fail",
                                            _rel(run_dir), line_no))
    notes.append(f"{n_runs} (protocol, model, suite) runs read")
    return out, notes


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def allocate(sizes: dict[tuple, int], total: int = TOTAL) -> tuple[dict[tuple, int], list[str]]:
    """Per-stratum number to draw. Base = total // n_strata; the ``total - base * n`` leftover records go one each to
    the largest strata (ties by stratum name). A stratum smaller than its quota gives all it has; the shortfall is
    added to the largest strata that still have records (largest first). Returns (counts, log lines)."""
    strata = sorted(sizes)
    base, extra = divmod(total, len(strata))
    by_size = sorted(strata, key=lambda s: (-sizes[s], s))
    quota = {s: base for s in strata}
    for s in by_size[:extra]:
        quota[s] += 1
    log = [f"quota {s}: {quota[s]} (frame {sizes[s]})" for s in strata]
    counts = {s: min(quota[s], sizes[s]) for s in strata}
    short = total - sum(counts.values())
    if short > 0:
        log.append(f"shortfall of {short}: " + ", ".join(f"{s} has {sizes[s]} < quota {quota[s]}" for s in strata
                                                      if sizes[s] < quota[s]))
    for s in by_size:
        if short <= 0:
            break
        room = sizes[s] - counts[s]
        take = min(room, short)
        if take > 0:
            counts[s] += take
            short -= take
            log.append(f"top-up: {take} more from {s}")
    if short > 0:
        raise ValueError(f"the frame has fewer than {total} records")
    return counts, log


def draw(cands: list[Cand], seed: int = SEED, total: int = TOTAL) -> tuple[list[Cand], dict]:
    """Stratified draw. Candidates are sorted first, strata are visited in sorted order, one generator for all."""
    groups: dict[tuple, list[Cand]] = {}
    for c in sorted(cands, key=Cand.sort_key):
        groups.setdefault(c.stratum, []).append(c)
    all_strata = [(su, v) for su in sorted({c.suite for c in cands}) for v in VERDICTS]
    sizes = {s: len(groups.get(s, [])) for s in all_strata}
    counts, log = allocate(sizes, total)
    rng = np.random.default_rng(seed)
    picked: list[Cand] = []
    for s in all_strata:
        k = counts[s]
        if k:
            idx = np.sort(rng.choice(len(groups[s]), size=k, replace=False))
            picked.extend(groups[s][int(i)] for i in idx)
    info = {"seed": seed, "total": len(picked), "frame_size": len(cands),
            "strata": [{"suite": s[0], "verdict": s[1], "frame": sizes[s], "drawn": counts[s]} for s in all_strata],
            "log": log}
    return picked, info


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/analysis_phase2.yaml")
    ap.add_argument("--out", required=True, help="JSON file for the draw (record locators + allocation log)")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args(argv)
    cfg = load_phase2_config(args.config)
    cands, notes = build_frame(cfg)
    picked, info = draw(cands, args.seed)
    info["notes"] = notes
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"info": info, "records": [asdict(c) for c in picked]}, indent=1), encoding="utf-8")
    print(f"drew {len(picked)} records from a frame of {len(cands)}; wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
