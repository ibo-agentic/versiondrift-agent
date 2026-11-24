"""Boundary check: recompute every pipeline comparison with exact fractions and find labels decided by floating-point noise.

    python -m scripts.exploratory.boundary_check --out <folder>        # a few minutes; not part of run_all

Wraps vdanalysis compare() while it runs Phase 1 and Phase 2 (decisions, controls, views, studies), recomputes each stress diff
exactly (fractions), and lists labels at +/-0.03, +/-0.05, +/-0.07 that differ between the float and the exact comparison; the
near-boundary ones are re-run with the CI gate, and the addendum's array-based diffs are checked the same way. Writes boundary_check.json.
"""

from __future__ import annotations

import sys, json
from fractions import Fraction
from collections import Counter, defaultdict
import vdanalysis.stats as st
import vdanalysis.engine as eng
import vdanalysis.studies as stu
import vdanalysis.phase2.controls2 as c2
import vdanalysis.phase2.descriptive as dsc
from upgradecanary.gates import point_gate, ci_gate
from vdanalysis.phase2.config import load_phase2_config
from vdanalysis.phase2.analysis import Phase2Analysis, ViewSpec
from vdanalysis.phase2.controls2 import control_rows2
from vdanalysis.phase2.addendum.run_addendum import Ctx
from vdanalysis.phase2.addendum.data import point_code      # the pipeline's own (unrounded) comparison: this is what is being checked
import numpy as np
from ._common import CONFIG, REPO_ROOT, parse_out


