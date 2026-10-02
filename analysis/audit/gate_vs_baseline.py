"""AUDIT follow-up item 5: baseline-only gate vs stress-based gate, and
selected vs random 30-task canary (1000 reps), per upgrade pair, per suite.

Read-only; reuses the exact gate-threshold convention (GATE_THRESHOLD=0.05)
and cross-pair leave-one-out informativeness selection method from
scripts/analyze_gate_threshold_sensitivity.py (k=30, category-coverage pass).
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import UPGRADE_PAIRS, load_parsed, sc  # noqa: E402

GATE_THRESHOLD = 0.05
STRESS = ("schema_drift", "runtime_fault")
K = 30
N_REPS = 1000
SEED = 20261002


def gate_label(d: float) -> str:
    if d < -GATE_THRESHOLD:
        return "harmful"
    if d > GATE_THRESHOLD:
        return "beneficial"
    return "neutral"


def mean_diff(ra: dict, rb: dict, keys: list) -> float:
    return sum(sc(rb[k]) - sc(ra[k]) for k in keys) / len(keys)


def select_canary(ranked: list, categories: dict, k: int) -> list:
    """Top-k by cross-pair |diff| with a category-coverage pass (same logic
    as scripts/analyze_gate_threshold_sensitivity.py select_canary)."""
    selected, covered = [], set()
    for t in ranked:
        if len(selected) >= k:
            break
        if categories[t] - covered:
            selected.append(t)
            covered |= categories[t]
    for t in ranked:
        if len(selected) >= k:
            break
        if t not in selected:
            selected.append(t)
    return selected


def main() -> None:
    lines: list[str] = []
    lines.append("# Gate vs baseline: baseline-only gate vs stress-based gate; selected vs random canary\n")
    lines.append(
        "Read-only. Gate threshold = 0.05 (same as `docs/protocol.md`). "
        "'stress-based gate' = full-suite truth as published "
        "(`tables/upgrade_decisions.csv`, mean(schema_drift, runtime_fault) "
        "diff). 'baseline-only gate' = the same threshold rule applied to "
        "the `baseline` condition diff alone. 'selected' canary = k=30, "
        "cross-pair leave-one-out informativeness with category coverage "
        "(same method as `scripts/analyze_gate_threshold_sensitivity.py`, "
        "trained only on the other 3 decisions within the same suite -- "
        "never on the decision being evaluated). 'random' = 1000 uniform "
        "30-task subsets, match rate against the stress-based truth.\n"
    )

    for suite in ("synthetic", "BFCL"):
        lines.append(f"\n## {suite}\n")
        lines.append(
            "| pair | stress truth | baseline-only verdict | agree with stress truth? | "
            "selected-canary (k=30) verdict | selected correct? | random-canary match rate (1000x, k=30) |"
        )
        lines.append("|---|---|---|---|---|---|---|")

        all_runs = {m: load_parsed(suite, m) for pair in UPGRADE_PAIRS for m in pair}
        task_ids_global = sorted({k[0] for recs in all_runs.values() for k in recs})

        # Per-decision full stress diff and per-task diff (for cross-pair selection).
        full = {}
        task_diff = {}
        cats = {}
        for a, b in UPGRADE_PAIRS:
            ra, rb = all_runs[a], all_runs[b]
            common = sorted(set(ra) & set(rb))
            task_ids = sorted({k[0] for k in common})
            stress_keys = [k for k in common if k[1] in STRESS]
            by_task = {t: [k for k in stress_keys if k[0] == t] for t in task_ids}
            full[(a, b)] = mean_diff(ra, rb, stress_keys)
            task_diff[(a, b)] = {t: mean_diff(ra, rb, by_task[t]) for t in task_ids}
            cats[(a, b)] = {
                t: {k[2] for k in ks if k[1] == "schema_drift"} | {k[3] for k in ks if k[1] == "runtime_fault"}
                for t, ks in by_task.items()
            }

        for a, b in UPGRADE_PAIRS:
            ra, rb = all_runs[a], all_runs[b]
            common = sorted(set(ra) & set(rb))
            task_ids = sorted({k[0] for k in common})
            baseline_keys = [k for k in common if k[1] == "baseline"]
            stress_keys = [k for k in common if k[1] in STRESS]
            by_task = {t: [k for k in stress_keys if k[0] == t] for t in task_ids}

            truth = gate_label(full[(a, b)])
            baseline_diff = mean_diff(ra, rb, baseline_keys)
            baseline_verdict = gate_label(baseline_diff)
            agree = "YES" if baseline_verdict == truth else "no"

            others = [p for p in UPGRADE_PAIRS if p != (a, b)]
            info = {
                t: sum(abs(task_diff[o].get(t, 0.0)) for o in others) / len(others)
                for t in task_ids
            }
            ranked = sorted(task_ids, key=lambda t: info[t], reverse=True)
            canary = select_canary(ranked, cats[(a, b)], K)
            canary_keys = [k for t in canary for k in by_task[t]]
            canary_diff = mean_diff(ra, rb, canary_keys)
            canary_verdict = gate_label(canary_diff)
            canary_correct = "YES" if canary_verdict == truth else "no"

            rng = random.Random(f"{SEED}-{suite}-{a}-{b}-{K}")
            match = 0
            for _ in range(N_REPS):
                subset = rng.sample(task_ids, K)
                keys = [k for t in subset for k in by_task[t]]
                d = mean_diff(ra, rb, keys)
                if gate_label(d) == truth:
                    match += 1

            lines.append(
                f"| {a} -> {b} | {truth} ({full[(a,b)]:+.3f}) | {baseline_verdict} ({baseline_diff:+.3f}) | "
                f"{agree} | {canary_verdict} ({canary_diff:+.3f}) | {canary_correct} | {match/N_REPS:.3f} |"
            )

    lines.append(
        "\n## Interpretation\n\n"
        "A baseline-only gate agreeing with the stress-based gate on a given "
        "pair means that, for that specific decision, running the clean "
        "condition alone would already have produced the correct "
        "accept/reject/inspect verdict -- i.e. the stress conditions were "
        "not *necessary* to reach that verdict (though they may still be "
        "necessary to size the effect, or to catch the category-level swaps "
        "AUDIT.md's H2 discusses). See AUDIT.md section K24 for the "
        "per-condition significance test this table complements: K24 shows "
        "BFCL's baseline gap is statistically significant and same-signed "
        "for all four pairs, and the baseline-only verdicts below confirm "
        "whether that significant gap is also large enough to cross the "
        "0.05 gate threshold on its own.\n"
    )

    out_path = Path(__file__).parent / "gate_vs_baseline.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
