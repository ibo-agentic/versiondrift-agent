"""Regenerate the UpgradeCanary-BFCL-100 task files from the BFCL source data.

Frozen selection protocol: docs/protocol.md ("UpgradeCanary-BFCL-100 selection
protocol"). Selection depends only on task metadata, never on model outcomes.

Run from the repo root:  python scripts/generate_bfcl_tasks.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from upgradecanary.bfcl import generate


def main() -> None:
    stats = generate()
    print(f"eligible: {stats['eligible']} (rejected/deduplicated: {stats['rejected']})")
    print(f"selected: {stats['selected']}")
    for sig, s in stats["strata"].items():
        print(f"  stratum '{sig or '(empty)'}': selected {s['selected']} of {s['eligible']} eligible")
    print("wrote data/bfcl_tasks.jsonl and data/bfcl_tasks_provenance.jsonl")


if __name__ == "__main__":
    main()