def run(outdir):
    orig = st.compare
    DELTAS = {"0.03": Fraction(3, 100), "0.05": Fraction(5, 100), "0.07": Fraction(7, 100)}
    calls = {}


    def exact_diff(old, new, conditions):
        keys = [k for k in set(old.keys) & set(new.keys) if k[1] in conditions]
        if not keys:
            return None
        per = defaultdict(lambda: [0, Fraction(0), Fraction(0)])
        for k in keys:
            a, b = old.keys[k][0], new.keys[k][0]
            assert a in (0.0, 1.0) and b in (0.0, 1.0)
            d = per[k[1]]
            d[0] += 1; d[1] += int(a); d[2] += int(b)
        return sum((d[2] - d[1]) / d[0] for d in per.values()) / len(per)


    def lab_exact_point(x, delta):
        return "harmful" if x < -delta else "beneficial" if x > delta else "neutral"


    def lab_exact_ci(x, lo, hi, delta):
        if x < -delta and hi < 0:
            return "harmful"
        if x > delta and lo > 0:
            return "beneficial"
        return "neutral"


    CTX = {"name": ""}


    def wrapped(old, new, conditions, threshold, reps, seed, with_ci=True):
        res = orig(old, new, conditions, threshold, reps, seed, with_ci=with_ci)
        if res is None:
            return res
        key = (CTX["name"], old.protocol, old.model, old.suite, new.protocol, new.model, new.suite, tuple(sorted(conditions)))
        if key not in calls:
            calls[key] = {"float": res.diff, "exact": exact_diff(old, new, conditions), "label_point": res.label_point, "label_ci": res.label_ci,
                          "lo": res.ci_lo, "hi": res.ci_hi, "threshold": threshold, "old": old, "new": new, "conds": list(conditions)}
        return res


    SAVED = [(mod, mod.compare) for mod in (st, eng, stu, c2, dsc)]
    for mod in (st, eng, stu, c2, dsc):
        mod.compare = wrapped


    def scan(name, cfg_path, mode):
        CTX["name"] = name
        cfg = load_phase2_config(cfg_path)
        an = Phase2Analysis(cfg, with_ci=False, allow_missing=True)
        n0 = len(calls)
        for proto in cfg.protocols:
            try:
                an.rows(proto)
            except Exception as exc:
                print(name, "rows failed", proto, type(exc).__name__, str(exc)[:80])
        for ctl_list in (cfg.controls, cfg.p2.get("descriptive_controls") or []):
            try:
                control_rows2(an, controls=ctl_list)
            except Exception as exc:
                print(name, "controls failed", type(exc).__name__, str(exc)[:80])
        if mode == "phase2":
            for view in ("greedy", "sampled"):
                av = an.with_view(ViewSpec(trials=view))
                for proto in ("D", "R", "D_AA2", "R_AA2", "R_PC_Q2K", "R_PC_NODESC", "F1", "F5", "F6"):
                    if proto in cfg.protocols:
                        try:
                            av.rows(proto)
                        except Exception as exc:
                            print(name, view, proto, "failed", str(exc)[:60])
                try:
                    control_rows2(av)
                except Exception as exc:
                    print(name, view, "controls failed", str(exc)[:60])
        else:
            for fn in (stu.qwen3_f4_vs_f2, stu.qwen3_pair_labels, stu.robust_checks):
                try:
                    fn(an)
                except Exception as exc:
                    print(name, fn.__name__, "failed", type(exc).__name__, str(exc)[:80])
        print(name, "compare calls recorded:", len(calls) - n0, flush=True)


    try:
        scan("phase1", str(REPO_ROOT / "configs/analysis_phase1_regression.yaml"), "phase1")
        scan("phase2", str(REPO_ROOT / "configs/analysis_phase2.yaml"), "phase2")
    finally:
        for mod, f in SAVED:
            mod.compare = f

    stress_calls = {k: v for k, v in calls.items() if v["exact"] is not None}
    print("total distinct comparisons:", len(stress_calls))
    report = {"n": len(stress_calls), "by_scan": dict(Counter(k[0] for k in stress_calls)), "boundary": [], "mismatch": {}, "ci_mismatch": []}
    for dn, d in DELTAS.items():
        dfl = float(dn)
        mism = []
        for k, v in stress_calls.items():
            ex = v["exact"]
            if abs(ex) == d:
                report["boundary"].append({"delta": dn, "key": "/".join(map(str, k[:7])) + "|" + ",".join(k[7]), "float": repr(v["float"]), "exact": str(ex),
                                           "float_label": point_gate(v["float"], dfl), "exact_label": lab_exact_point(ex, d)})
            if point_gate(v["float"], dfl) != lab_exact_point(ex, d):
                mism.append("/".join(map(str, k[:7])) + "|" + ",".join(k[7]))
        report["mismatch"][dn] = mism
    # CI-gate check at 0.05 for every call whose exact diff is within 1e-6 of a boundary (any delta): re-run with CI
    near = [(k, v) for k, v in stress_calls.items() if any(abs(abs(float(v["exact"])) - float(dn)) < 1e-6 for dn in DELTAS)]
    print("comparisons within 1e-6 of a gate boundary:", len(near))
    CTXN = {}
    for k, v in near:
        res = orig(v["old"], v["new"], v["conds"], v["threshold"], 10000, 1234, with_ci=True)
        for dn, d in DELTAS.items():
            a = ci_gate(res.diff, res.ci_lo, res.ci_hi, float(dn))
            b = lab_exact_ci(v["exact"], res.ci_lo, res.ci_hi, d)
            if a != b:
                report["ci_mismatch"].append({"delta": dn, "key": "/".join(map(str, k[:7])), "float_label": a, "exact_label": b, "diff": repr(res.diff), "exact": str(v["exact"])})
    report["near_boundary_calls"] = len(near)
    # addendum path: array-based diff vs exact for the near-boundary Phase 2 comparisons
    if True:
        cfg = load_phase2_config(str(CONFIG))
        an = Phase2Analysis(cfg, with_ci=False, allow_missing=True)
        cx = Ctx(an)
        pairs = [cfg.pair_name(p) for p in cfg.pairs]
        n = 0
        bound = {0.03: 0, 0.05: 0, 0.07: 0}
        mism = []
        for proto in cfg.protocols:
            for pair in pairs:
                for suite in cfg.suites:
                    try:
                        a = cx.arrays(proto, pair, suite)
                    except Exception:
                        a = None
                    if a is None:
                        continue
                    n += 1
                    Ssum, Nsum = a.S.sum(axis=0), a.N.sum(axis=0)
                    ex = sum(Fraction(int(round(s))) / Fraction(int(round(m))) for s, m in zip(Ssum, Nsum)) / len(Ssum)
                    fl = float(a.diff())
                    for dl in (0.03, 0.05, 0.07):
                        d = Fraction(int(round(dl * 100)), 100)
                        if abs(ex) == d:
                            bound[dl] += 1
                        lab_f = int(point_code(np.array([fl]), dl)[0])
                        lab_e = -1 if ex < -d else 1 if ex > d else 0
                        if lab_f != lab_e:
                            mism.append((dl, proto, pair, suite, repr(fl), str(ex), lab_f, lab_e))
        report["array_check"] = {"diffs_checked": n, "exact_boundary_cases": {str(k): v for k, v in bound.items()}, "float_vs_exact_mismatches": [list(map(str, m)) for m in mism]}
        print("array-based diffs checked:", n, "exact-boundary cases per delta:", bound, "mismatches:", len(mism))

    (outdir / "boundary_check.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: (v if k not in ("boundary",) else len(v)) for k, v in report.items()}, indent=1)[:3000])

    return ["boundary_check.json"]


if __name__ == "__main__":
    print(run(parse_out(__doc__)))
