"""F7 rescore-only factor: reads existing run records, writes a NEW folder
(default rescored/F7/...). See vdanalysis/rescore.py for the rule.
Never run this on results being produced by a live session; it only reads
the source protocol's records, but pass --out-root outside results*/."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vdanalysis.rescore import cli  # noqa: E402

if __name__ == "__main__":
    sys.exit(cli("F7"))
