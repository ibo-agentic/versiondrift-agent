"""General-purpose version of scripts/f1_qwen3_bfcl_multiple_split.py
(2026-10-06): run any (protocol, model, suite) as two 50-task halves and
merge, for whenever a run is expected to or does exceed the ~2-hour
background-execution ceiling on this session. That ceiling is a tool/
infrastructure constraint, not a property of any experiment -- never a
reason to change a protocol's settings.

Why this is safe: every task's randomness is keyed by rng_for(seed,
task_id, condition) -- see upgradecanary/utils.py -- never by processing
order or position in the task list. Splitting the task file in half and
running each half under the SAME global seed and trial seeds produces
identical per-task generations to running all 100 together; only the
physical grouping into two subprocess calls differs. Proven directly in
scripts/prove_split_equivalence.py (90/90 records identical, D protocol,
gemma2_2b) -- the same mechanism applies to every protocol/model/suite.

Usage: python scripts/split_run.py <model_key> <suite> <protocol>
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

from scripts.real_run_models import MODEL_ORDER, SUITES  # noqa: E402
from scripts.real_run_one import build_config  # noqa: E402

SPLIT_ROOT = REPO_ROOT / "results_v2" / "_split_tmp"


def write_half(lines: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def existing_half_output(output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    for run_dir in output_dir.iterdir():
        if run_dir.is_dir() and (run_dir / "parsed_results.jsonl").exists():
            n = sum(1 for _ in open(run_dir / "parsed_results.jsonl", encoding="utf-8"))
            if n == 450:
                return run_dir
    return None


def run_half(model_key: str, gguf_path: str, suite: str, data_path: Path, protocol: str, half_name: str) -> dict:
    output_dir_rel = f"results_v2/_split_tmp/{protocol}_{model_key}_{suite}_{half_name}_output"
    output_dir_abs = REPO_ROOT / output_dir_rel
    existing = existing_half_output(output_dir_abs)
    if existing is not None:
        print(f"[{half_name}] already complete (450 records) -> {existing}, skipping.", flush=True)
        return {"run_dir": existing, "elapsed": 0.0}

    gen_cfg_dir = REPO_ROOT / "results_v2" / "_generated_configs"
    gen_cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = gen_cfg_dir / f"{protocol}__{model_key}__{suite}__{half_name}.yaml"
    cfg = build_config(
        model_key, gguf_path, suite, str(data_path.relative_to(REPO_ROOT)),
        protocol=protocol, output_dir=output_dir_rel,
    )
    with open(cfg_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False)

    print(f"[{half_name}] starting ({data_path.name}, output -> {output_dir_rel}) ...", flush=True)
    t0 = time.perf_counter()
    from upgradecanary.runner import run

    summary = run(str(cfg_path))
    elapsed = time.perf_counter() - t0
    print(f"[{half_name}] done: {summary.get('num_records')} records in {elapsed:.0f}s", flush=True)
    return {"run_dir": REPO_ROOT / output_dir_rel / summary["run_id"], "elapsed": elapsed}


def main(model_key: str, suite: str, protocol: str) -> int:
    gguf_path = dict(MODEL_ORDER)[model_key]
    source_data = REPO_ROOT / SUITES[suite]
    lines = source_data.read_text(encoding="utf-8").splitlines(keepends=True)
    assert len(lines) == 100, f"expected 100 tasks, got {len(lines)}"

    half1_path = SPLIT_ROOT / f"{model_key}_{suite}_half1.jsonl"
    half2_path = SPLIT_ROOT / f"{model_key}_{suite}_half2.jsonl"
    write_half(lines[:50], half1_path)
    write_half(lines[50:], half2_path)

    r1 = run_half(model_key, gguf_path, suite, half1_path, protocol, "half1")
    r2 = run_half(model_key, gguf_path, suite, half2_path, protocol, "half2")

    def load_jsonl(p: Path) -> list[dict]:
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    def record_key(row):
        return (
            row["task_id"], row["condition"],
            (row.get("drift") or {}).get("type", ""),
            (row.get("fault") or {}).get("type", ""),
            int(row.get("trial_index", 0)),
        )

    raw_merged = sorted(load_jsonl(r1["run_dir"] / "raw_outputs.jsonl") + load_jsonl(r2["run_dir"] / "raw_outputs.jsonl"), key=record_key)
    parsed_merged = sorted(load_jsonl(r1["run_dir"] / "parsed_results.jsonl") + load_jsonl(r2["run_dir"] / "parsed_results.jsonl"), key=record_key)

    from upgradecanary.evaluator import summarize
    from upgradecanary.utils import write_json, write_jsonl

    summary = summarize(parsed_merged)
    half1_manifest = json.loads((r1["run_dir"] / "run_manifest.json").read_text(encoding="utf-8"))
    merged_run_id = half1_manifest["run_id"].replace("-half1-", "-merged-")
    final_output_dir = REPO_ROOT / "results_v2" / protocol / model_key / suite
    final_run_dir = final_output_dir / merged_run_id
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
        f"Split into two 50-task halves and merged (protocol {protocol}, "
        f"model {model_key}, suite {suite}) due to a 2-hour background-"
        "execution ceiling on this session (not a protocol change) -- see "
        "scripts/split_run.py and DEVIATIONS.md. Per-task randomness is "
        "keyed by (seed, task_id, condition), never by processing order, "
        "so this is byte-identical to one unsplit invocation (proven in "
        "scripts/prove_split_equivalence.py)."
    )
    write_json(final_run_dir / "run_manifest.json", manifest)

    status = {
        "model_key": model_key, "suite": suite, "protocol": protocol,
        "completed": len(parsed_merged) == 900,
        "run_id": merged_run_id, "run_dir": str(final_run_dir),
        "num_records": len(parsed_merged), "expected_records": 900,
        "record_count_ok": len(parsed_merged) == 900,
        "elapsed_seconds": r1["elapsed"] + r2["elapsed"],
        "split_run": True,
    }
    write_json(final_output_dir / "_status.json", status)

    print(f"\nMerged {len(parsed_merged)} records -> {final_run_dir}")
    return 0 if status["completed"] else 1


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python scripts/split_run.py <model_key> <suite> <protocol>")
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
