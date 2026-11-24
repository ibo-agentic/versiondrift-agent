"""Regenerate every exploratory .md / .csv / .png into a temp folder and compare it with the files in analysis/exploratory/.

    python -m scripts.exploratory.run_all                      # all analyses, temp output folder, then the comparison
    python -m scripts.exploratory.run_all --only pseudo_aa threshold_sensitivity
    python -m scripts.exploratory.run_all --out some_scratch_folder --current analysis/exploratory

The analyses only read existing data (results_v2, results_v3, rescored_v3, analysis_out_v3*, data/) and write only into --out
(never into a protected result folder). The comparison reports, per file: identical, text differs but all numbers equal, or the
numbers that differ. Hand-written paragraphs kept in scripts/exploratory/_text/ are copied verbatim, so they are not checked
against the data. PNG files are regenerated (matplotlib needed) but not compared. EXPLORATORY_deviations_table.md is written by
hand from DEVIATIONS.md and has no script.
"""

from __future__ import annotations

import argparse
import importlib
import re
import tempfile
import time
import traceback
from pathlib import Path

from ._common import REPO_ROOT, check_out_dir

ANALYSES = ["equivalence_bounds", "headline_cluster", "flip_vs_threshold", "r_vs_d_noise", "qwen3_dose", "pseudo_aa", "threshold_sensitivity",
            "s1_headline_excl_qwen", "s3_w3_tasks", "task_level_comparison", "failure_examples", "item_level_flips", "flip_examples_full", "wrong_calls"]
NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


def numbers(text: str) -> list[str]:
    return NUMBER.findall(text)


def same_number(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) < 1e-9
    except ValueError:
        return False


def compare_file(new: Path, old: Path) -> tuple[str, list[str]]:
    if new.suffix == ".png":
        return "binary (regenerated, not compared)", []
    a = old.read_text(encoding="utf-8-sig")
    b = new.read_text(encoding="utf-8-sig")
    if a == b:
        return "identical", []
    na, nb = numbers(a), numbers(b)
    if len(na) != len(nb):
        return f"DIFFERENT: {len(na)} numbers in the current file, {len(nb)} regenerated", []
    diffs = [(i, x, y) for i, (x, y) in enumerate(zip(na, nb)) if not same_number(x, y)]
    if not diffs:
        return "text differs, all numbers equal", []
    shown = []
    for i, x, y in diffs[:8]:
        shown.append(f"number #{i}: current {x} -> regenerated {y}")
    return f"DIFFERENT: {len(diffs)} of {len(na)} numbers differ", shown


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None, help="output folder (default: a new temp folder)")
    ap.add_argument("--current", default=str(REPO_ROOT / "analysis" / "exploratory"), help="folder with the current files to compare with")
    ap.add_argument("--only", nargs="*", default=None, help="run only these analyses")
    args = ap.parse_args(argv)
    out = check_out_dir(args.out or tempfile.mkdtemp(prefix="exploratory_regen_"))
    current = Path(args.current)
    names = args.only or ANALYSES
    unknown = [n for n in names if n not in ANALYSES]
    if unknown:
        raise SystemExit(f"unknown analysis: {unknown}; known: {ANALYSES}")
    made: list[str] = []
    failed: dict[str, str] = {}
    print(f"output folder: {out}")
    for name in names:
        t0 = time.time()
        try:
            mod = importlib.import_module(f"scripts.exploratory.{name}")
            files = mod.run(out)
            made += list(files)
            print(f"[ok]     {name:24s} {time.time() - t0:6.0f} s  {', '.join(files)}", flush=True)
        except Exception as exc:                                    # keep going: report every failure at the end
            failed[name] = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            print(f"[FAILED] {name:24s} {failed[name][:160]}", flush=True)
            traceback.print_exc()
    print("\nComparison with", current)
    n_diff = 0
    for f in sorted(set(made)):
        if not (current / f).exists():
            print(f"  {f}: new file (nothing to compare)")
            continue
        status, shown = compare_file(out / f, current / f)
        n_diff += status.startswith("DIFFERENT")
        print(f"  {f}: {status}")
        for line in shown:
            print(f"      {line}")
    not_made = sorted(p.name for p in current.glob("*") if p.is_file() and p.name not in made and p.suffix in (".md", ".csv", ".png", ".json", ".txt", ".py"))
    if not_made:
        print("\nFiles in the current folder that these scripts do not produce (hand-written or from older scripts): " + ", ".join(not_made))
    print(f"\n{len(made)} files regenerated, {n_diff} with differing numbers, {len(failed)} analyses failed.")
    return 1 if failed or n_diff else 0


if __name__ == "__main__":
    raise SystemExit(main())
