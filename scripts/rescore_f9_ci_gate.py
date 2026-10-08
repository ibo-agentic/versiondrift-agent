"""F9 (gate rule: point threshold vs CI gate). No data is changed: this
computes each D decision's label under both gates and writes the table to a
NEW folder (default rescored/F9/ci_gate_decisions.csv)."""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from vdanalysis.config import assert_safe_output_dir, load_config  # noqa: E402
from vdanalysis.engine import Analysis  # noqa: E402
from vdanalysis.run_analysis import write_csv  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(REPO_ROOT / "configs" / "analysis_official_folders.yaml"))
    ap.add_argument("--out-root", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    root = Path(args.out_root) if args.out_root else (cfg.base_dir / cfg.raw["rescored_root"])
    out = assert_safe_output_dir(root) / "F9"
    rows = []
    for r in Analysis(cfg).rows(cfg.base_protocol).values():
        rows.append({k: r[k] for k in ("pair", "suite", "size_changing", "stress_diff", "ci_lo", "ci_hi",
                                       "label_point", "label_ci")} | {"flipped": r["label_point"] != r["label_ci"]})
    write_csv(out / "ci_gate_decisions.csv", rows)
    print(f"{len(rows)} decisions -> {out / 'ci_gate_decisions.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
