"""Audit follow-up: intent-match strictness, informed by the human spot-check
(analysis/audit/intent_spotcheck_filled.csv: 32/40 agree, kappa=0.60, all
8 disagreements rule=False/human=yes, attributable to 5 causes).

Part 1: across all 10 final runs, every condition, count records whose
strict args_intent_match is False but relaxing exactly ONE named cause
(independently) would make it True -- i.e. the record's intent failure is
attributable to that specific, named leniency. Broken down by model.

Part 2: recompute the full score (all 5 components) with intent_match
relaxed for ALL 5 causes at once, and check whether any of the 8 published
upgrade decisions (4 pairs x 2 suites) flips its gate label (threshold
0.05). Diagnostic only -- the official args_intent_match/score is never
changed; this is read-only analysis over existing logs.

Writes analysis/audit/intent_strictness.md and appends any flips found to
analysis/audit/verdict_flips.md.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import FINAL_RUNS, UPGRADE_PAIRS, load_parsed, sc, task_lookup  # noqa: E402
from relaxed_intent import ALL_CAUSES, relaxed_compatible  # noqa: E402

from upgradecanary.runner import task_base_schema  # noqa: E402
from upgradecanary.perturbations.schema_drift import Drift, drifted_schema  # noqa: E402
from upgradecanary.perturbations.runtime_faults import Fault  # noqa: E402
from upgradecanary.evaluator import evaluate  # noqa: E402

GATE_THRESHOLD = 0.05
STRESS = ("schema_drift", "runtime_fault")
BOOTSTRAP_REPS = 10000
BOOTSTRAP_SEED = 1234


def to_drift(d):
    return Drift(type=d["type"], tool=d["tool"], field=d["field"], params=d.get("params", {})) if d else None


def to_fault(f):
    return Fault(type=f["type"], params=f.get("params", {})) if f else None


def gate_label(d: float) -> str:
    if d < -GATE_THRESHOLD:
        return "harmful"
    if d > GATE_THRESHOLD:
        return "beneficial"
    return "neutral"


def mean_diff(ra: dict, rb: dict, keys: list) -> float:
    return sum(sc(rb[k]) - sc(ra[k]) for k in keys) / len(keys)


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


def relaxed_intent_for_record(tasks: dict, prec: dict, causes: set[str]) -> bool:
    task = tasks[prec["task_id"]]
    drift = to_drift(prec.get("drift"))
    base_schema = task_base_schema(task)
    schema = drifted_schema(base_schema, drift)
    parsed_call = prec.get("parsed_call")
    if parsed_call is None:
        return False
    parsed_args = parsed_call.get("arguments", {})
    return relaxed_compatible(parsed_args, task.expected_call["arguments"], drift, task.acceptable, schema, causes)


def relaxed_score_for_record(tasks: dict, prec: dict, causes: set[str]) -> float:
    """Full score with args_intent_match relaxed (all other components
    exactly as evaluator.evaluate() already computed them, since none of
    the 5 causes touch parse/tool-name/validity/execution)."""
    m = prec["metrics"]
    if m["args_intent_match"]:
        return float(m["score"])  # unaffected by relaxation
    relaxed_intent = relaxed_intent_for_record(tasks, prec, causes)
    if not relaxed_intent:
        return float(m["score"])
    return float(m["parse_ok"] and m["tool_name_ok"] and relaxed_intent and m["args_valid_under_drift"] and m["executor_ok"])


def main() -> None:
    lines: list[str] = []
    lines.append("# Intent-match strictness: human spot-check findings, scaled up\n")
    lines.append(
        "## Human spot-check result\n\n"
        "`analysis/audit/intent_spotcheck_filled.csv` (40 records, 20 "
        "rule_verdict=true / 20 false, spread across drift types/models/"
        "suites): **32/40 agree (80%), Cohen's kappa = 0.60** (moderate "
        "agreement). **All 8 disagreements are rule=False, human=True** -- "
        "the rule-based `args_intent_match` metric is never too lenient in "
        "this sample, only too strict. Five causes account for all 8:\n\n"
        "1. **extra `\"properties\"` wrapper** -- model emits "
        "`{\"properties\": {...actual args...}}` instead of the arguments "
        "directly (2/8 cases).\n"
        "2. **string booleans** -- `\"true\"`/`\"false\"` instead of a JSON "
        "boolean (2/8 cases).\n"
        "3. **units attached to numbers** -- `\"5m\"` instead of `5` (2/8 "
        "cases).\n"
        "4. **unit synonyms** -- `\"miles\"` instead of `\"mi\"` (1/8 "
        "cases).\n"
        "5. **swapped order for symmetric args** -- e.g. `team1`/`team2` "
        "values exchanged, where the task is symmetric in those two slots "
        "(1/8 cases).\n\n"
        "**Calibration check** (`_relaxed_intent_calibration.py`): a "
        "diagnostic `relaxed_compatible()` implementing exactly these 5 "
        "leniencies (new file, `analysis/audit/relaxed_intent.py`, calling "
        "`upgradecanary/perturbations/schema_drift.py`'s own "
        "canonicalization helpers unchanged -- nothing under `upgradecanary/` "
        "was modified) reproduces the human verdict on **39/40** rows when "
        "all 5 causes are enabled together. The one exception "
        "(`bfcl-simple_python_10`, Qwen2.5) is **not** human-judgment "
        "noise -- it is a real rule the 5-cause taxonomy does not capture. "
        "The human labeling rule for the \"units attached to numbers\" "
        "cause is narrower than a per-value suffix strip: **a unit-"
        "suffixed value is accepted only if the unit is applied "
        "*consistently* to every measurement in the call; mixing a unit-"
        "suffixed value with a unitless value for another measurement of "
        "the same kind -- when a separate `unit` field exists to carry "
        "that information once -- is not accepted.** Applying that rule "
        "to the two near-identical `bfcl-simple_python_10` records: "
        "Mistral v0.3 emitted `{\"base\": \"6cm\", \"height\": \"10cm\"}` "
        "-- the `cm` suffix is attached to *both* measurements "
        "consistently, so it reads as a single (if redundant) unit choice "
        "applied uniformly, and the human accepted it. Qwen2.5 emitted "
        "`{\"base\": \"6cm\", \"height\": 10}` -- `cm` is attached to "
        "`base` only, `height` is bare, which is an inconsistent/ambiguous "
        "use of units rather than a uniform formatting choice, so the "
        "human rejected it. `relaxed_compatible()`'s `unit_number` "
        "leniency strips a unit suffix from each value independently and "
        "has no notion of consistency across sibling measurements, so it "
        "accepts both records -- this is a genuine gap in the taxonomy, "
        "not noise in the human label.\n\n"
        "**In-sample caveat**: `relaxed_compatible()`'s 5 causes (and "
        "their parameters, e.g. the unit-synonym map) were derived "
        "directly from this same 40-row sample, and the 39/40 calibration "
        "figure above is measured on that same sample -- it is an "
        "in-sample, optimistic number, not a held-out validation. "
        "**The reportable human-vs-official-rule agreement is 32/40, "
        "Cohen's kappa = 0.60** (first line of this section); the 39/40 "
        "figure should be read only as \"the taxonomy is internally "
        "consistent with the sample it was built from, modulo the one gap "
        "just described,\" not as independent evidence that the taxonomy "
        "generalizes.\n"
    )

    # --- Part 1: per-cause, per-model attribution ---
    lines.append("\n## Part 1: records whose intent failure is attributable to exactly one named cause\n")
    lines.append(
        "For every record with strict `args_intent_match=False`, each cause "
        "is tried independently (the other 4 off); a record is attributed "
        "to a cause if enabling *that cause alone* flips intent_match to "
        "True. A record can be attributed to more than one cause if either "
        "alone would resolve it (rare -- tracked separately below).\n"
    )
    lines.append("| suite | model | cond | intent_fail_n | properties_wrapper | string_bool | unit_number | unit_synonym | swapped_symmetric | explained_by_any | explained_by_none |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")

    per_model_totals: dict[str, dict[str, int]] = {}
    tasks_cache = {}
    CONDITIONS = ["baseline", "schema_drift", "runtime_fault"]

    for suite, model in FINAL_RUNS:
        if suite not in tasks_cache:
            tasks_cache[suite] = task_lookup(suite)
        tasks = tasks_cache[suite]
        recs = load_parsed(suite, model)
        totals = per_model_totals.setdefault(model, {c: 0 for c in ALL_CAUSES} | {"intent_fail_n": 0, "explained_by_any": 0, "explained_by_none": 0})
        for cond in CONDITIONS:
            fail_keys = [k for k, p in recs.items() if p["condition"] == cond and not p["metrics"]["args_intent_match"]]
            n = len(fail_keys)
            per_cause = {c: 0 for c in ALL_CAUSES}
            any_n = none_n = 0
            for k in fail_keys:
                prec = recs[k]
                hit_any = False
                for c in ALL_CAUSES:
                    if relaxed_intent_for_record(tasks, prec, {c}):
                        per_cause[c] += 1
                        totals[c] += 1
                        hit_any = True
                if hit_any:
                    any_n += 1
                    totals["explained_by_any"] += 1
                else:
                    none_n += 1
                    totals["explained_by_none"] += 1
            totals["intent_fail_n"] += n
            lines.append(
                f"| {suite} | {model} | {cond} | {n} | {per_cause['properties_wrapper']} | "
                f"{per_cause['string_bool']} | {per_cause['unit_number']} | {per_cause['unit_synonym']} | "
                f"{per_cause['swapped_symmetric']} | {any_n} | {none_n} |"
            )

    lines.append("\n### Per-model totals (all conditions, both suites pooled)\n")
    lines.append("| model | intent_fail_n | properties_wrapper | string_bool | unit_number | unit_synonym | swapped_symmetric | explained_by_any | explained_by_none |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for model, t in per_model_totals.items():
        lines.append(
            f"| {model} | {t['intent_fail_n']} | {t['properties_wrapper']} | {t['string_bool']} | "
            f"{t['unit_number']} | {t['unit_synonym']} | {t['swapped_symmetric']} | {t['explained_by_any']} | {t['explained_by_none']} |"
        )

    # --- Part 2: relaxed-intent score recompute, check decision flips ---
    lines.append("\n## Part 2: relaxed-intent (all 5 causes) score recompute -- upgrade decision flips\n")
    lines.append(
        "Full score recomputed with `args_intent_match` relaxed for all 5 "
        "causes at once (all other components -- parse_ok, tool_name_ok, "
        "args_valid_under_drift, executor_ok -- exactly as already scored). "
        "Gate threshold 0.05, same convention as `docs/protocol.md` and "
        "every other table in this audit.\n"
    )
    lines.append("| suite | decision | strict stress diff | relaxed-intent stress diff | strict label | relaxed label | flip? |")
    lines.append("|---|---|---|---|---|---|---|")

    all_decision_rows = []
    new_flip_rows = []
    for suite in ("synthetic", "BFCL"):
        tasks = tasks_cache[suite]
        relaxed_scores: dict[str, dict] = {}
        for a, b in UPGRADE_PAIRS:
            for m in (a, b):
                if m not in relaxed_scores:
                    recs = load_parsed(suite, m)
                    relaxed_scores[m] = {k: relaxed_score_for_record(tasks, p, set(ALL_CAUSES)) for k, p in recs.items()}
        for a, b in UPGRADE_PAIRS:
            ra_strict, rb_strict = load_parsed(suite, a), load_parsed(suite, b)
            common_keys = sorted(set(ra_strict) & set(rb_strict))
            stress_keys = [k for k in common_keys if k[1] in STRESS]
            d_strict = mean_diff(ra_strict, rb_strict, stress_keys)
            ra_r, rb_r = relaxed_scores[a], relaxed_scores[b]
            d_relaxed = sum(rb_r[k] - ra_r[k] for k in stress_keys) / len(stress_keys)
            lab_strict, lab_relaxed = gate_label(d_strict), gate_label(d_relaxed)
            flipped = lab_strict != lab_relaxed
            pair_label = f"{a}->{b}"
            lines.append(
                f"| {suite} | {pair_label} | {d_strict:+.3f} | {d_relaxed:+.3f} | {lab_strict} | {lab_relaxed} | "
                f"{'**FLIP**' if flipped else 'no change'} |"
            )
            row = {
                "harness_choice": "Relaxed-intent (5 human-spot-check causes) fix -- CANDIDATE, not applied",
                "pair": pair_label, "suite": suite,
                "before": lab_strict, "after": lab_relaxed,
                "diff_before": d_strict, "diff_after": d_relaxed, "flipped": flipped,
            }
            all_decision_rows.append(row)
            if flipped:
                new_flip_rows.append(row)

    lines.append(f"\n**{len(new_flip_rows)} decision(s) flip under relaxed intent.**\n")

    out_path = Path(__file__).parent / "intent_strictness.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"{len(new_flip_rows)} flips found" + (":" if new_flip_rows else " (0/8 decisions flip)."))
    for r in new_flip_rows:
        print(" ", r)

    # --- Append all 8 decision rows to verdict_flips.md (consistent with
    # the fault-rescore candidate section, which also lists all 8 rows
    # even though it found 0 flips) ---
    vf_path = Path(__file__).parent / "verdict_flips.md"
    vf_text = vf_path.read_text(encoding="utf-8")
    table_lines = vf_text.splitlines()
    last_row_idx = max(i for i, l in enumerate(table_lines) if l.startswith("| ") and l[2].isdigit())
    last_num = int(table_lines[last_row_idx].split("|")[1].strip())
    insert_at = last_row_idx + 1
    new_lines = []
    for i, r in enumerate(all_decision_rows, start=last_num + 1):
        marker = "**FLIP**" if r["flipped"] else "no change"
        new_lines.append(
            f"| {i} | {r['harness_choice']} | {r['pair']} | {r['suite']} | {r['before']} | {r['after']} | "
            f"{marker} | {r['diff_before']:+.3f} -> {r['diff_after']:+.3f} |"
        )
    table_lines[insert_at:insert_at] = new_lines
    for i, l in enumerate(table_lines):
        if l.strip().startswith("**") and "rows are label flips" in l:
            import re as _re
            m = _re.search(r"\*\*(\d+) of (\d+) rows", l)
            if m:
                old_flips, old_total = int(m.group(1)), int(m.group(2))
                table_lines[i] = f"**{old_flips + len(new_flip_rows)} of {old_total + len(all_decision_rows)} rows are label flips.**"
            break
    table_lines.append("")
    table_lines.append("## Addendum: relaxed-intent (human spot-check) candidate fix")
    table_lines.append("")
    table_lines.append(
        f"Rows above (added {len(all_decision_rows)}, {len(new_flip_rows)} flips) come from "
        "`intent_strictness.md`'s relaxed-intent diagnostic (all 5 "
        "human-spot-check causes applied together: properties-wrapper, "
        "string-booleans, unit-attached-to-number, unit-synonyms, "
        "swapped-symmetric-args). Candidate only -- strict scoring "
        "remains official. Unlike escape-repair and the Qwen3 thinking-mode "
        "fix, this candidate changes no decision's gate label -- the "
        "biggest single-model effect (Mistral v0.2 on BFCL, where "
        "`properties`-wrapper alone explains 96 intent failures) moves "
        "both halves of each pair it's in roughly together, so the paired "
        "difference barely shifts."
    )
    vf_path.write_text("\n".join(table_lines) + "\n", encoding="utf-8")
    print(f"appended {len(all_decision_rows)} row(s) to {vf_path}")


if __name__ == "__main__":
    main()
