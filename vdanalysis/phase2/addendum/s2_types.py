"""S2: flip types.

Sign reversal: harmful <-> beneficial. Boundary crossing: any other flip, i.e. one that involves neutral under the
point gate (and, under the four-class gate of S3, neutral or inconclusive: the addendum does not say how
"inconclusive" counts, so every flip that is not a sign reversal is called a boundary crossing).
"""

from __future__ import annotations

from collections import Counter

SIGN = "sign_reversal"
BOUNDARY = "boundary_crossing"


def flip_type(a: str, b: str) -> str | None:
    """None if the two labels are equal."""
    if a == b:
        return None
    return SIGN if {a, b} == {"harmful", "beneficial"} else BOUNDARY


def count_types(pairs: list[tuple[str, str]]) -> dict[str, int]:
    """``pairs`` = [(label_a, label_b), ...] for decisions; returns n, flips and the two type counts."""
    c = Counter(flip_type(a, b) for a, b in pairs)
    return {"n_decisions": len(pairs), "n_flips": c[SIGN] + c[BOUNDARY], SIGN: c[SIGN], BOUNDARY: c[BOUNDARY]}


def split_rows(rows: list[dict], key_a: str, key_b: str, group_keys: tuple[str, ...], separate_pair: str | None = None) -> list[dict]:
    """Counts per group (e.g. factor), with ``separate_pair`` (the qwen25->qwen3 pair) shown on its own rows."""
    out = []
    groups: dict[tuple, list] = {}
    for r in rows:
        for part in ("all", "excluding_pair", "only_pair") if separate_pair else ("all",):
            if part == "excluding_pair" and r["pair"] == separate_pair:
                continue
            if part == "only_pair" and r["pair"] != separate_pair:
                continue
            groups.setdefault(tuple(r[k] for k in group_keys) + (part,), []).append((r[key_a], r[key_b]))
    for key, pairs in groups.items():
        out.append({**dict(zip(group_keys, key[:-1])), "subset": key[-1], **count_types(pairs)})
    return out
