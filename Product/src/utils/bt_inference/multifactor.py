from __future__ import annotations

import numpy as np

from .ranks import q_per_draw, rank_summary


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    z = np.asarray(x, dtype=float)
    z = z - np.max(z, axis=axis, keepdims=True)
    e = np.exp(np.clip(z, -40.0, 40.0))
    return e / np.clip(e.sum(axis=axis, keepdims=True), 1e-15, None)


def combine_factor_draws(
    factor_latent: np.ndarray,
    factor_option_q: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    factor_latent: [S, F]
    factor_option_q: [S, F, O]  (NaN = option not scored under that factor)
    Returns weights [S, F], overall U [S, O]
    """
    weights = softmax(factor_latent, axis=1)
    q = np.asarray(factor_option_q, dtype=float)
    w = weights[:, :, None]
    mask = np.isfinite(q)
    q0 = np.where(mask, q, 0.0)
    w_eff = np.where(mask, w, 0.0)
    denom = w_eff.sum(axis=1)
    numer = (w_eff * q0).sum(axis=1)
    overall = np.divide(numer, np.clip(denom, 1e-15, None), out=np.full_like(numer, 0.5), where=denom > 0)
    return weights, overall


def factor_leverage(
    weights: np.ndarray,
    factor_option_q: np.ndarray,
) -> dict[str, np.ndarray]:
    """Importance, discrimination, leverage from draws.

    weights [S, F], factor_option_q [S, F, O]
    """
    w_mean = weights.mean(axis=0)
    q = np.asarray(factor_option_q, dtype=float)
    mask = np.isfinite(q)
    counts = mask.sum(axis=0)
    numer = np.where(mask, q, 0.0).sum(axis=0)
    q_mean = np.divide(numer, counts, out=np.full(numer.shape, 0.5), where=counts > 0)
    if q_mean.shape[1] > 1:
        disc = q_mean.std(axis=1)
    else:
        disc = np.zeros(q_mean.shape[0], dtype=float)
    lev = w_mean * disc
    lev_sum = float(lev.sum()) or 1.0
    lev_norm = lev / lev_sum
    w_lo = np.quantile(weights, 0.025, axis=0)
    w_hi = np.quantile(weights, 0.975, axis=0)
    return {
        "importance": w_mean,
        "weight_median": np.median(weights, axis=0),
        "weight_ci95_lo": w_lo,
        "weight_ci95_hi": w_hi,
        "discrimination": disc,
        "leverage": lev,
        "leverage_norm": lev_norm,
        "p_most_important": (np.argmax(weights, axis=1)[:, None] == np.arange(weights.shape[1])).mean(axis=0),
    }


def aligned_q_cube(
    per_factor_q: list[np.ndarray],
    per_factor_item_ids: list[list[int]],
    all_option_ids: list[int],
    n_samples: int,
) -> np.ndarray:
    """Stack per-factor Q draws onto a common option axis. Missing → NaN."""
    n_f = len(per_factor_q)
    n_o = len(all_option_ids)
    cube = np.full((n_samples, n_f, n_o), np.nan, dtype=float)
    index = {oid: i for i, oid in enumerate(all_option_ids)}
    for f, (q, ids) in enumerate(zip(per_factor_q, per_factor_item_ids)):
        if q is None or q.size == 0:
            continue
        take = min(n_samples, q.shape[0])
        for local, oid in enumerate(ids):
            j = index.get(int(oid))
            if j is None:
                continue
            cube[:take, f, j] = q[:take, local]
    return cube


def equal_weight_overall(factor_option_q: np.ndarray) -> np.ndarray:
    if factor_option_q.size == 0:
        return np.zeros((0, 0), dtype=float)
    q = np.asarray(factor_option_q, dtype=float)
    mask = np.isfinite(q)
    counts = mask.sum(axis=1)
    numer = np.where(mask, q, 0.0).sum(axis=1)
    out = np.full(numer.shape, 0.5, dtype=float)
    np.divide(numer, counts, out=out, where=counts > 0)
    return out


def q_draws_from_fit(score_samples, kappa, lapse) -> np.ndarray:
    return q_per_draw(score_samples, kappa=kappa, lapse=lapse)


def overall_rank_summary(overall_u: np.ndarray, top_n: int) -> list[dict]:
    return rank_summary(overall_u, top_n)
