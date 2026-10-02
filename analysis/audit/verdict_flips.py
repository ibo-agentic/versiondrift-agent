"""Consolidated verdict-flip table across every harness-choice investigated
in this audit: the BFCL drift-prompt-transmission fix (historical, already
applied), the Qwen3 thinking-mode fix (this session, applied as new runs),
and two still-diagnostic-only candidate fixes checked here for the first
time at the decision level: escape-repair (lenient) parsing, and
final-attempt-consistent ("fixed") fault scoring. For each, checks whether
applying it alone would flip any of the 8 upgrade decisions' gate label
(harmful/neutral/beneficial, threshold 0.05).

Read-only; no scoring code changed. Writes analysis/audit/verdict_flips.md.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (  # noqa: E402
    PREFIX_BFCL_RUNS, REPO_ROOT, load_parsed, load_raw, recompute_record,
    sc, task_lookup,
)
import json
import os

GATE_THRESHOLD = 0.05
STRESS = ("schema_drift", "runtime_fault")
PAIRS = [
    ("Mistral v0.1", "Mistral v0.2"),
    ("Mistral v0.2", "Mistral v0.3"),
    ("Mistral v0.1", "Mistral v0.3"),
    ("Qwen2.5", "Qwen3"),
]


def gate_label(d: float) -> str:
    if d < -GATE_THRESHOLD:
        return "harmful"
    if d > GATE_THRESHOLD:
        return "beneficial"
    return "neutral"


def mean_diff(ra: dict, rb: dict, keys: list) -> float:
    return sum(sc(rb[k]) - sc(ra[k]) for k in keys) / len(keys)


def recompute_scores(suite: str, model: str, *, lenient: bool, use_final_attempt: bool) -> dict:
    """task_key -> recomputed score, for every record, under the given mode."""
    tasks = task_lookup(suite)
    recs = load_parsed(suite, model)
    raw = load_raw(suite, model)
    out = {}
    for key, prec in recs.items():
        rrow = raw.get((prec["task_id"], prec["condition"], prec["trial_index"]))
        m, _ = recompute_record(tasks, prec, rrow, use_final_attempt=use_final_attempt, lenient=lenient, strip_think=False)
        out[key] = m["score"]
    return out


def stress_diff_from_scores(sa: dict, sb: dict, suite: str, model_a: str, model_b: str) -> float:
    ra = load_parsed(suite, model_a)
    keys = [k for k in ra if ra[k]["condition"] in STRESS]
    return sum(sb[k] - sa[k] for k in keys) / len(keys)


def load_prefix_bfcl(model: str) -> dict:
    path = os.path.join(REPO_ROOT, "results", PREFIX_BFCL_RUNS[model], "parsed_results.jsonl")
    recs = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            p = json.loads(line)
            key = (p["task_id"], p["condition"], (p.get("drift") or {}).get("type"),
                   (p.get("fault") or {}).get("type"), p.get("trial_index", 0))
            recs[key] = p
    return recs


def main() -> None:
    rows: list[dict] = []  # each: harness_choice, pair, suite, verdict_before, verdict_after, diff_before, diff_after

    # ---- 1. BFCL drift-prompt-transmission fix (historical; already applied project-wide) ----
    for a, b in PAIRS:
        ra_pre, rb_pre = load_prefix_bfcl(a), load_prefix_bfcl(b)
        ra_post, rb_post = load_parsed("BFCL", a), load_parsed("BFCL", b)
        common_pre = sorted(set(ra_pre) & set(rb_pre))
        common_post = sorted(set(ra_post) & set(rb_post))
        stress_pre = [k for k in common_pre if k[1] in STRESS]
        stress_post = [k for k in common_post if k[1] in STRESS]
        d_pre = mean_diff(ra_pre, rb_pre, stress_pre)
        d_post = mean_diff(ra_post, rb_post, stress_post)
        rows.append({
            "harness_choice": "BFCL drift-prompt-transmission fix (applied, historical)",
            "pair": f"{a}->{b}", "suite": "BFCL",
            "before": gate_label(d_pre), "after": gate_label(d_post),
            "diff_before": d_pre, "diff_after": d_post,
        })

    # ---- 2. Qwen3 thinking-mode fix (applied this session, new runs) ----
    for suite in ("synthetic", "BFCL"):
        ra = load_parsed(suite, "Qwen2.5")
        for variant, tag in (("Qwen3-nothink", "nothink (primary)"), ("Qwen3-think_long", "think_long (secondary)")):
            rb_pre = load_parsed(suite, "Qwen3")
            rb_post = load_parsed(suite, variant)
            common_pre = sorted(set(ra) & set(rb_pre))
            common_post = sorted(set(ra) & set(rb_post))
            d_pre = mean_diff(ra, rb_pre, [k for k in common_pre if k[1] in STRESS])
            d_post = mean_diff(ra, rb_post, [k for k in common_post if k[1] in STRESS])
            rows.append({
                "harness_choice": f"Qwen3 thinking-mode fix: {tag} (applied, this session)",
                "pair": "Qwen2.5->Qwen3", "suite": suite,
                "before": gate_label(d_pre), "after": gate_label(d_post),
                "diff_before": d_pre, "diff_after": d_post,
            })

    # ---- 3. Escape-repair (lenient) fix -- candidate, not applied to official scoring ----
    for suite in ("synthetic", "BFCL"):
        model_scores_strict = {}
        model_scores_lenient = {}
        for a, b in PAIRS:
            for m in (a, b):
                if m not in model_scores_strict:
                    model_scores_strict[m] = recompute_scores(suite, m, lenient=False, use_final_attempt=False)
                    model_scores_lenient[m] = recompute_scores(suite, m, lenient=True, use_final_attempt=False)
        for a, b in PAIRS:
            ra, rb = load_parsed(suite, a), load_parsed(suite, b)
            keys = [k for k in (set(ra) & set(rb)) if ra[k]["condition"] in STRESS]
            d_strict = sum(model_scores_strict[b][k] - model_scores_strict[a][k] for k in keys) / len(keys)
            d_lenient = sum(model_scores_lenient[b][k] - model_scores_lenient[a][k] for k in keys) / len(keys)
            rows.append({
                "harness_choice": "Escape-repair (lenient) parsing fix -- CANDIDATE, not applied",
                "pair": f"{a}->{b}", "suite": suite,
                "before": gate_label(d_strict), "after": gate_label(d_lenient),
                "diff_before": d_strict, "diff_after": d_lenient,
            })

    # ---- 4. Fault-rescore (final-attempt-consistent) fix -- candidate, not applied ----
    for suite in ("synthetic", "BFCL"):
        model_scores_mixed = {}
        model_scores_final = {}
        for a, b in PAIRS:
            for m in (a, b):
                if m not in model_scores_mixed:
                    model_scores_mixed[m] = recompute_scores(suite, m, lenient=False, use_final_attempt=False)
                    model_scores_final[m] = recompute_scores(suite, m, lenient=False, use_final_attempt=True)
        for a, b in PAIRS:
            ra, rb = load_parsed(suite, a), load_parsed(suite, b)
            keys = [k for k in (set(ra) & set(rb)) if ra[k]["condition"] in STRESS]
            d_mixed = sum(model_scores_mixed[b][k] - model_scores_mixed[a][k] for k in keys) / len(keys)
            d_final = sum(model_scores_final[b][k] - model_scores_final[a][k] for k in keys) / len(keys)
            rows.append({
                "harness_choice": "Fault rescore (final-attempt-consistent) fix -- CANDIDATE, not applied",
                "pair": f"{a}->{b}", "suite": suite,
                "before": gate_label(d_mixed), "after": gate_label(d_final),
                "diff_before": d_mixed, "diff_after": d_final,
            })

    # ---- Write markdown ----
    lines: list[str] = []
    lines.append("# Verdict flips found across this audit\n")
    lines.append(
        "One row per (harness choice x upgrade pair x suite). "
        "\"before\"/\"after\" are the gate label (harmful/neutral/beneficial, "
        "threshold 0.05) under the unfixed vs fixed harness choice. "
        "**APPLIED** rows reflect changes already baked into the project's "
        "official numbers (BFCL drift-prompt fix, historical) or into new "
        "runs produced this session (Qwen3 thinking-mode fix). **CANDIDATE** "
        "rows are diagnostics only (escape-repair, fault-rescore) -- strict, "
        "mixed-attempt scoring remains the project's official metric for "
        "every published number; these rows show what *would* change if "
        "either candidate fix were adopted.\n"
    )
    lines.append("| # | harness choice | pair | suite | verdict before | verdict after | flip? | stress diff before -> after |")
    lines.append("|---|---|---|---|---|---|---|---|")
    flips_only = []
    for i, r in enumerate(rows, 1):
        flipped = r["before"] != r["after"]
        flips_only.append(flipped)
        marker = "**FLIP**" if flipped else "no change"
        lines.append(
            f"| {i} | {r['harness_choice']} | {r['pair']} | {r['suite']} | {r['before']} | {r['after']} | "
            f"{marker} | {r['diff_before']:+.3f} -> {r['diff_after']:+.3f} |"
        )

    n_flips = sum(flips_only)
    lines.append(f"\n**{n_flips} of {len(rows)} rows are label flips.**\n")

    lines.append(
        "\n## Reading this table\n\n"
        "- Rows 1-4 (BFCL drift-prompt fix): only the "
        "Mistral v0.1->v0.3 BFCL decision flips label (neutral -> "
        "beneficial); the other three BFCL pairs keep the same label through "
        "this fix (their magnitudes still move a lot -- see AUDIT.md H17 -- "
        "just not across a gate boundary).\n"
        "- Rows 5-8 (Qwen3 thinking-mode fix, nothink + think_long x 2 "
        "suites): BFCL flips from harmful to neutral under both corrected "
        "configs; synthetic stays labeled neutral both before and after, but "
        "the point estimate crosses zero (sign reversal without a label "
        "flip) -- flagged as \"no change\" here since the 0.05 gate itself "
        "doesn't move, but see `qwen3_rerun.md` / `decisions_corrected.md` "
        "for the magnitude story.\n"
        "- Rows 9-16 (escape-repair candidate): check whether these rows "
        "flip before treating any of them as settled -- the escape bug was "
        "concentrated in Mistral v0.1/v0.2 `runtime_fault` (see "
        "`escape_check.md`), so the Mistral v0.1->v0.2 rows are where a flip "
        "is most plausible a priori.\n"
        "- Rows 17-24 (fault-rescore candidate): checks whether "
        "final-attempt-consistent scoring (vs. the current mixed "
        "first-attempt-metrics/retry-exec_ok scoring, see AUDIT.md E10) "
        "moves any decision across the gate boundary on its own.\n"
    )

    out_path = Path(__file__).parent / "verdict_flips.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}: {n_flips}/{len(rows)} flips")
    for i, r in enumerate(rows, 1):
        if r["before"] != r["after"]:
            print(f"  FLIP #{i}: {r['harness_choice']} | {r['pair']} | {r['suite']} | {r['before']} -> {r['after']}")


if __name__ == "__main__":
    main()
