"""Cluster bootstrap for suites with repeated prompts (PLAN_PHASE2.md section 4, descriptive).

The synthetic generator is deterministic with small value pools: the 100 original tasks hold only 54 distinct
baseline prompts, so tasks that share a baseline prompt are not independent draws. For such suites every
decision is also reported with a bootstrap that resamples *clusters* of tasks, a cluster being the tasks that
share the same baseline prompt. Descriptive only: the gate (labels, thresholds, the task-level bootstrap in the
main tables) is unchanged; ``label_cluster_ci`` is a second reading next to it, never a replacement.

With every task its own cluster the result equals the ordinary task-level bootstrap exactly (same draws), which
the tests check.
"""

from __future__ import annotations

from typing import Any, Callable

from upgradecanary.gates import ci_gate, point_gate

from ..loader import Run
from ..stats import bootstrap_ci
from .analysis import Phase2Analysis
from .controls2 import EXPECTED


def baseline_clusters(run: Run, baseline_condition: str) -> dict[str, str]:
    """task -> cluster id (the baseline prompt hash) for one run."""
    prompts = getattr(run, "prompts", None)
    if not prompts:
        raise ValueError(f"{run.protocol}/{run.model}/{run.suite}: no prompts loaded, cannot form prompt clusters")
    return {task: sha for (task, cond), sha in prompts.items() if cond == baseline_condition}


def _partition(m: dict[str, str]) -> frozenset:
    groups: dict[str, list[str]] = {}
    for t, c in m.items():
        groups.setdefault(c, []).append(t)
    return frozenset(frozenset(v) for v in groups.values())


def cluster_map(an: Phase2Analysis, suite: str) -> dict[str, str]:
    """task -> cluster id for ``suite``, from the base protocol's baseline prompts. All models must agree on which
    tasks share a prompt (they see byte-identical prompts), otherwise this raises."""
    cfg = an.cfg
    best: dict[str, str] | None = None
    sig = None
    for model in cfg.models:
        run = an.run_for(cfg.base_protocol, model, suite)
        if run is None:
            continue
        m = baseline_clusters(run, cfg.baseline_condition)
        if sig is None:
            best, sig = m, _partition(m)
        elif _partition(m) != sig:
            raise ValueError(f"{suite}: models disagree on which tasks share a baseline prompt ({model})")
    if best is None:
        raise ValueError(f"{suite}: no {cfg.base_protocol} run to take the prompt clusters from")
    return best


def compare_clustered(old: Run, new: Run, conditions, threshold: float, reps: int, seed: int,
                      cluster_of: Callable[[str], str]) -> dict[str, Any] | None:
    """Same estimator as vdanalysis.stats.compare (paired difference, equal-weight over conditions), with the
    bootstrap resampling clusters instead of tasks."""
    keys = sorted(k for k in set(old.keys) & set(new.keys) if k[1] in conditions)
    if not keys:
        return None
    conds = sorted({k[1] for k in keys})
    per = {c: [0, 0.0] for c in conds}                        # records, sum of (new - old)
    by_cluster: dict[str, dict[str, list]] = {}
    tasks = set()
    for k in keys:
        d = new.keys[k][0] - old.keys[k][0]
        per[k[1]][0] += 1
        per[k[1]][1] += d
        cell = by_cluster.setdefault(cluster_of(k[0]), {c: [0.0, 0] for c in conds})[k[1]]
        cell[0] += d
        cell[1] += 1
        tasks.add(k[0])
    diff = sum(s / n for n, s in per.values()) / len(per)
    lo, hi = bootstrap_ci([[tuple(by_cluster[c][cond]) for cond in conds] for c in sorted(by_cluster)], reps, seed)
    return {"n_records": len(keys), "n_tasks": len(tasks), "n_clusters": len(by_cluster),
            "largest_cluster": max(len({t for t in tasks if cluster_of(t) == c}) for c in by_cluster),
            "diff": diff, "ci_lo": lo, "ci_hi": hi, "label_point": point_gate(diff, threshold),
            "label_ci": ci_gate(diff, lo, hi, threshold)}


