from __future__ import annotations

import numpy as np


def posterior_ranks(score_samples: np.ndarray) -> np.ndarray:
    """score_samples [S, items] → ranks [S, items], 1 = best."""
    scores = np.asarray(score_samples, dtype=float)
    if scores.ndim != 2 or scores.shape[1] == 0:
        return np.zeros_like(scores, dtype=int)
    order = np.argsort(-scores, axis=1, kind="stable")
    ranks = np.empty_like(order)
    rows = np.arange(scores.shape[0])[:, None]
    ranks[rows, order] = np.arange(1, scores.shape[1] + 1)
    return ranks


def rank_entropy(rank_samples_i: np.ndarray, n: int) -> float:
    if n <= 1:
        return 0.0
    counts = np.bincount(rank_samples_i.astype(int), minlength=n + 1)[1 : n + 1]
    p = counts / max(1, counts.sum())
    p = p[p > 0]
    if p.size == 0:
        return 0.0
    return float(-(p * np.log(p)).sum())


def rank_summary(score_samples: np.ndarray, top_n: int) -> list[dict]:
    scores = np.asarray(score_samples, dtype=float)
    if scores.ndim != 2 or scores.shape[1] == 0:
        return []
    s_count, n = scores.shape
    if s_count == 0:
        return []
    tn = max(1, min(int(top_n or n), n))
    ranks = posterior_ranks(scores)
    mean_scores = scores.mean(axis=0)
    final_order = np.argsort(-mean_scores, kind="stable")
    assigned = np.empty(n, dtype=int)
    assigned[final_order] = np.arange(1, n + 1)
    log_n = float(np.log(n)) if n > 1 else 1.0
    result = []
    for i in range(n):
        ri = ranks[:, i]
        h = rank_entropy(ri, n)
        result.append({
            "item": i,
            "rank": int(assigned[i]),
            "expected_rank": float(ri.mean()),
            "rank_sd": float(ri.std()),
            "median_rank": float(np.median(ri)),
            "p_exact_rank": float(np.mean(ri == assigned[i])),
            "p_best": float(np.mean(ri == 1)),
            "p_top_n": float(np.mean(ri <= tn)),
            "rank_ci95": [
                float(np.quantile(ri, 0.025)),
                float(np.quantile(ri, 0.975)),
            ],
            "rank_entropy": h,
            "rank_entropy_norm": float(h / log_n) if log_n > 0 else 0.0,
        })
    return result


def pairwise_win_matrix(
    score_samples: np.ndarray,
    kappa: np.ndarray | float = 1.0,
    lapse: np.ndarray | float = 0.0,
) -> np.ndarray:
    """Posterior P(i>j). Diagonal is 0.5."""
    scores = np.asarray(score_samples, dtype=float)
    if scores.ndim != 2 or scores.shape[1] == 0:
        return np.zeros((0, 0), dtype=float)
    s_count, n = scores.shape
    if s_count == 0:
        return np.full((n, n), 0.5)
    kap = np.asarray(kappa, dtype=float)
    if kap.ndim == 0:
        kap = np.full(s_count, float(kap))
    lam = np.asarray(lapse, dtype=float)
    if lam.ndim == 0:
        lam = np.full(s_count, float(lam))
    kap = kap.reshape(s_count, 1, 1)
    lam = lam.reshape(s_count, 1, 1)
    diff = scores[:, :, None] - scores[:, None, :]
    p = (1.0 - lam) * _expit(kap * diff) + 0.5 * lam
    p_mean = p.mean(axis=0)
    np.fill_diagonal(p_mean, 0.5)
    return p_mean


def pairwise_q_from_p(p_mat: np.ndarray) -> np.ndarray:
    n = p_mat.shape[0]
    if n <= 1:
        return np.ones(n, dtype=float)
    out = (p_mat.sum(axis=1) - np.diag(p_mat)) / float(n - 1)
    return np.clip(out, 0.0, 1.0)


def q_per_draw(
    score_samples: np.ndarray,
    kappa: np.ndarray | float = 1.0,
    lapse: np.ndarray | float = 0.0,
) -> np.ndarray:
    """Q_i for every draw. Shape [S, items]."""
    scores = np.asarray(score_samples, dtype=float)
    if scores.ndim != 2 or scores.shape[0] == 0 or scores.shape[1] == 0:
        return np.zeros_like(scores, dtype=float)
    s_count, n = scores.shape
    if n <= 1:
        return np.ones((s_count, n), dtype=float)
    kap = np.asarray(kappa, dtype=float)
    if kap.ndim == 0:
        kap = np.full(s_count, float(kap))
    lam = np.asarray(lapse, dtype=float)
    if lam.ndim == 0:
        lam = np.full(s_count, float(lam))
    kap = kap.reshape(s_count, 1, 1)
    lam = lam.reshape(s_count, 1, 1)
    diff = scores[:, :, None] - scores[:, None, :]
    p = (1.0 - lam) * _expit(kap * diff) + 0.5 * lam
    eye = np.eye(n, dtype=bool)
    p[:, eye] = np.nan
    return np.nanmean(p, axis=2)


def _expit(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40.0, 40.0)))
