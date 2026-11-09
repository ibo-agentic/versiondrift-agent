"""S6: power and minimum detectable effect. Descriptive only; our own method, not part of the original plan.

Method (as in analysis/exploratory/EXPLORATORY_phase1_report.md): normal approximation on task-level paired
differences, trials averaged within task.
  MDE(80% power, alpha 0.05) = (z_0.975 + z_0.80) * SD / sqrt(n)
  power at a true effect delta = Phi(delta / SE - z_0.975) + Phi(-delta / SE - z_0.975),   SE = SD / sqrt(n)

EXPLORATORY extension (Phase 1 data): split the variance of the per-task stress diff into a between-task part and a
within-task (trial) part, then project the SD to other trial and task counts.

  Model per task t: ybar_t = (g_t + s_t1 + ... ) / K, with one greedy trial g_t (no sampling noise) and K-1 sampled
  trials s_tk = mu_t + e_tk, Var(e) = sigma2_s.
  Phase 1 has K = 3 (1 greedy + 2 sampled). sigma2_s is estimated from the two sampled trials of each task:
  mean over tasks of (s_t1 - s_t2)^2 / 2. Observed Var_t(ybar_t) = B + (2/9) sigma2_s, so B = V3 - (2/9) sigma2_s.
  With 10 trials (1 greedy + 9 sampled): Var(ybar_t) = B' + (9 / 100) sigma2_s, with B' = B under the assumption
  g_t ~ mu_t (the greedy outcome of a task has the same expectation as a sampled outcome). This assumption is
  not tested here. A second estimate uses the two sampled trials only: B_mu = Var_t((s_t1 + s_t2)/2) - sigma2_s/2.
"""

from __future__ import annotations

import math

import numpy as np

from . import DELTA, Z_ALPHA_2, Z_POWER_80


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def mde(sd: float, n: int, z_alpha: float = Z_ALPHA_2, z_power: float = Z_POWER_80) -> float:
    return (z_alpha + z_power) * sd / math.sqrt(n)


def power_at(effect: float, sd: float, n: int, z_alpha: float = Z_ALPHA_2) -> float:
    se = sd / math.sqrt(n)
    return norm_cdf(effect / se - z_alpha) + norm_cdf(-effect / se - z_alpha)


def variance_components(y: np.ndarray, greedy_col: int | None = 0) -> dict:
    """``y``: (units, trials) per-trial stress diffs (NaN allowed; units with a NaN are dropped). Returns the
    observed variance of the per-unit mean over all trials (V_all), the sampling-noise variance sigma2_s from the
    sampled trials, and the between-unit variance estimates under the model in the module docstring."""
    ok = np.isfinite(y).all(axis=1)
    y = y[ok]
    n, k = y.shape
    sampled = [j for j in range(k) if j != greedy_col]
    ys = y[:, sampled]
    ks = ys.shape[1]
    sigma2_s = float(np.mean(np.var(ys, axis=1, ddof=1))) if ks >= 2 else float("nan")
    v_all = float(np.var(y.mean(axis=1), ddof=1))
    v_samp = float(np.var(ys.mean(axis=1), ddof=1)) if ks >= 1 else float("nan")
    g = 1 if greedy_col is not None else 0
    # Var(ybar over all k trials) = B + (ks / k^2) * sigma2_s for one greedy + ks sampled trials
    b_all = v_all - (ks / (k * k)) * sigma2_s
    b_samp = v_samp - sigma2_s / ks
    return {"n_units": n, "n_trials": k, "n_sampled_trials": ks, "V_observed": v_all, "sigma2_sampling": sigma2_s,
            "B_between_from_all_trials": b_all, "B_between_from_sampled_trials": b_samp, "greedy_trials": g}


def project_variance(b: float, sigma2_s: float, n_trials: int, greedy: int = 1) -> float:
    """Variance of a unit's mean over ``n_trials`` trials (``greedy`` of them deterministic) given the between-unit
    variance ``b`` and the sampling variance ``sigma2_s`` per sampled trial. Negative ``b`` is clipped to 0."""
    ks = n_trials - greedy
    return max(b, 0.0) + (ks / (n_trials * n_trials)) * sigma2_s


def project_table(comp: dict, label: str, scenarios: list[dict], delta: float = DELTA) -> list[dict]:
    """``scenarios``: [{'name', 'n_trials', 'n_units'}]. One row per scenario and per between-variance estimate."""
    rows = []
    for est in ("B_between_from_all_trials", "B_between_from_sampled_trials"):
        b = comp[est]
        for sc in scenarios:
            v = project_variance(b, comp["sigma2_sampling"], sc["n_trials"])
            sd = math.sqrt(v)
            rows.append({"group": label, "between_estimate": est, "scenario": sc["name"], "n_trials": sc["n_trials"],
                         "n_units": sc["n_units"], "sd_of_unit_mean": sd, "mde_80": mde(sd, sc["n_units"]),
                         "power_at_delta": power_at(delta, sd, sc["n_units"])})
    return rows
