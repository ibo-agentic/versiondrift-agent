"""AUDIT questions E (10-13): runtime-fault scoring mechanics on real logs.

Read-only. For each model's runtime_fault records:
- breaks down outcome by fault.type (stale_result vs the four retryable types)
- for retryable faults, checks whether first-attempt exec was forced to fail
  by apply_fault even when args were valid (upgradecanary/tools.py apply_fault,
  always returns ok=False for timeout/tool_exception/empty_result/partial_result)
- computes baseline-vs-fault paired flip counts per model (synthetic suite)
- prints concrete failing fault-condition examples for Mistral v0.2 and Qwen3
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import load_parsed, load_raw, sc  # noqa: E402

RETRYABLE = ("timeout", "tool_exception", "empty_result", "partial_result")


def fault_type_breakdown(suite: str, model: str) -> None:
    recs = load_parsed(suite, model)
    rows = [r for r in recs.values() if r["condition"] == "runtime_fault"]
    print(f"\n--- {suite} {model}: runtime_fault outcome by fault.type ---")
    by_type: dict[str, list] = {}
    for r in rows:
        ft = (r.get("fault") or {}).get("type", "?")
        by_type.setdefault(ft, []).append(r)
    for ft, rs in sorted(by_type.items()):
        n = len(rs)
        score_mean = sum(sc(r) for r in rs) / n
        exec_result = [r["exec_result"] for r in rs]
        had_retry = sum(1 for e in exec_result if isinstance(e, dict) and "retry" in e)
        first_fail_but_valid_args = sum(
            1
            for r, e in zip(rs, exec_result)
            if isinstance(e, dict) and "first_attempt" in e
            and e["first_attempt"].get("ok") is False
            and r["metrics"]["args_valid_under_drift"]
        )
        print(
            f"  {ft:15} n={n:3} mean_score={score_mean:.3f} retried={had_retry:3} "
            f"(valid_first_attempt_forced_to_fail={first_fail_but_valid_args:3})"
        )


def baseline_vs_fault_flips(suite: str, model: str) -> None:
    recs = load_parsed(suite, model)
    by_key = {}
    for r in recs.values():
        by_key[(r["task_id"], r["condition"], r["trial_index"])] = r
    base_keys = [k for k in by_key if k[1] == "baseline"]
    neg = pos = same_pass = same_fail = 0
    for (tid, _, ti) in base_keys:
        b = by_key.get((tid, "baseline", ti))
        f = by_key.get((tid, "runtime_fault", ti))
        if b is None or f is None:
            continue
        bs, fs = sc(b), sc(f)
        if bs == 1 and fs == 0:
            neg += 1
        elif bs == 0 and fs == 1:
            pos += 1
        elif bs == 1 and fs == 1:
            same_pass += 1
        else:
            same_fail += 1
    print(
        f"{suite:9} {model:12}: baseline->fault flips: pass->fail={neg:3} fail->pass={pos:3} "
        f"both_pass={same_pass:3} both_fail={same_fail:3}"
    )


def show_examples(suite: str, model: str, n: int = 3) -> None:
    recs = load_parsed(suite, model)
    raw = load_raw(suite, model)
    rows = [r for r in recs.values() if r["condition"] == "runtime_fault" and sc(r) == 0.0]
    print(f"\n=== {n} failing runtime_fault examples: {suite} {model} ===")
    shown = 0
    for r in rows:
        if shown >= n:
            break
        key = (r["task_id"], "runtime_fault", r["trial_index"])
        rawrow = raw.get(key, {})
        print(f"\n-- {r['task_id']} trial={r['trial_index']} fault={ (r.get('fault') or {}).get('type') } --")
        print(f"metrics: {r['metrics']}")
        print(f"exec_result: {r['exec_result']}")
        print(f"prompt (first 300 chars): {rawrow.get('prompt','')[:300]!r}")
        print(f"raw_output (first 300 chars): {rawrow.get('raw_output','')[:300]!r}")
        if rawrow.get("retry_raw_output"):
            print(f"retry_raw_output (first 300 chars): {rawrow.get('retry_raw_output','')[:300]!r}")
        shown += 1


def main() -> None:
    for suite, model in [("synthetic", "Mistral v0.1"), ("synthetic", "Mistral v0.2"),
                          ("synthetic", "Mistral v0.3"), ("synthetic", "Qwen2.5"), ("synthetic", "Qwen3")]:
        fault_type_breakdown(suite, model)

    print("\n=== Q12: baseline vs runtime_fault paired flips (synthetic suite) ===")
    for suite, model in [("synthetic", "Mistral v0.1"), ("synthetic", "Mistral v0.2"),
                          ("synthetic", "Mistral v0.3"), ("synthetic", "Qwen2.5"), ("synthetic", "Qwen3")]:
        baseline_vs_fault_flips(suite, model)
    print("\n=== Q12: baseline vs runtime_fault paired flips (BFCL suite) ===")
    for suite, model in [("BFCL", "Mistral v0.1"), ("BFCL", "Mistral v0.2"),
                          ("BFCL", "Mistral v0.3"), ("BFCL", "Qwen2.5"), ("BFCL", "Qwen3")]:
        baseline_vs_fault_flips(suite, model)

    show_examples("synthetic", "Mistral v0.2", 3)
    show_examples("synthetic", "Qwen3", 3)


if __name__ == "__main__":
    main()
