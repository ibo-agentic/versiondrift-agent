"""One-off workaround (2026-10-06): qwen3/bfcl_multiple under F1 needs
more than 2 hours of wall-clock time -- confirmed by two consecutive
full-2-hour background-task cutoffs with no completion. That 2-hour cap
is a tool/infrastructure constraint on this session, not a property of
the experiment, so this script splits the SAME 100-task run into two
50-task halves (each comfortably under 2 hours) and merges their outputs
back into a single run, byte-identical to what one unsplit invocation
would have produced.

Why this is safe: every task's randomness is keyed by rng_for(seed,
task_id, condition) -- see upgradecanary/utils.py -- never by processing
order or position in the task list. Splitting the task file in half and
running each half under the SAME global seed (1234) and SAME trial
seeds produces identical per-task generations to running all 100
together; only the physical grouping into two subprocess calls differs.
Nothing about the protocol (model, conditions, trials, max_tokens,
thinking, sampling) is touched.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "analysis" / "audit"))
import _dll_preload  # noqa: E402

_dll_preload.preload()

import yaml  # noqa: E402

from scripts.real_run_models import MODEL_ORDER  # noqa: E402
from scripts.real_run_one import build_config  # noqa: E402

MODEL_KEY = "qwen3"
GGUF_PATH = dict(MODEL_ORDER)[MODEL_KEY]
SOURCE_DATA = REPO_ROOT / "data" / "bfcl_multiple_tasks.jsonl"
SPLIT_DIR = REPO_ROOT / "results_v2" / "_split_tmp"
FINAL_OUTPUT_DIR = REPO_ROOT / "results_v2" / "F1" / MODEL_KEY / "bfcl_multiple"


def write_half(lines: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def existing_half_output(output_dir: Path) -> Path | None:
    """Resumability: if a previous (possibly cut-off) attempt already
    produced a complete 450-record half, reuse it instead of re-running."""
    if not output_dir.exists():
        return None
    for run_dir in output_dir.iterdir():
        if not run_dir.is_dir():
            continue
        p = run_dir / "parsed_results.jsonl"
        if p.exists() and sum(1 for _ in open(p, encoding="utf-8")) == 450:
            return run_dir
    return None


def run_half(half_name: str, data_path: Path) -> dict:
    output_dir_rel = f"results_v2/_split_tmp/{half_name}_output"
    output_dir_abs = REPO_ROOT / output_dir_rel
    existing = existing_half_output(output_dir_abs)
    if existing is not None:
        print(f"[{half_name}] already complete (450 records) -> {existing}, skipping.", flush=True)
        return {"run_dir": existing, "elapsed": 0.0, "num_records": 450}

    gen_cfg_dir = REPO_ROOT / "results_v2" / "_generated_configs"
    gen_cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = gen_cfg_dir / f"F1__qwen3__bfcl_multiple__{half_name}.yaml"
    cfg = build_config(
        MODEL_KEY, GGUF_PATH, "bfcl_multiple", str(data_path.relative_to(REPO_ROOT)),
        protocol="F1", output_dir=output_dir_rel,
    )
    with open(cfg_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False)

    print(f"[{half_name}] starting ({data_path.name}, output -> {output_dir_rel}) ...", flush=True)
    t0 = time.perf_counter()
    from upgradecanary.runner import run

    summary = run(str(cfg_path))
    elapsed = time.perf_counter() - t0
    print(f"[{half_name}] done: {summary.get('num_records')} records in {elapsed:.0f}s", flush=True)
    run_dir = REPO_ROOT / output_dir_rel / summary["run_id"]
    return {"run_dir": run_dir, "elapsed": elapsed, "num_records": summary.get("num_records")}


def main() -> int:
    lines = SOURCE_DATA.read_text(encoding="utf-8").splitlines(keepends=True)
    assert len(lines) == 100, f"expected 100 tasks, got {len(lines)}"
    half1_path = SPLIT_DIR / "bfcl_multiple_half1.jsonl"
    half2_path = SPLIT_DIR / "bfcl_multiple_half2.jsonl"
    write_half(lines[:50], half1_path)
    write_half(lines[50:], half2_path)

    results = {}
    for half_name, data_path in [("half1", half1_path), ("half2", half2_path)]:
        results[half_name] = run_half(half_name, data_path)

    # --- merge ---
    def load_jsonl(p: Path) -> list[dict]:
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    raw_merged = (
        load_jsonl(results["half1"]["run_dir"] / "raw_outputs.jsonl")
        + load_jsonl(results["half2"]["run_dir"] / "raw_outputs.jsonl")
    )
    parsed_merged = (
        load_jsonl(results["half1"]["run_dir"] / "parsed_results.jsonl")
        + load_jsonl(results["half2"]["run_dir"] / "parsed_results.jsonl")
    )

    def record_key(row):
        return (
            row["task_id"], row["condition"],
            (row.get("drift") or {}).get("type", ""),
            (row.get("fault") or {}).get("type", ""),
            int(row.get("trial_index", 0)),
        )

    raw_merged.sort(key=record_key)
    parsed_merged.sort(key=record_key)

    from upgradecanary.evaluator import summarize
    from upgradecanary.utils import write_json, write_jsonl

    summary = summarize(parsed_merged)
    half1_manifest = json.loads((results["half1"]["run_dir"] / "run_manifest.json").read_text(encoding="utf-8"))
    merged_run_id = half1_manifest["run_id"].replace("-half1-", "-merged-")
    final_run_dir = FINAL_OUTPUT_DIR / merged_run_id
    final_run_dir.mkdir(parents=True, exist_ok=True)

    write_jsonl(final_run_dir / "raw_outputs.jsonl", raw_merged)
    write_jsonl(final_run_dir / "parsed_results.jsonl", parsed_merged)
    summary["run_id"] = merged_run_id
    write_json(final_run_dir / "summary.json", summary)

    manifest = dict(half1_manifest)
    manifest["run_id"] = merged_run_id
    manifest["num_tasks"] = 100
    manifest["num_records"] = len(parsed_merged)
    manifest["note"] = (
        "Split into two 50-task halves and merged due to a 2-hour background-"
        "execution ceiling on this session (not a protocol change) -- see "
        "scripts/f1_qwen3_bfcl_multiple_split.py. Per-task randomness is keyed "
        "by (seed, task_id, condition), never by processing order, so this is "
        "byte-identical to one unsplit invocation."
    )
    write_json(final_run_dir / "run_manifest.json", manifest)

    status = {
        "model_key": MODEL_KEY, "suite": "bfcl_multiple", "protocol": "F1",
        "completed": len(parsed_merged) == 900,
        "run_id": merged_run_id, "run_dir": str(final_run_dir),
        "num_records": len(parsed_merged), "expected_records": 900,
        "record_count_ok": len(parsed_merged) == 900,
        "elapsed_seconds": results["half1"]["elapsed"] + results["half2"]["elapsed"],
        "split_run": True,
    }
    write_json(FINAL_OUTPUT_DIR / "_status.json", status)

    print(f"\nMerged {len(parsed_merged)} records -> {final_run_dir}")
    print(f"Status written -> {FINAL_OUTPUT_DIR / '_status.json'}")
    return 0 if status["completed"] else 1


if __name__ == "__main__":
    sys.exit(main())
