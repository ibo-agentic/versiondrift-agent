"""Proof (2026-10-06, DEVIATIONS.md item A): running a task set as one
run vs. as two halves produces byte-identical records, for any model --
not just asserted, demonstrated directly. Uses gemma2_2b/synthetic, 10
tasks, under protocol D (the exact mechanism used for the real
qwen3/bfcl_multiple F1 split). Writes both to a throwaway scratch
location, never touching any real results_v2/<protocol>/ data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "analysis" / "audit"))
import _dll_preload  # noqa: E402

_dll_preload.preload()

import yaml  # noqa: E402

from scripts.real_run_models import MODEL_ORDER  # noqa: E402
from scripts.real_run_one import build_config  # noqa: E402

MODEL_KEY = "gemma2_2b"
GGUF_PATH = dict(MODEL_ORDER)[MODEL_KEY]
SOURCE_DATA = REPO_ROOT / "data" / "base_tasks.jsonl"
SCRATCH = REPO_ROOT / "results_v2" / "_proof_scratch"


def run_cfg(data_path: Path, output_dir: str, tag: str) -> Path:
    gen_cfg_dir = SCRATCH / "configs"
    gen_cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = gen_cfg_dir / f"{tag}.yaml"
    cfg = build_config(
        MODEL_KEY, GGUF_PATH, "synthetic", str(data_path.relative_to(REPO_ROOT)),
        protocol="D", output_dir=output_dir,
    )
    with open(cfg_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False)
    print(f"[{tag}] running...", flush=True)
    from upgradecanary.runner import run

    summary = run(str(cfg_path))
    run_dir = REPO_ROOT / output_dir / summary["run_id"]
    print(f"[{tag}] done: {summary.get('num_records')} records -> {run_dir}", flush=True)
    return run_dir


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def record_key(row: dict) -> tuple:
    return (
        row["task_id"], row["condition"],
        (row.get("drift") or {}).get("type", ""),
        (row.get("fault") or {}).get("type", ""),
        int(row.get("trial_index", 0)),
    )


def main() -> int:
    lines = SOURCE_DATA.read_text(encoding="utf-8").splitlines(keepends=True)[:10]
    ten_path = SCRATCH / "ten_tasks.jsonl"
    ten_path.parent.mkdir(parents=True, exist_ok=True)
    ten_path.write_text("".join(lines), encoding="utf-8")
    half1_path = SCRATCH / "half1.jsonl"
    half2_path = SCRATCH / "half2.jsonl"
    half1_path.write_text("".join(lines[:5]), encoding="utf-8")
    half2_path.write_text("".join(lines[5:]), encoding="utf-8")

    whole_dir = run_cfg(ten_path, "results_v2/_proof_scratch/whole", "whole")
    half1_dir = run_cfg(half1_path, "results_v2/_proof_scratch/half1", "half1")
    half2_dir = run_cfg(half2_path, "results_v2/_proof_scratch/half2", "half2")

    whole_parsed = sorted(load_jsonl(whole_dir / "parsed_results.jsonl"), key=record_key)
    split_parsed = sorted(
        load_jsonl(half1_dir / "parsed_results.jsonl") + load_jsonl(half2_dir / "parsed_results.jsonl"),
        key=record_key,
    )
    whole_raw = sorted(load_jsonl(whole_dir / "raw_outputs.jsonl"), key=record_key)
    split_raw = sorted(
        load_jsonl(half1_dir / "raw_outputs.jsonl") + load_jsonl(half2_dir / "raw_outputs.jsonl"),
        key=record_key,
    )

    print(f"\nwhole: {len(whole_parsed)} parsed records, {len(whole_raw)} raw records")
    print(f"split (merged): {len(split_parsed)} parsed records, {len(split_raw)} raw records")

    parsed_identical = whole_parsed == split_parsed
    # raw_outputs includes "run_id" which legitimately differs between the
    # whole and split runs -- strip it before comparing, everything else
    # (prompt, raw_output, truncated, prompt_sha256) must still match.
    def strip_run_id(rows):
        return [{k: v for k, v in r.items() if k != "run_id"} for r in rows]

    raw_identical = strip_run_id(whole_raw) == strip_run_id(split_raw)

    print(f"\nparsed_results.jsonl identical (sorted): {parsed_identical}")
    print(f"raw_outputs.jsonl identical (sorted, excl. run_id): {raw_identical}")

    if not parsed_identical:
        for w, s in zip(whole_parsed, split_parsed):
            if w != s:
                print("FIRST MISMATCH (parsed):")
                print("  whole:", w)
                print("  split:", s)
                break
    if not raw_identical:
        for w, s in zip(strip_run_id(whole_raw), strip_run_id(split_raw)):
            if w != s:
                print("FIRST MISMATCH (raw):")
                print("  whole:", w)
                print("  split:", s)
                break

    return 0 if (parsed_identical and raw_identical) else 1


if __name__ == "__main__":
    sys.exit(main())
