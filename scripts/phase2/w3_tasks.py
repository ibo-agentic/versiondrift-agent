"""W3 added-task files for the BFCL suites (PLAN_PHASE2.md W3). No model is run.

    python -m scripts.phase2.w3_tasks            # writes data/phase2/w3_added_bfcl_{simple,multiple}.jsonl (+ provenance)
    python -m scripts.phase2.w3_tasks --check    # verify the written files, write nothing

bfcl_simple: the eligible items that the frozen 100-task selection did not take (191 - 100 = 91).
bfcl_multiple: the same for the 3500-character rule (109 - 100 = 9). Eligibility is exactly the rules that
produced the original files (upgradecanary.bfcl.is_eligible / is_eligible_multiple, including the
one-task-per-function rule); nothing is loosened. The code re-derives the original selection first and refuses
to continue unless it is byte-identical to data/bfcl_tasks.jsonl / data/bfcl_multiple_tasks.jsonl, so the
"remaining" items are remaining relative to the files actually used in Phase 1.
Task ids are the upstream ids (bfcl-simple_python_N / bfcl-multiple-multiple_N), sorted like the originals.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from upgradecanary import bfcl  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "phase2"
MULTIPLE_MAX_PROMPT_CHARS = 3500            # PLAN.md: the eligibility budget of BFCL-multiple-100
KINDS = {
    "simple": {"suite": "bfcl_simple", "original": "bfcl_tasks", "protocol": "UpgradeCanary-BFCL-100 selection protocol (docs/protocol.md)"},
    "multiple": {"suite": "bfcl_multiple", "original": "bfcl_multiple_tasks",
                 "protocol": "UpgradeCanary-BFCL-multiple-100 selection protocol (docs/protocol.md)"},
}
W3_PROTOCOL = "PLAN_PHASE2.md W3: eligible items not in the Phase 1 100-task selection (same eligibility filters)"


def eligible_items(kind: str, root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    """The eligible items exactly as bfcl.generate / bfcl.generate_multiple build them (before selection)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    if kind == "simple":
        records = bfcl.load_jsonl(root / bfcl.SOURCE_REL)
        answers = {a["id"]: a for a in bfcl.load_jsonl(root / bfcl.ANSWERS_REL)}
        for r in records:
            a = answers.get(r["id"])
            ok, _ = bfcl.is_eligible(r, a)
            fn = r["function"][0]["name"]
            if not ok or fn in seen:
                continue
            seen.add(fn)
            out.append({"task": bfcl.convert(r, a), "signature": bfcl.type_signature(r["function"][0], a["ground_truth"][0][fn]),
                        "source_id": r["id"], "function": fn})
    else:
        records = bfcl.load_jsonl(root / bfcl.MULTIPLE_SOURCE_REL)
        answers = {a["id"]: a for a in bfcl.load_jsonl(root / bfcl.MULTIPLE_ANSWERS_REL)}
        for r in records:
            a = answers.get(r["id"])
            ok, _ = bfcl.is_eligible_multiple(r, a, max_prompt_chars=MULTIPLE_MAX_PROMPT_CHARS)
            if not ok:
                continue
            truth = next(iter(a["ground_truth"][0]))
            fn = bfcl.find_correct_function(r["function"], truth)
            if fn["name"] in seen:
                continue
            seen.add(fn["name"])
            out.append({"task": bfcl.convert_multiple(r, a),
                        "signature": f"{bfcl.type_signature(fn, a['ground_truth'][0][truth])},n{len(r['function'])}",
                        "source_id": r["id"], "function": fn["name"]})
    return out