def _row(source: str, protocol: str, pair: str, suite: str, base: dict[str, Any], c: dict[str, Any], gate: str) -> dict[str, Any]:
    """Both readings are CI readings (the point label does not depend on the bootstrap). ``gate`` is the gate the
    decision or control is judged with in the main tables, for information."""
    lab_task, lab_cluster = base["label_ci"], c["label_ci"]
    w_task = base["ci_hi"] - base["ci_lo"] if base.get("ci_lo") is not None else None
    w_cluster = c["ci_hi"] - c["ci_lo"]
    return {"source": source, "protocol": protocol, "pair": pair, "suite": suite, "gate": gate,
            "n_tasks": c["n_tasks"], "n_clusters": c["n_clusters"], "largest_cluster": c["largest_cluster"],
            "stress_diff": c["diff"], "label_point": c["label_point"], "task_ci_lo": base.get("ci_lo"), "task_ci_hi": base.get("ci_hi"),
            "cluster_ci_lo": c["ci_lo"], "cluster_ci_hi": c["ci_hi"],
            "label_ci_task_bootstrap": lab_task, "label_ci_cluster_bootstrap": lab_cluster,
            "label_changes": lab_task != lab_cluster,
            "ci_width_task": w_task, "ci_width_cluster": w_cluster,
            "ci_width_ratio": (w_cluster / w_task) if w_task else None}


def cluster_rows(an: Phase2Analysis, protocols: list[str]) -> list[dict[str, Any]]:
    """One row per decision (and per control decision) of the configured suites. Empty without the bootstrap."""
    cfg = an.cfg
    spec = cfg.p2.get("cluster_bootstrap") or {}
    suites = [s for s in spec.get("suites", []) if s in cfg.suites]
    if not suites or not an.with_ci:
        return []
    out: list[dict[str, Any]] = []
    for suite in suites:
        cmap = cluster_map(an, suite)
        of = lambda t, m=cmap: m.get(t, f"task:{t}")
        for proto in protocols:
            for (pair, s), r in an.rows(proto).items():
                if s != suite:
                    continue
                old, new = an.run_for(proto, r["old"], suite), an.run_for(proto, r["new"], suite)
                c = compare_clustered(old, new, cfg.stress, cfg.threshold, cfg.reps, cfg.seed, of)
                if c is not None:
                    out.append(_row("decision", proto, pair, suite, r, c, "point" if proto == cfg.base_protocol else "ci"))
        for ctl in cfg.controls:
            gate = ctl.get("gate", "ci")
            for model in ctl["models"]:
                a, b = an.run_for(ctl["protocol_a"], model, suite), an.run_for(ctl["protocol_b"], model, suite)
                if a is None or b is None:
                    continue
                base = an.row_from_runs(ctl["protocol_b"], {"old": model, "new": model}, suite, a, b, confound="")
                c = compare_clustered(a, b, cfg.stress, cfg.threshold, cfg.reps, cfg.seed, of)
                if base and c is not None:
                    row = _row(f"control:{ctl['name']}", ctl["protocol_b"], f"{model}->{model}", suite, base, c, gate)
                    row["expected"] = EXPECTED[ctl["kind"]]
                    out.append(row)
    return out


def cluster_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for key in dict.fromkeys((r["source"], r["protocol"]) for r in rows):
        sel = [r for r in rows if (r["source"], r["protocol"]) == key]
        ratios = [r["ci_width_ratio"] for r in sel if r["ci_width_ratio"] is not None]
        out.append({"source": key[0], "protocol": key[1], "n_decisions": len(sel),
                    "n_clusters_min": min(r["n_clusters"] for r in sel), "n_clusters_max": max(r["n_clusters"] for r in sel),
                    "n_label_changes": sum(r["label_changes"] for r in sel),
                    "median_ci_width_ratio": sorted(ratios)[len(ratios) // 2] if ratios else None})
    return out
