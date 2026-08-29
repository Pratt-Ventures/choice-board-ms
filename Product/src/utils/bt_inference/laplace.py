from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from .model import (
    ChannelData,
    ParamLayout,
    bounds_for,
    decode,
    grad_neg_log_posterior,
    layout_for,
    neg_log_posterior,
    pack_initial,
    participant_likelihood_grad,
)

FIT_CALLS = 0
DEFAULT_SAMPLES = 600


@dataclass
class FitResult:
    item_ids: list[int]
    participant_ids: list[int]
    x_hat: np.ndarray
    layout: ParamLayout
    data: ChannelData
    mu_samples: np.ndarray
    u_samples: np.ndarray | None
    kappa_samples: np.ndarray
    lapse_samples: np.ndarray
    beta_l_samples: np.ndarray
    mu_map: np.ndarray
    kappa_map: float
    lapse_map: float
    beta_l_map: float
    sigma_u_map: float | None
    hess_inv: np.ndarray
    converged: bool
    nll: float
    n_obs: int


def reset_fit_calls() -> None:
    global FIT_CALLS
    FIT_CALLS = 0


def _hessian(grad_fn, x: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    n = x.size
    h = np.zeros((n, n), dtype=float)
    g0 = grad_fn(x)
    for i in range(n):
        xp = x.copy()
        step = eps * max(1.0, abs(float(x[i])))
        xp[i] += step
        h[i] = (grad_fn(xp) - g0) / step
    return 0.5 * (h + h.T)


def _sample_laplace(x_hat: np.ndarray, hess: np.ndarray, n_samples: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    w, v = np.linalg.eigh(hess)
    w = np.clip(w, 1e-8, None)
    scale = v * (1.0 / np.sqrt(w))
    z = rng.standard_normal((n_samples, x_hat.size))
    draws = x_hat + z @ scale.T
    cov = (v * (1.0 / w)) @ v.T
    return draws, cov


def fit_channel(
    data: ChannelData,
    *,
    n_samples: int = DEFAULT_SAMPLES,
    seed: int = 0,
) -> FitResult:
    global FIT_CALLS
    FIT_CALLS += 1
    lay = layout_for(data)
    x0 = pack_initial(data, lay)
    bounds = bounds_for(lay)

    def fun(z):
        return neg_log_posterior(z, data, lay)

    def jac(z):
        return grad_neg_log_posterior(z, data, lay)

    res = minimize(
        fun,
        x0,
        method="L-BFGS-B",
        jac=jac,
        bounds=bounds,
        options={"maxiter": 400, "ftol": 1e-10},
    )
    x_hat = np.asarray(res.x, dtype=float)
    hess = _hessian(jac, x_hat)
    rng = np.random.default_rng(int(seed) % (2**31))
    draws, cov = _sample_laplace(x_hat, hess, max(50, int(n_samples)), rng)

    decoded_map = decode(x_hat, lay)
    mu_s = np.zeros((draws.shape[0], lay.n_items), dtype=float)
    u_s = None
    if lay.use_hierarchy:
        u_s = np.zeros((draws.shape[0], lay.n_part, lay.n_items), dtype=float)
    kap = np.empty(draws.shape[0], dtype=float)
    lam = np.empty(draws.shape[0], dtype=float)
    beta = np.empty(draws.shape[0], dtype=float)
    for i in range(draws.shape[0]):
        di = decode(draws[i], lay)
        mu_s[i] = di["mu"]
        if u_s is not None and di["u"] is not None:
            u_s[i] = di["u"]
        kap[i] = di["kappa"]
        lam[i] = di["lapse"]
        beta[i] = di["beta_l"]

    return FitResult(
        item_ids=list(data.item_ids),
        participant_ids=list(data.participant_ids),
        x_hat=x_hat,
        layout=lay,
        data=data,
        mu_samples=mu_s,
        u_samples=u_s,
        kappa_samples=kap,
        lapse_samples=lam,
        beta_l_samples=beta,
        mu_map=decoded_map["mu"],
        kappa_map=float(decoded_map["kappa"]),
        lapse_map=float(decoded_map["lapse"]),
        beta_l_map=float(decoded_map["beta_l"]),
        sigma_u_map=decoded_map["sigma_u"],
        hess_inv=cov,
        converged=bool(res.success),
        nll=float(res.fun),
        n_obs=int(data.y.size),
    )


def personal_scores(fit: FitResult, participant_id: int) -> np.ndarray:
    if fit.u_samples is None:
        return fit.mu_samples
    try:
        idx = fit.participant_ids.index(int(participant_id))
    except ValueError:
        return fit.mu_samples
    return fit.mu_samples + fit.u_samples[:, idx, :]


def approx_loo_winner_shift(fit: FitResult, consensus_winner_idx: int) -> float:
    """Max |Δ P(winner)| from first-order Laplace leave-one-participant influence."""
    if len(fit.participant_ids) < 2:
        return 0.0
    x = fit.x_hat
    lay = fit.layout
    data = fit.data
    max_shift = 0.0
    mu0 = fit.mu_map
    n = len(fit.item_ids)
    if n < 2:
        return 0.0
    p0 = _bt_p_best(mu0, fit.kappa_map, fit.lapse_map)
    w0 = int(consensus_winner_idx)
    for pi in range(len(fit.participant_ids)):
        g_p = participant_likelihood_grad(x, data, lay, pi)
        try:
            delta = fit.hess_inv @ g_p
        except ValueError:
            continue
        x_loo = x - delta
        d = decode(x_loo, lay)
        p1 = _bt_p_best(d["mu"], d["kappa"], d["lapse"])
        max_shift = max(max_shift, abs(float(p1[w0] - p0[w0])))
    return float(max_shift)


def _bt_p_best(mu: np.ndarray, kappa: float, lapse: float) -> np.ndarray:
    n = mu.size
    if n <= 1:
        return np.ones(n, dtype=float)
    diff = mu[:, None] - mu[None, :]
    p = (1.0 - lapse) * (1.0 / (1.0 + np.exp(-np.clip(kappa * diff, -40.0, 40.0)))) + 0.5 * lapse
    q = (p.sum(axis=1) - np.diag(p)) / float(n - 1)
    # softmax of Q as a cheap p_best stand-in for influence
    z = q - q.max()
    e = np.exp(z * 8.0)
    return e / e.sum()
