"""W6 human labels: merge the filled rater files and the key into the CSV that ``run_phase2 --labels`` reads.

    python -m scripts.phase2.w6_merge --key w6_labels/private/labels_key.csv \
        --rater rater1=w6_labels/for_raters/labels_rater1_filled.xlsx \
        --rater rater2=w6_labels/for_raters/labels_rater2_filled.xlsx \
        --out-dir w6_labels/merged

Writes two files with the columns record_id, labeler, label (labelers: the names given with --rater, plus ``rule``):

  labels_unsure_as_class.csv   every filled label as given (``unsure`` stays its own class)
  labels_unsure_excluded.csv   the same without the ``unsure`` rows of a rater; the analysis compares two raters over the
                               items both labeled, so an item drops out of a pair as soon as either rater said unsure

``--rater`` can be given once (one labeler: human-human kappa is then not available). The rule's label comes from the
key: correct = pass, wrong = fail. Then, for each file:

    python -m vdanalysis.phase2.run_phase2 --config configs/analysis_phase2.yaml --out <new folder> --labels <file>
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

LABELS = ("correct", "wrong", "unsure")
RULE = "rule"
LABEL_HEADER = "label"


def read_key(path: Path) -> dict[str, str]:
    with open(path, encoding="utf-8", newline="") as fh:
        return {r["item_id"]: r["rule_label"] for r in csv.DictReader(fh)}


def read_filled(path: Path) -> dict[str, str]:
    """{item_id: label} from a filled labeling sheet (.xlsx, or a .csv with item_id and label columns)."""
    if str(path).lower().endswith(".csv"):
        with open(path, encoding="utf-8", newline="") as fh:
            rows = [(r["item_id"], r.get("label") or r.get("label (correct / wrong / unsure)")) for r in csv.DictReader(fh)]
    else:
        from openpyxl import load_workbook
        ws = load_workbook(path, read_only=True, data_only=True)["items"]
        it = ws.iter_rows(values_only=True)
        header = [str(h or "").strip() for h in next(it)]
        i_id = header.index("item_id")
        i_lab = next(i for i, h in enumerate(header) if h.lower().startswith(LABEL_HEADER))
        rows = [(r[i_id], r[i_lab]) for r in it if r[i_id]]
    out: dict[str, str] = {}
    for item, lab in rows:
        item = str(item).strip()
        if item in out:
            raise ValueError(f"{path.name}: item {item} appears twice")
        out[item] = ("" if lab is None else str(lab)).strip().lower()
    return out


def merge(key: dict[str, str], raters: dict[str, dict[str, str]]) -> tuple[list[dict], list[dict], list[str]]:
    """Returns (rows with unsure as a class, rows without unsure, problems). Problems are blocking."""
    problems = []
    for name, labs in raters.items():
        unknown = sorted(set(labs) - set(key))
        missing = sorted(set(key) - set(labs))
        blank = sorted(i for i, v in labs.items() if v == "")
        bad = sorted((i, v) for i, v in labs.items() if v and v not in LABELS)
        if unknown:
            problems.append(f"{name}: items not in the key: {unknown[:5]}")
        if missing:
            problems.append(f"{name}: {len(missing)} items missing, e.g. {missing[:5]}")
        if blank:
            problems.append(f"{name}: {len(blank)} items have no label, e.g. {blank[:5]}")
        if bad:
            problems.append(f"{name}: labels other than correct/wrong/unsure: {bad[:5]}")
    if problems:
        return [], [], problems
    rows = [{"record_id": i, "labeler": RULE, "label": key[i]} for i in sorted(key)]
    for name, labs in raters.items():
        rows += [{"record_id": i, "labeler": name, "label": labs[i]} for i in sorted(labs)]
    return rows, [r for r in rows if r["label"] != "unsure"], []


def write_rows(rows: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["record_id", "labeler", "label"])
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", required=True)
    ap.add_argument("--rater", action="append", required=True, metavar="NAME=FILE")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)
    key = read_key(Path(args.key))
    raters = {}
    for spec in args.rater:
        name, _, file = spec.partition("=")
        if not name or not file or name == RULE:
            raise SystemExit(f"bad --rater {spec!r}: use NAME=FILE and a name other than {RULE!r}")
        raters[name] = read_filled(Path(file))
    full, no_unsure, problems = merge(key, raters)
    if problems:
        print("NOT MERGED:\n  " + "\n  ".join(problems))
        return 1
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_rows(full, out / "labels_unsure_as_class.csv")
    write_rows(no_unsure, out / "labels_unsure_excluded.csv")
    n_unsure = {n: sum(v == "unsure" for v in labs.values()) for n, labs in raters.items()}
    print(f"wrote {len(full)} rows (unsure as class) and {len(no_unsure)} rows (unsure excluded) to {out}; unsure per rater: {n_unsure}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
