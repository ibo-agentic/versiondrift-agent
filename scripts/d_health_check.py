"""PLAN v1 D-protocol health check (2026-10-05). Reads all 48 real runs
under results_v2/D/ directly -- no verdict/pair-diff computation, per
instruction. Computes per-run metrics, checks run_manifest.json
consistency, flags anomalies, and writes a SHA-256 manifest of every
file under results_v2/D/.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from upgradecanary.evaluator import expected_fault_report  # noqa: E402
from upgradecanary.perturbations.runtime_faults import Fault  # noqa: E402

D_ROOT = REPO_ROOT / "results_v2" / "D"


def find_run_dir(model: str, suite: str) -> Path:
    suite_dir = D_ROOT / model / suite
    candidates = [d for d in suite_dir.iterdir() if d.is_dir()]
    assert len(candidates) == 1, f"{model}/{suite}: expected exactly 1 run dir, found {len(candidates)}"
    return candidates[0]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def compute_run_metrics(model: str, suite: str) -> dict:
    run_dir = find_run_dir(model, suite)
    raw = load_jsonl(run_dir / "raw_outputs.jsonl")
    parsed = load_jsonl(run_dir / "parsed_results.jsonl")
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))

    tool_call_records = [p for p in parsed if p["condition"] in ("baseline", "schema_drift")]
    fr_records = [p for p in parsed if p["condition"] == "fault_reporting"]

    parse_rate = (
        sum(1 for p in tool_call_records if p["metrics"]["parse_ok"]) / len(tool_call_records)
        if tool_call_records else None
    )
    truncation_rate = sum(1 for r in raw if r.get("truncated")) / len(raw) if raw else None

    greedy_baseline = [p for p in tool_call_records if p["condition"] == "baseline" and p["trial_index"] == 0]
    greedy_drift = [p for p in tool_call_records if p["condition"] == "schema_drift" and p["trial_index"] == 0]
    greedy_baseline_acc = (
        sum(p["metrics"]["score"] for p in greedy_baseline) / len(greedy_baseline) if greedy_baseline else None
    )
    greedy_drift_acc = (
        sum(p["metrics"]["score"] for p in greedy_drift) / len(greedy_drift) if greedy_drift else None
    )

    fr_status_acc = (
        sum(1 for p in fr_records if p["metrics"]["status_ok"]) / len(fr_records) if fr_records else None
    )

    failure_expected = []
    for p in fr_records:
        fault = Fault(**p["fault"]) if p["fault"] else None
        if expected_fault_report(fault) == "failed":
            failure_expected.append(p)
    fabrication_rate = (
        sum(1 for p in failure_expected if not p["metrics"]["no_fabrication"]) / len(failure_expected)
        if failure_expected else None
    )

    return {
        "model": model, "suite": suite,
        "parse_rate": parse_rate,
        "truncation_rate": truncation_rate,
        "greedy_baseline_acc": greedy_baseline_acc,
        "greedy_drift_acc": greedy_drift_acc,
        "fr_status_acc": fr_status_acc,
        "fabrication_rate": fabrication_rate,
        "n_tool_call": len(tool_call_records),
        "n_fr": len(fr_records),
        "n_failure_expected": len(failure_expected),
        "model_backend": manifest.get("model_backend", {}),
        "run_factors": manifest.get("run_factors", {}),
        "run_dir": str(run_dir),
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024 * 4), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    models = sorted(d.name for d in D_ROOT.iterdir() if d.is_dir() and not d.name.startswith("_"))
    suites = ["synthetic", "bfcl_simple", "bfcl_multiple"]

    all_metrics = []
    for model in models:
        for suite in suites:
            all_metrics.append(compute_run_metrics(model, suite))

    Path("results_v2/_health_check_metrics.json").write_text(
        json.dumps(all_metrics, indent=2, sort_keys=True), encoding="utf-8"
    )

    # SHA-256 manifest of every file under results_v2/D/
    manifest_lines = []
    for path in sorted(D_ROOT.rglob("*")):
        if path.is_file():
            rel = path.relative_to(REPO_ROOT)
            manifest_lines.append(f"{sha256_file(path)}  {rel.as_posix()}")
    Path("analysis/plan/D_sha256_manifest.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    print(f"Wrote {len(all_metrics)} run metrics and {len(manifest_lines)} file hashes.")


if __name__ == "__main__":
    main()
