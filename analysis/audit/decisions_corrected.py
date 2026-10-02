"""Recompute every downstream decision/gate/calibration analysis using the
corrected Qwen3 runs (nothink = primary, think_long = secondary), with the
original Qwen3 run relabeled "pre-fix" throughout. Mistral decisions are
unchanged (recomputed from the same final runs as always) and included for
context/consistency.

Read-only; reuses the exact conventions already used elsewhere in this
audit: GATE_THRESHOLD=0.05, task-cluster bootstrap (10,000 reps, seed 1234),
cross-pair leave-one-out informativeness canary selection with category
coverage (k=30), 1000-rep random-subset baseline, least-squares-through-
-origin calibration fit (scripts/analyze_gate_threshold_sensitivity.py).
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import load_parsed, sc  # noqa: E402

GATE_THRESHOLD = 0.05
STRESS = ("schema_drift", "runtime_fault")
CONDITIONS = ["baseline", "schema_drift", "runtime_fault"]
BOOTSTRAP_REPS = 10000
BOOTSTRAP_SEED = 1234
K = 30
N_RANDOM_REPS = 1000
RANDOM_SEED = 20261002

QWEN_VARIANTS = [("Qwen3", "pre-fix"), ("Qwen3-nothink", "primary (nothink)"), ("Qwen3-think_long", "secondary (think_long)")]
MISTRAL_PAIRS = [("Mistral v0.1", "Mistral v0.2"), ("Mistral v0.2", "Mistral v0.3"), ("Mistral v0.1", "Mistral v0.3")]


def pairs_for(qwen_model: str) -> list[tuple[str, str]]:
    return MISTRAL_PAIRS + [("Qwen2.5", qwen_model)]


def gate_label(d: float) -> str:
    if d < -GATE_THRESHOLD:
        return "harmful"
    if d > GATE_THRESHOLD:
        return "beneficial"
    return "neutral"


def mean_diff(ra: dict, rb: dict, keys: list) -> float:
    return sum(sc(rb[k]) - sc(ra[k]) for k in keys) / len(keys)


def flip_counts(ra: dict, rb: dict, keys: list) -> tuple:
    neg = sum(1 for k in keys if sc(ra[k]) == 1 and sc(rb[k]) == 0)
    pos = sum(1 for k in keys if sc(ra[k]) == 0 and sc(rb[k]) == 1)
    return neg, pos


def cluster_ci(ra: dict, rb: dict, keys: list, rng: random.Random) -> tuple:
    task_ids = sorted({k[0] for k in keys})
    by_task = {t: [k for k in keys if k[0] == t] for t in task_ids}
    diffs = []
    for _ in range(BOOTSTRAP_REPS):
        picked = [task_ids[rng.randrange(len(task_ids))] for _ in task_ids]
        ks = [k for t in picked for k in by_task[t]]
        diffs.append(mean_diff(ra, rb, ks))
    diffs.sort()
    return diffs[250], diffs[9749]


def select_canary(ranked: list, categories: dict, k: int) -> list:
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


def fit_alpha(full_diffs: list, canary_diffs: list) -> float:
    denom = sum(c * c for c in canary_diffs)
    return sum(f * c for f, c in zip(full_diffs, canary_diffs)) / denom if denom else float("nan")


def load_all(suite: str, qwen_model: str) -> dict:
    models = set()
    for a, b in pairs_for(qwen_model):
        models.add(a)
        models.add(b)
    return {m: load_parsed(suite, m) for m in models}


def main() -> None:
    lines: list[str] = []
    lines.append("# Decisions recomputed with the corrected Qwen3 runs\n")
    lines.append(
        "Every table below is recomputed directly from existing result logs "
        "(no new runs), reusing the exact bootstrap/selection/calibration "
        "conventions already used throughout this audit. **nothink is the "
        "primary corrected Qwen3 config, think_long is secondary, the "
        "original run is labeled \"pre-fix\" throughout.** Mistral decisions "
        "are unchanged from `docs/results_summary.md` and are recomputed "
        "here only for internal consistency (same 10 final runs as always).\n"
    )

    # ============ Part 1: Upgrade decision table ============
    lines.append("\n## 1. Upgrade decision table, both suites, all three Qwen variants\n")
    lines.append("| suite | decision | d_baseline | d_drift | d_fault | **d_stress** | label | neg/pos flips | 95% CI |")
    lines.append("|---|---|---|---|---|---|---|---|---|")

    decision_full: dict[tuple, dict] = {}  # (suite, qwen_model) -> {pair: full_stress_diff}
    decision_task_diff: dict[tuple, dict] = {}  # (suite, qwen_model) -> {pair: {task_id: diff}}
    decision_categories: dict[tuple, dict] = {}

    for suite in ("synthetic", "BFCL"):
        for qwen_model, qwen_tag in QWEN_VARIANTS:
            recs_by_model = load_all(suite, qwen_model)
            full = {}
            task_diff = {}
            cats = {}
            rng = random.Random(BOOTSTRAP_SEED)
            for a, b in pairs_for(qwen_model):
                ra, rb = recs_by_model[a], recs_by_model[b]
                common_keys = sorted(set(ra) & set(rb))
                task_ids = sorted({k[0] for k in common_keys})
                stress_keys = [k for k in common_keys if k[1] in STRESS]
                by_task = {t: [k for k in stress_keys if k[0] == t] for t in task_ids}
                d_stress = mean_diff(ra, rb, stress_keys)
                lo, hi = cluster_ci(ra, rb, stress_keys, rng)
                label = gate_label(d_stress)
                neg, pos = flip_counts(ra, rb, stress_keys)
                d_base = mean_diff(ra, rb, [k for k in common_keys if k[1] == "baseline"])
                d_drift = mean_diff(ra, rb, [k for k in common_keys if k[1] == "schema_drift"])
                d_fault = mean_diff(ra, rb, [k for k in common_keys if k[1] == "runtime_fault"])
                pair_label = f"{a}->{b}" if a != "Qwen2.5" else f"Qwen2.5->{b} [{qwen_tag}]"
                lines.append(
                    f"| {suite} | {pair_label} | {d_base:+.3f} | {d_drift:+.3f} | {d_fault:+.3f} | "
                    f"**{d_stress:+.3f}** | {label} | {neg}/{pos} | [{lo:+.3f}, {hi:+.3f}] |"
                )
                full[(a, b)] = d_stress
                task_diff[(a, b)] = {t: mean_diff(ra, rb, by_task[t]) for t in task_ids}
                cats[(a, b)] = {
                    t: {k[2] for k in ks if k[1] == "schema_drift"} | {k[3] for k in ks if k[1] == "runtime_fault"}
                    for t, ks in by_task.items()
                }
            decision_full[(suite, qwen_model)] = full
            decision_task_diff[(suite, qwen_model)] = task_diff
            decision_categories[(suite, qwen_model)] = cats

    # ============ Part 2: Gate accuracy (LOUO selected / random / baseline-only) ============
    lines.append("\n## 2. Gate accuracy: LOUO-selected canary (k=30), random canary (1000x, k=30), baseline-only gate\n")
    lines.append(
        "LOUO selection: for each decision, informativeness = mean |per-task "
        "stress diff| over the OTHER 3 decisions IN THE SAME QWEN-VARIANT "
        "SET (so a Mistral pair's canary is now selected partly using the "
        "corrected, much-smaller Qwen signal -- this is exactly the "
        "mechanism that can make Mistral canaries change too, see note "
        "below the table).\n"
    )
    lines.append("| suite | qwen variant | decision | truth | selected@k=30 | correct? | random match rate | baseline-only | agrees? |")
    lines.append("|---|---|---|---|---|---|---|---|---|")

    for suite in ("synthetic", "BFCL"):
        for qwen_model, qwen_tag in QWEN_VARIANTS:
            recs_by_model = load_all(suite, qwen_model)
            full = decision_full[(suite, qwen_model)]
            task_diff = decision_task_diff[(suite, qwen_model)]
            cats = decision_categories[(suite, qwen_model)]
            pairs = pairs_for(qwen_model)
            for a, b in pairs:
                ra, rb = recs_by_model[a], recs_by_model[b]
                common_keys = sorted(set(ra) & set(rb))
                task_ids = sorted({k[0] for k in common_keys})
                stress_keys = [k for k in common_keys if k[1] in STRESS]
                baseline_keys = [k for k in common_keys if k[1] == "baseline"]
                by_task = {t: [k for k in stress_keys if k[0] == t] for t in task_ids}

                truth = gate_label(full[(a, b)])
                others = [p for p in pairs if p != (a, b)]
                info = {t: sum(abs(task_diff[o].get(t, 0.0)) for o in others) / len(others) for t in task_ids}
                ranked = sorted(task_ids, key=lambda t: info[t], reverse=True)
                canary = select_canary(ranked, cats[(a, b)], K)
                canary_keys = [k for t in canary for k in by_task[t]]
                canary_diff = mean_diff(ra, rb, canary_keys)
                sel_verdict = gate_label(canary_diff)
                sel_correct = "YES" if sel_verdict == truth else "no"

                rng = random.Random(f"{RANDOM_SEED}-{suite}-{qwen_model}-{a}-{b}-{K}")
                match = 0
                for _ in range(N_RANDOM_REPS):
                    subset = rng.sample(task_ids, K)
                    keys = [k for t in subset for k in by_task[t]]
                    d = mean_diff(ra, rb, keys)
                    if gate_label(d) == truth:
                        match += 1

                baseline_diff = mean_diff(ra, rb, baseline_keys)
                baseline_verdict = gate_label(baseline_diff)
                base_agree = "YES" if baseline_verdict == truth else "no"

                pair_label = f"{a}->{b}" if a != "Qwen2.5" else f"Qwen2.5->{b} [{qwen_tag}]"
                lines.append(
                    f"| {suite} | {qwen_tag if a == 'Qwen2.5' else '-'} | {pair_label} | {truth} | "
                    f"{sel_verdict} ({canary_diff:+.3f}) | {sel_correct} | {match/N_RANDOM_REPS:.3f} | "
                    f"{baseline_verdict} ({baseline_diff:+.3f}) | {base_agree} |"
                )

    lines.append(
        "\n**Note on Mistral canary changes:** because Mistral canary "
        "selection partly depends on the Qwen decision's per-task diffs "
        "(cross-pair informativeness), the Mistral rows' `selected@k=30` "
        "values can differ across the three Qwen-variant blocks above even "
        "though the Mistral runs themselves are identical in all three -- "
        "any such difference is coming entirely from which tasks get "
        "selected, not from any change in Mistral's own scores.\n"
    )

    # ============ Part 3: Calibration ============
    lines.append("\n## 3. Calibration fits (alpha, least squares through origin, k=30)\n")
    lines.append(
        "alpha = sum(full_i * canary_i) / sum(canary_i^2) (same as "
        "`scripts/analyze_gate_threshold_sensitivity.py:fit_alpha`). LOUO: "
        "alpha fit on the other 3 decisions, applied to the held-out one. "
        "Family transfer: alpha(Mistral->Qwen) fit on the 3 Mistral "
        "decisions (n=3); alpha(Qwen->Mistral) fit on the single Qwen "
        "decision (n=1, always unstable -- see AUDIT.md J22).\n"
    )
    lines.append("| suite | qwen variant | LOUO alpha (M12, M23, M13, Qwen) | alpha(Mistral->Qwen) | alpha(Qwen->Mistral) | magnitude MAE: raw / LOUO-cal |")
    lines.append("|---|---|---|---|---|---|")

    for suite in ("synthetic", "BFCL"):
        for qwen_model, qwen_tag in QWEN_VARIANTS:
            recs_by_model = load_all(suite, qwen_model)
            full = decision_full[(suite, qwen_model)]
            task_diff = decision_task_diff[(suite, qwen_model)]
            cats = decision_categories[(suite, qwen_model)]
            pairs = pairs_for(qwen_model)

            canary_diff = {}
            for a, b in pairs:
                ra, rb = recs_by_model[a], recs_by_model[b]
                common_keys = sorted(set(ra) & set(rb))
                task_ids = sorted({k[0] for k in common_keys})
                stress_keys = [k for k in common_keys if k[1] in STRESS]
                by_task = {t: [k for k in stress_keys if k[0] == t] for t in task_ids}
                others = [p for p in pairs if p != (a, b)]
                info = {t: sum(abs(task_diff[o].get(t, 0.0)) for o in others) / len(others) for t in task_ids}
                ranked = sorted(task_ids, key=lambda t: info[t], reverse=True)
                canary = select_canary(ranked, cats[(a, b)], K)
                canary_diff[(a, b)] = mean_diff(ra, rb, [k for t in canary for k in by_task[t]])

            qwen_pair = ("Qwen2.5", qwen_model)
            names = pairs
            loup_alpha = {}
            loup_pred = {}
            for p in names:
                train = [x for x in names if x != p]
                alpha = fit_alpha([full[x] for x in train], [canary_diff[x] for x in train])
                loup_alpha[p] = alpha
                loup_pred[p] = alpha * canary_diff[p]
            mistral_train = [p for p in names if p != qwen_pair]
            alpha_m2q = fit_alpha([full[x] for x in mistral_train], [canary_diff[x] for x in mistral_train])
            alpha_q2m = fit_alpha([full[qwen_pair]], [canary_diff[qwen_pair]])

            mae_raw = sum(abs(canary_diff[x] - full[x]) for x in names) / len(names)
            mae_loup = sum(abs(loup_pred[x] - full[x]) for x in names) / len(names)

            alpha_str = ", ".join(f"{loup_alpha[p]:.2f}" for p in names)
            lines.append(
                f"| {suite} | {qwen_tag} | {alpha_str} | {alpha_m2q:.2f} | {alpha_q2m:.2f} | "
                f"{mae_raw:.3f} / {mae_loup:.3f} |"
            )

    lines.append(
        "\n**What changes because the Qwen pair is now neutral (not "
        "harmful/decisive):**\n"
        "- `alpha(Qwen->Mistral)` (the single-point fit) is now fit on a "
        "near-zero full diff with a correspondingly different canary diff -- "
        "this was already flagged as statistically meaningless with n=1 "
        "(AUDIT.md J22), and a near-zero full value makes the ratio even "
        "more sensitive to canary-selection noise than before (a small "
        "canary-diff denominator change can swing alpha sharply). Treat "
        "every `alpha(Qwen->Mistral)` value in this table as illustrative, "
        "never as a calibration to rely on.\n"
        "- The Qwen decision's own LOUO alpha and predicted magnitude move "
        "accordingly, but since the decision is neutral either way (pre-fix "
        "on BFCL was the one exception -- harmful -- and that's precisely "
        "the row that changes), the *decision accuracy* impact is really "
        "about whether the corrected BFCL Qwen row still gates to the same "
        "label under calibration, which table 1 above already answers "
        "directly (gate label), not something calibration adds information "
        "to here.\n"
    )

    # ============ Part 4: K24-style ranking/gap table ============
    lines.append("\n## 4. K24-style ranking/gap table: per-condition gaps + bootstrap CI, Qwen2.5 vs each Qwen3 variant\n")
    lines.append("(Mistral rows are unchanged from AUDIT.md K24 and are not repeated here; only the Qwen2.5->Qwen3 row changes.)\n")
    lines.append("| suite | qwen variant | condition | diff | 95% CI | significant? |")
    lines.append("|---|---|---|---|---|---|")
    for suite in ("synthetic", "BFCL"):
        for qwen_model, qwen_tag in QWEN_VARIANTS:
            ra = load_parsed(suite, "Qwen2.5")
            rb = load_parsed(suite, qwen_model)
            common_keys = sorted(set(ra) & set(rb))
            rng = random.Random(BOOTSTRAP_SEED)
            signs = []
            for cond in CONDITIONS:
                keys = [k for k in common_keys if k[1] == cond]
                d = mean_diff(ra, rb, keys)
                lo, hi = cluster_ci(ra, rb, keys, rng)
                sig = "significant" if (lo > 0 or hi < 0) else "n.s."
                signs.append(d > 0)
                lines.append(f"| {suite} | {qwen_tag} | {cond} | {d:+.4f} | [{lo:+.4f}, {hi:+.4f}] | {sig} |")
            agree = "ALL SAME SIGN" if signs[0] == signs[1] == signs[2] else "SIGNS DISAGREE"
            lines.append(f"| {suite} | {qwen_tag} | **sign agreement** | {agree} | | |")

    out_path = Path(__file__).parent / "decisions_corrected.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")

    # Return key values for verdict_flips.py to reuse without recomputing.
    return decision_full


if __name__ == "__main__":
    main()