def _lines(path: Path) -> list[str]:
    return [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def original_task_lines(kind: str, root: Path = REPO_ROOT) -> list[str]:
    return _lines(root / "data" / f"{KINDS[kind]['original']}.jsonl")


def remaining_items(kind: str, root: Path = REPO_ROOT) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(all eligible items, the ones not in the original 100). Refuses unless the original selection is reproduced."""
    eligible = eligible_items(kind, root)
    selected, _ = bfcl.select_tasks(eligible)
    reproduced = [json.dumps(it["task"], ensure_ascii=False) for it in selected]
    if reproduced != original_task_lines(kind, root):
        raise RuntimeError(f"the re-derived {kind} selection is not byte-identical to the original task file; "
                           "the eligibility rules or the source data changed")
    taken = {it["task"]["task_id"] for it in selected}
    rest = sorted((it for it in eligible if it["task"]["task_id"] not in taken), key=lambda it: it["task"]["task_id"])
    return eligible, rest


def provenance_row(kind: str, item: dict[str, Any]) -> dict[str, Any]:
    row = {"task_id": item["task"]["task_id"], "source_id": item["source_id"], "function": item["function"],
           "signature": item["signature"], "question_chars": len(item["task"]["prompt"]), "suite": "bfcl",
           "protocol": W3_PROTOCOL, "original_protocol": KINDS[kind]["protocol"], "w3_added": True}
    if kind == "multiple":
        row["num_candidates"] = len(item["task"]["candidate_schemas"])
    return row


def path_for(kind: str, provenance: bool = False, out_dir: Path = OUT_DIR) -> Path:
    return out_dir / f"w3_added_{KINDS[kind]['suite']}{'_provenance' if provenance else ''}.jsonl"


def write_added(kind: str, root: Path = REPO_ROOT, out_dir: Path = OUT_DIR) -> dict[str, int]:
    eligible, rest = remaining_items(kind, root)
    out_dir.mkdir(parents=True, exist_ok=True)
    path_for(kind, False, out_dir).write_text(
        "".join(json.dumps(it["task"], ensure_ascii=False) + "\n" for it in rest), encoding="utf-8")
    path_for(kind, True, out_dir).write_text(
        "".join(json.dumps(provenance_row(kind, it), ensure_ascii=False) + "\n" for it in rest), encoding="utf-8")
    return {"eligible": len(eligible), "original": len(eligible) - len(rest), "added": len(rest)}


def check_added(kind: str, root: Path = REPO_ROOT, out_dir: Path = OUT_DIR) -> list[str]:
    """Problems with a written added-task file (empty list = fine)."""
    problems: list[str] = []
    new_p = path_for(kind, False, out_dir)
    if not new_p.exists():
        return [f"{new_p} does not exist"]
    new = [json.loads(l) for l in _lines(new_p)]
    old = [json.loads(l) for l in original_task_lines(kind, root)]
    prov = [json.loads(l) for l in _lines(path_for(kind, True, out_dir))]
    ids_new, ids_old = [t["task_id"] for t in new], [t["task_id"] for t in old]
    if len(set(ids_new)) != len(ids_new):
        problems.append("duplicate task ids among the added tasks")
    if set(ids_new) & set(ids_old):
        problems.append(f"added tasks overlap the original 100: {sorted(set(ids_new) & set(ids_old))[:3]}")
    if len(set(ids_new + ids_old)) != len(ids_new) + len(ids_old):
        problems.append("task ids are not unique across the merged set")
    src_new = [t["source_id"] for t in new]
    src_old = [t["source_id"] for t in old]
    if set(src_new) & set(src_old):
        problems.append("added tasks share a source item with the original 100")
    prompts_new = [t["prompt"] for t in new]
    if len(set(prompts_new)) != len(prompts_new):
        problems.append("duplicate prompts among the added tasks")
    if set(prompts_new) & {t["prompt"] for t in old}:
        problems.append("an added prompt equals an original prompt")
    if len({t["prompt"] for t in old}) != len(old):
        problems.append("the original file itself has duplicate prompts")
    if [p["task_id"] for p in prov] != ids_new:
        problems.append("provenance rows do not match the task rows")
    if old and new and set(new[0]) != set(old[0]):
        problems.append(f"task fields differ from the original file: {sorted(set(new[0]) ^ set(old[0]))}")
    return problems


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    rc = 0
    for kind in KINDS:
        if not args.check:
            c = write_added(kind)
            print(f"{KINDS[kind]['suite']}: eligible {c['eligible']}, original {c['original']}, added {c['added']}")
        probs = check_added(kind)
        print(f"{KINDS[kind]['suite']}: {'ok' if not probs else probs}")
        rc |= bool(probs)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
