"""EXPLORATORY_wrong_calls.md (+ three CSVs): how often a one-run upgrade test gives the wrong call, and how much more runs vs. the
calibrated method (CI gate + 'inconclusive') help.

    python -m scripts.exploratory.wrong_calls --out <folder>

Part 1 (_wrong_calls_base) and part 2 (_wrong_calls_more) compute everything; two short hand-written blocks (scripts/exploratory/_text/
wrong_calls_where_errors.md and wrong_calls_more_summary.md) are kept verbatim and are NOT recomputed: re-read them if any table changes.
"""

from __future__ import annotations

from . import _wrong_calls_base, _wrong_calls_more
from ._common import parse_out, static


def run(out):
    base = _wrong_calls_base.run(out)
    more = _wrong_calls_more.run(out)
    base = base.replace("\n## Caveats\n", "\n" + static("wrong_calls_where_errors") + "\n## Caveats\n", 1)
    md = base.rstrip("\n") + "\n" + more.rstrip("\n") + "\n" + static("wrong_calls_more_summary")
    (out / "EXPLORATORY_wrong_calls.md").write_text(md, encoding="utf-8")
    return ["EXPLORATORY_wrong_calls.md", "EXPLORATORY_wrong_calls_decisions.csv", "EXPLORATORY_wrong_calls_bad_output_shares.csv",
            "EXPLORATORY_wrong_calls_summary.csv"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
