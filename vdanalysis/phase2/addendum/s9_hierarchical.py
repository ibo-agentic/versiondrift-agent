"""S9: hierarchical logistic model, a descriptive sensitivity check (spec: DEVIATIONS.md, 2026-11-08, entry f).

For each suite and each generation-side protocol P in PROTOCOLS that has a run for every pair and both of its models,
fitted separately:

  data     stress-condition records of protocol D and protocol P, pair-stacked: a model that belongs to two pairs
           appears in both (new = 0 in one, new = 1 in the other).
  outcome  binary strict score.
  fixed    intercept + new + P + new x P + condition   (D is the reference protocol)
  random   crossed intercepts (1 | task) + (1 | pair)
  fit      statsmodels BinomialBayesMixedGLM.fit_vb, rng seeded with 1234.
  report   posterior mean and SD of the new x P coefficient (log-odds), and whether its sign agrees with the sign of
           the mean difference (P minus D) in stress diff over the suite's decisions.

Interpretation made for "S1's direction": S1 reports flips (unsigned), so the direction is taken as the sign of the
mean over pairs of (stress diff under P - stress diff under D). Descriptive only; it feeds no gate or verdict.
"""

from __future__ import annotations

import warnings

import numpy as np

SEED = 1234
PROTOCOLS = ("R", "F1", "F3", "F4", "F5", "F6")
REFERENCE = "D"


def fit(y, new, proto, cond, task, pair, seed: int = SEED) -> dict:
    """Fit one model. All arguments are 1-D arrays of equal length: ``y`` in {0,1}, ``new``/``proto``/``cond`` in
    {0,1} (proto = 1 for the protocol under test, 0 for D), ``task`` and ``pair`` are labels."""
    from scipy import sparse
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM

    y = np.asarray(y, dtype=float)
    new, proto, cond = (np.asarray(a, dtype=float) for a in (new, proto, cond))
    n = len(y)
    exog = np.column_stack([np.ones(n), new, proto, new * proto, cond])
    tcodes, tlev = _codes(task)
    pcodes, plev = _codes(pair)
    rows = np.arange(n)
    mt = sparse.csr_matrix((np.ones(n), (rows, tcodes)), shape=(n, len(tlev)))
    mp = sparse.csr_matrix((np.ones(n), (rows, pcodes)), shape=(n, len(plev)))
    exog_vc = sparse.hstack([mt, mp]).tocsr()
    ident = np.r_[np.zeros(len(tlev), dtype=int), np.ones(len(plev), dtype=int)]
    names = ["intercept", "new", "protocol", "new:protocol", "condition"]
    model = BinomialBayesMixedGLM(y, exog, exog_vc, ident, fep_names=names, vcp_names=["task", "pair"])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        res = model.fit_vb(rng=np.random.default_rng(seed))
    converged = not any("did not converge" in str(w.message) for w in caught)
    mean = dict(zip(names, (float(v) for v in res.fe_mean)))
    sd = dict(zip(names, (float(v) for v in res.fe_sd)))
    return {"vb_converged": converged, "n_records": n, "n_tasks": len(tlev), "n_pairs": len(plev),
            "coef_new_x_protocol_mean": mean["new:protocol"], "coef_new_x_protocol_sd": sd["new:protocol"],
            "coef_new_mean": mean["new"], "coef_new_sd": sd["new"], "coef_protocol_mean": mean["protocol"],
            "coef_condition_mean": mean["condition"],
            "vcp_task_mean": float(res.vcp_mean[0]), "vcp_pair_mean": float(res.vcp_mean[1])}


def _codes(labels) -> tuple[np.ndarray, list]:
    levels = sorted(set(labels), key=str)
    idx = {v: i for i, v in enumerate(levels)}
    return np.array([idx[v] for v in labels]), levels


def sign_agrees(coef: float, direction: float) -> bool | None:
    """None when either number is 0 or missing (no sign to compare)."""
    if not np.isfinite(coef) or not np.isfinite(direction) or coef == 0 or direction == 0:
        return None
    return bool(np.sign(coef) == np.sign(direction))


def stack_records(runs_by_pair: dict[str, dict[str, tuple]], protocol: str, conditions) -> dict:
    """``runs_by_pair``: pair -> {protocol: (old_run, new_run)}. Returns column lists for ``fit`` (protocol D rows
    have proto = 0, ``protocol`` rows have proto = 1). Scores must be 0/1."""
    cond_list = sorted(conditions)
    cols = {"y": [], "new": [], "proto": [], "cond": [], "task": [], "pair": []}
    for pair, by in runs_by_pair.items():
        for pr, flag in ((REFERENCE, 0), (protocol, 1)):
            old, new = by[pr]
            for is_new, run in ((0, old), (1, new)):
                for k, (score, _bucket) in run.keys.items():
                    if k[1] not in conditions:
                        continue
                    if score not in (0, 1):
                        raise ValueError(f"S9 needs binary strict scores, got {score!r}")
                    cols["y"].append(score)
                    cols["new"].append(is_new)
                    cols["proto"].append(flag)
                    cols["cond"].append(cond_list.index(k[1]))
                    cols["task"].append(k[0])
                    cols["pair"].append(pair)
    return cols


def run_s9(cx, protocols=PROTOCOLS, seed: int = SEED) -> tuple[list[dict], list[dict]]:
    """Returns (result rows, skipped rows). ``cx`` is the driver's ``Ctx``."""
    cfg = cx.cfg
    results, skipped = [], []
    for suite in cfg.suites:
        for pr in protocols:
            if pr not in cfg.protocols:
                skipped.append({"suite": suite, "protocol": pr, "reason": "protocol not in config"})
                continue
            by_pair: dict[str, dict] = {}
            missing = []
            for pair in cx.pairs:
                got = {}
                for p in (REFERENCE, pr):
                    old, new = cx.runs(p, pair, suite)
                    if old is None or new is None:
                        missing.append(f"{pair}/{p}")
                    else:
                        got[p] = (old, new)
                by_pair[pair] = got
            if missing:
                skipped.append({"suite": suite, "protocol": pr, "reason": "does not cover all pairs: missing " + ", ".join(missing[:6]) + (" ..." if len(missing) > 6 else "")})
                continue
            cols = stack_records(by_pair, pr, set(cfg.stress))
            res = fit(cols["y"], cols["new"], cols["proto"], cols["cond"], cols["task"], cols["pair"], seed)
            rows_p, rows_d = cx.rows(pr), cx.rows(REFERENCE)
            diffs = [rows_p[(p, suite)]["stress_diff"] - rows_d[(p, suite)]["stress_diff"] for p in cx.pairs
                     if (p, suite) in rows_p and (p, suite) in rows_d]
            direction = float(np.mean(diffs)) if diffs else float("nan")
            res.update({"suite": suite, "protocol": pr, "s1_direction_mean_stress_diff_P_minus_D": direction,
                        "n_decisions_for_direction": len(diffs),
                        "sign_agrees_with_direction": sign_agrees(res["coef_new_x_protocol_mean"], direction)})
            results.append(res)
    return results, skipped
