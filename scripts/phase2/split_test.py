"""Split-equivalence test for adding trials (PLAN_PHASE2.md W0 / W3 preconditions).

    python -m scripts.phase2.split_test --model gemma2_2b --suite synthetic --protocol D --n-tasks 10

Question: is one run with trial seeds 1234-1243 the same as a run with seeds 1234-1236 plus a separate run with
seeds 1237-1243? Both are made with the protocol's own config (first N tasks of the suite, run seed 1234):

  A   one run, 10 trials   (seeds 1234-1243, temperatures 0, 0.7 x 9)
  B1  one run, 3 trials    (seeds 1234-1236, temperatures 0, 0.7, 0.7)       Phase 1's layout
  B2  one run, 7 trials    (seeds 1237-1243, temperatures 0.7 x 7)           the Phase 2 add-on

B1 and B2 are put on one trial axis (B2's trial_index + 3). For every trial the records of A and of B are compared
(prompt, raw output byte for byte, parsed call, strict score). Writes <out>/split_test_result.json,
<out>/<protocol>_result.json (``all_identical`` is what the W3 gate reads) and <out>/split_test_report.md.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "analysis" / "audit"))

from scripts.phase2.build import apply_trials, write_config  # noqa: E402

RUN_SEED = 1234
SCHEMES = {
    "A": ([RUN_SEED + i for i in range(10)], [0.0] + [0.7] * 9),
    "B1": ([RUN_SEED + i for i in range(3)], [0.0, 0.7, 0.7]),
    "B2": ([RUN_SEED + 3 + i for i in range(7)], [0.7] * 7),
}
TRIAL_OFFSET = {"A": 0, "B1": 0, "B2": 3}
DEFAULT_OUT = Path("results_v3/W0_determinism/split_test")


def _read(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def canon(x: Any) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def load_records(run_dir: Path, offset: int = 0) -> dict[tuple, dict]:
    raw = {(r["task_id"], r["condition"], int(r["trial_index"])): r for r in _read(run_dir / "raw_outputs.jsonl")}
    out = {}
    for p in _read(run_dir / "parsed_results.jsonl"):
        k = (p["task_id"], p["condition"], int(p["trial_index"]))
        r = raw[k]
        out[(k[0], k[1], k[2] + offset)] = {"raw_output": r["raw_output"], "prompt_sha256": r.get("prompt_sha256"),
                                           "parsed_call": canon(p.get("parsed_call")), "score": p["metrics"]["score"],
                                           "temperature": p.get("temperature"), "seed": p.get("seed")}
    return out


def compare_split(a: dict[tuple, dict], b: dict[tuple, dict]) -> dict[str, Any]:
    """Per merged trial index, and for greedy / sampled / all: % identical prompt, raw output, parsed call, score."""
    keys = sorted(set(a) & set(b))
    groups: dict[str, list[int]] = {}
    examples = []
    for k in keys:
        t = k[2]
        for g in (f"trial_{t}", "greedy" if a[k]["temperature"] == 0 else "sampled", "all"):
            c = groups.setdefault(g, [0, 0, 0, 0, 0])
            c[0] += 1
            c[1] += a[k]["prompt_sha256"] == b[k]["prompt_sha256"]
            c[2] += a[k]["raw_output"] == b[k]["raw_output"]
            c[3] += a[k]["parsed_call"] == b[k]["parsed_call"]
            c[4] += a[k]["score"] == b[k]["score"]
        if a[k]["raw_output"] != b[k]["raw_output"] and len(examples) < 3:
            examples.append({"key": list(k), "a": a[k]["raw_output"], "b": b[k]["raw_output"]})
    res = {g: {"n": c[0], "pct_prompt_identical": 100 * c[1] / c[0], "pct_raw_identical": 100 * c[2] / c[0],
               "pct_parsed_identical": 100 * c[3] / c[0], "pct_score_identical": 100 * c[4] / c[0]}
           for g, c in groups.items()}
    return {"n_a": len(a), "n_b": len(b), "n_matched": len(keys), "groups": res, "examples": examples,
            "all_identical": len(a) == len(b) == len(keys) and all(
                v["pct_prompt_identical"] == v["pct_raw_identical"] == v["pct_parsed_identical"]
                == v["pct_score_identical"] == 100 for v in res.values())}


def make_subset(data: str, n_tasks: int, dest: Path, root: Path = REPO_ROOT) -> Path:
    lines = [l for l in (root / data).read_text(encoding="utf-8").splitlines() if l.strip()][:n_tasks]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def run_split_test(model: str, suite: str, protocol: str, n_tasks: int, out: Path = DEFAULT_OUT,
                   root: Path = REPO_ROOT, runner: Callable[[str], dict] | None = None,
                   gguf: str | None = None) -> dict[str, Any]:
    from scripts.real_run_models import MODEL_ORDER, SUITES
    from scripts.real_run_one import build_config

    out = Path(out)
    path = gguf or dict(MODEL_ORDER)[model]
    subset = make_subset(SUITES[suite], n_tasks, root / out / f"tasks_first{n_tasks}.jsonl", root)
    if runner is None:
        import os
        os.chdir(root)
        import _dll_preload

        _dll_preload.preload()
        from upgradecanary.runner import run as runner
    runs, timings = {}, {}
    for name, (seeds, temps) in SCHEMES.items():
        cfg = build_config(model, path, suite, (out / subset.name).as_posix(), protocol=protocol,
                           output_dir=(out / protocol / name).as_posix())
        apply_trials(cfg, seeds, temps)
        cfg["experiment"] = f"split-test-{protocol}-{model}-{suite}-{name}"
        cfg_path = write_config(cfg, root / out / "configs" / f"{protocol}__{name}.yaml")
        t0 = time.perf_counter()
        summary = runner(str(cfg_path))
        timings[name] = time.perf_counter() - t0
        runs[name] = {"run_dir": str(root / out / protocol / name / summary["run_id"]), "num_records": summary["num_records"],
                      "expected_records": n_tasks * 3 * len(seeds), "seeds": seeds, "wall_clock_seconds": timings[name]}
        print(f"[{name}] {summary['num_records']} records in {timings[name]:.0f}s", flush=True)
    a = load_records(Path(runs["A"]["run_dir"]))
    b = {**load_records(Path(runs["B1"]["run_dir"]), 0), **load_records(Path(runs["B2"]["run_dir"]), 3)}
    if len(b) != len(load_records(Path(runs["B1"]["run_dir"]))) + len(load_records(Path(runs["B2"]["run_dir"]), 3)):
        raise RuntimeError("B1 and B2 overlap on the merged trial axis")
    res = {"model": model, "suite": suite, "protocol": protocol, "n_tasks": n_tasks, "runs": runs,
           **compare_split(a, b)}
    (root / out).mkdir(parents=True, exist_ok=True)
    (root / out / "split_test_result.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (root / out / f"{protocol}_result.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (root / out / "split_test_report.md").write_text(report(res), encoding="utf-8")
    return res


def report(res: dict[str, Any]) -> str:
    lines = [f"# Split test: {res['protocol']} / {res['model']} / {res['suite']}, first {res['n_tasks']} tasks", "",
             "A = one run, trial seeds 1234-1243. B = run 1234-1236 + separate run 1237-1243, on one trial axis.", "",
             "| run | records | expected | wall-clock s |", "|---|---|---|---|"]
    for n, r in res["runs"].items():
        lines.append(f"| {n} | {r['num_records']} | {r['expected_records']} | {r['wall_clock_seconds']:.0f} |")
    lines += ["", f"matched records: {res['n_matched']} (A {res['n_a']}, B {res['n_b']}); all identical: {res['all_identical']}", "",
              "| group | n | prompt % | raw output % | parsed call % | strict score % |", "|---|---|---|---|---|---|"]
    order = [f"trial_{i}" for i in range(10)] + ["greedy", "sampled", "all"]
    for g in order:
        v = res["groups"].get(g)
        if v:
            lines.append(f"| {g} | {v['n']} | {v['pct_prompt_identical']:.2f} | {v['pct_raw_identical']:.2f} | "
                         f"{v['pct_parsed_identical']:.2f} | {v['pct_score_identical']:.2f} |")
    for ex in res["examples"]:
        lines += ["", f"differing record {ex['key']}:", f"- A: {ex['a']!r}", f"- B: {ex['b']!r}"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="gemma2_2b")
    ap.add_argument("--suite", default="synthetic")
    ap.add_argument("--protocol", default="D")
    ap.add_argument("--n-tasks", type=int, default=10)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)
    res = run_split_test(args.model, args.suite, args.protocol, args.n_tasks, Path(args.out))
    print(report(res))
    return 0 if res["all_identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
