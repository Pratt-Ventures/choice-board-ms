from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import expit

from .observations import PairObs


MU_PRIOR_SD = 2.0
LOG_SIGMA_U_MEAN = float(np.log(1.0))
LOG_SIGMA_U_SD = 0.85
LOGIT_LAPSE_MEAN = float(np.log(0.05 / 0.95))
LOGIT_LAPSE_SD = 1.0
LOG_KAPPA_MEAN = 0.0
LOG_KAPPA_SD = 0.5
BETA_L_SD = 0.3
MIN_HIER_PARTICIPANTS = 2
MIN_HIER_PAIRS = 4


def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1.0 - 1e-6)
    return float(np.log(p / (1.0 - p)))


@dataclass
class ChannelData:
    item_ids: list[int]
    participant_ids: list[int]
    winner_idx: np.ndarray
    loser_idx: np.ndarray
    pid_idx: np.ndarray
    y: np.ndarray
    left_sign: np.ndarray
    use_hierarchy: bool


@dataclass
class ParamLayout:
    n_items: int
    n_part: int
    use_hierarchy: bool
    mu0: int
    u0: int
    log_sigma_u: int | None
    logit_lapse: int
    log_kappa: int
    beta_l: int
    n_params: int


def prepare_channel(obs: list[PairObs], allowed_ids: set[int] | None = None) -> ChannelData | None:
    if not obs:
        return None
    items: list[int] = []
    seen: set[int] = set()
    for o in obs:
        for iid in (o.winner_id, o.loser_id):
            if allowed_ids is not None and iid not in allowed_ids:
                continue
            if iid not in seen:
                seen.add(iid)
                items.append(iid)
    if len(items) < 2:
        return None
    index = {iid: i for i, iid in enumerate(items)}
    kept = [
        o for o in obs
        if o.winner_id in index and o.loser_id in index
    ]
    if not kept:
        return None
    pids: list[int] = []
    pseen: set[int] = set()
    for o in kept:
        if o.participant_id not in pseen:
            pseen.add(o.participant_id)
            pids.append(o.participant_id)
    pindex = {p: i for i, p in enumerate(pids)}
    n_pairs = len(kept)
    use_h = (
        len(pids) >= MIN_HIER_PARTICIPANTS
        and n_pairs >= MIN_HIER_PAIRS
    )
    return ChannelData(
        item_ids=items,
        participant_ids=pids,
        winner_idx=np.array([index[o.winner_id] for o in kept], dtype=int),
        loser_idx=np.array([index[o.loser_id] for o in kept], dtype=int),
        pid_idx=np.array([pindex[o.participant_id] for o in kept], dtype=int),
        y=np.array([o.y for o in kept], dtype=float),
        left_sign=np.array([o.left_sign for o in kept], dtype=float),
        use_hierarchy=use_h,
    )


def layout_for(data: ChannelData) -> ParamLayout:
    n = len(data.item_ids)
    p = len(data.participant_ids)
    n_free = n - 1
    mu0 = 0
    pos = n_free
    u0 = pos
    log_sigma = None
    if data.use_hierarchy:
        pos += p * n_free
        log_sigma = pos
        pos += 1
    logit_lapse = pos
    log_kappa = pos + 1
    beta_l = pos + 2
    return ParamLayout(
        n_items=n,
        n_part=p,
        use_hierarchy=data.use_hierarchy,
        mu0=mu0,
        u0=u0,
        log_sigma_u=log_sigma,
        logit_lapse=logit_lapse,
        log_kappa=log_kappa,
        beta_l=beta_l,
        n_params=pos + 3,
    )


def expand_centered(free: np.ndarray, n: int) -> np.ndarray:
    full = np.empty(n, dtype=float)
    if n <= 1:
        full[0] = 0.0
        return full
    full[:-1] = free
    full[-1] = -float(np.sum(free))
    return full


def pack_initial(data: ChannelData, lay: ParamLayout) -> np.ndarray:
    n = lay.n_items
    x = np.zeros(lay.n_params, dtype=float)
    wins = np.zeros(n, dtype=float)
    np.add.at(wins, data.winner_idx, data.y)
    np.add.at(wins, data.loser_idx, 1.0 - data.y)
    plays = np.zeros(n, dtype=float)
    np.add.at(plays, data.winner_idx, 1.0)
    np.add.at(plays, data.loser_idx, 1.0)
    rate = np.where(plays > 0, wins / np.maximum(plays, 1.0), 0.5)
    raw = np.log(np.clip(rate, 0.05, 0.95) / np.clip(1.0 - rate, 0.05, 0.95))
    raw = raw - raw.mean()
    x[lay.mu0 : lay.mu0 + n - 1] = raw[:-1]
    if lay.log_sigma_u is not None:
        x[lay.log_sigma_u] = LOG_SIGMA_U_MEAN
    x[lay.logit_lapse] = LOGIT_LAPSE_MEAN
    x[lay.log_kappa] = LOG_KAPPA_MEAN
    return x


def decode(x: np.ndarray, lay: ParamLayout) -> dict:
    n = lay.n_items
    mu = expand_centered(x[lay.mu0 : lay.mu0 + n - 1], n)
    lapse = float(expit(x[lay.logit_lapse]))
    kappa = float(np.exp(x[lay.log_kappa]))
    beta_l = float(x[lay.beta_l])
    u = None
    sigma_u = None
    if lay.use_hierarchy:
        n_free = n - 1
        u = np.zeros((lay.n_part, n), dtype=float)
        block = x[lay.u0 : lay.u0 + lay.n_part * n_free].reshape(lay.n_part, n_free)
        for p in range(lay.n_part):
            u[p] = expand_centered(block[p], n)
        sigma_u = float(np.exp(x[lay.log_sigma_u]))
    return {
        "mu": mu,
        "u": u,
        "lapse": lapse,
        "kappa": kappa,
        "beta_l": beta_l,
        "sigma_u": sigma_u,
    }


def _theta(decoded: dict, data: ChannelData) -> np.ndarray:
    mu = decoded["mu"]
    if decoded["u"] is None:
        return mu[None, :].repeat(max(1, len(data.participant_ids)), axis=0)
    return mu[None, :] + decoded["u"]


def neg_log_posterior(x: np.ndarray, data: ChannelData, lay: ParamLayout) -> float:
    d = decode(x, lay)
    theta = _theta(d, data)
    delta = (
        theta[data.pid_idx, data.winner_idx]
        - theta[data.pid_idx, data.loser_idx]
        + d["beta_l"] * data.left_sign
    )
    p = (1.0 - d["lapse"]) * expit(np.clip(d["kappa"] * delta, -40.0, 40.0)) + 0.5 * d["lapse"]
    p = np.clip(p, 1e-12, 1.0 - 1e-12)
    y = data.y
    ll = y * np.log(p) + (1.0 - y) * np.log(1.0 - p)
    nll = -float(ll.sum())

    mu = d["mu"]
    nll += 0.5 * float(np.dot(mu, mu)) / (MU_PRIOR_SD ** 2)

    if d["u"] is not None and d["sigma_u"] is not None:
        sig2 = max(d["sigma_u"] ** 2, 1e-10)
        nll += 0.5 * float(np.sum(d["u"] ** 2)) / sig2
        nll += float(d["u"].size) * np.log(d["sigma_u"])
        z = (x[lay.log_sigma_u] - LOG_SIGMA_U_MEAN) / LOG_SIGMA_U_SD
        nll += 0.5 * float(z * z)

    z = (x[lay.logit_lapse] - LOGIT_LAPSE_MEAN) / LOGIT_LAPSE_SD
    nll += 0.5 * float(z * z)
    z = (x[lay.log_kappa] - LOG_KAPPA_MEAN) / LOG_KAPPA_SD
    nll += 0.5 * float(z * z)
    nll += 0.5 * (d["beta_l"] ** 2) / (BETA_L_SD ** 2)
    return float(nll)


def grad_neg_log_posterior(x: np.ndarray, data: ChannelData, lay: ParamLayout) -> np.ndarray:
    d = decode(x, lay)
    n = lay.n_items
    theta = _theta(d, data)
    delta = (
        theta[data.pid_idx, data.winner_idx]
        - theta[data.pid_idx, data.loser_idx]
        + d["beta_l"] * data.left_sign
    )
    z = np.clip(d["kappa"] * delta, -40.0, 40.0)
    sig = expit(z)
    p = (1.0 - d["lapse"]) * sig + 0.5 * d["lapse"]
    p = np.clip(p, 1e-12, 1.0 - 1e-12)
    y = data.y
    dll_dp = y / p - (1.0 - y) / (1.0 - p)
    dsig_dz = sig * (1.0 - sig)
    dp_dz = (1.0 - d["lapse"]) * dsig_dz
    dp_dlapse = 0.5 - sig
    dll_ddelta = dll_dp * dp_dz * d["kappa"]
    dll_dkappa = dll_dp * dp_dz * delta
    dll_dlapse = dll_dp * dp_dlapse
    dll_dbeta = dll_ddelta * data.left_sign

    g_mu = np.zeros(n, dtype=float)
    np.add.at(g_mu, data.winner_idx, dll_ddelta)
    np.add.at(g_mu, data.loser_idx, -dll_ddelta)

    g = np.zeros(lay.n_params, dtype=float)
    # nll = -ll → flip signs for likelihood terms
    g_mu_nll = -g_mu + mu_prior_grad(d["mu"])
    g[lay.mu0 : lay.mu0 + n - 1] = g_mu_nll[:-1] - g_mu_nll[-1]

    if lay.use_hierarchy and d["u"] is not None and d["sigma_u"] is not None:
        g_u = np.zeros((lay.n_part, n), dtype=float)
        np.add.at(g_u, (data.pid_idx, data.winner_idx), dll_ddelta)
        np.add.at(g_u, (data.pid_idx, data.loser_idx), -dll_ddelta)
        sig2 = max(d["sigma_u"] ** 2, 1e-10)
        g_u_nll = -g_u + d["u"] / sig2
        n_free = n - 1
        for pi in range(lay.n_part):
            sl = lay.u0 + pi * n_free
            g[sl : sl + n_free] = g_u_nll[pi, :-1] - g_u_nll[pi, -1]
        # d nll / d log σ
        nll_dlog = -float(np.sum(d["u"] ** 2)) / sig2 + float(d["u"].size)
        nll_dlog += (x[lay.log_sigma_u] - LOG_SIGMA_U_MEAN) / (LOG_SIGMA_U_SD ** 2)
        g[lay.log_sigma_u] = nll_dlog

    dlapse_dlogit = d["lapse"] * (1.0 - d["lapse"])
    g[lay.logit_lapse] = (
        -float(dll_dlapse.sum()) * dlapse_dlogit
        + (x[lay.logit_lapse] - LOGIT_LAPSE_MEAN) / (LOGIT_LAPSE_SD ** 2)
    )
    g[lay.log_kappa] = (
        -float(dll_dkappa.sum()) * d["kappa"]
        + (x[lay.log_kappa] - LOG_KAPPA_MEAN) / (LOG_KAPPA_SD ** 2)
    )
    g[lay.beta_l] = -float(dll_dbeta.sum()) + d["beta_l"] / (BETA_L_SD ** 2)
    return g


def mu_prior_grad(mu: np.ndarray) -> np.ndarray:
    return mu / (MU_PRIOR_SD ** 2)


def participant_likelihood_grad(
    x: np.ndarray,
    data: ChannelData,
    lay: ParamLayout,
    pid_local: int,
) -> np.ndarray:
    """Gradient of nll from one participant's observations only (no prior)."""
    mask = data.pid_idx == int(pid_local)
    if not np.any(mask):
        return np.zeros(lay.n_params, dtype=float)
    sub = ChannelData(
        item_ids=data.item_ids,
        participant_ids=data.participant_ids,
        winner_idx=data.winner_idx[mask],
        loser_idx=data.loser_idx[mask],
        pid_idx=data.pid_idx[mask],
        y=data.y[mask],
        left_sign=data.left_sign[mask],
        use_hierarchy=data.use_hierarchy,
    )
    d = decode(x, lay)
    n = lay.n_items
    theta = _theta(d, sub)
    delta = (
        theta[sub.pid_idx, sub.winner_idx]
        - theta[sub.pid_idx, sub.loser_idx]
        + d["beta_l"] * sub.left_sign
    )
    z = np.clip(d["kappa"] * delta, -40.0, 40.0)
    sig = expit(z)
    p = (1.0 - d["lapse"]) * sig + 0.5 * d["lapse"]
    p = np.clip(p, 1e-12, 1.0 - 1e-12)
    y = sub.y
    dll_dp = y / p - (1.0 - y) / (1.0 - p)
    dsig_dz = sig * (1.0 - sig)
    dp_dz = (1.0 - d["lapse"]) * dsig_dz
    dll_ddelta = dll_dp * dp_dz * d["kappa"]
    g_mu = np.zeros(n, dtype=float)
    np.add.at(g_mu, sub.winner_idx, dll_ddelta)
    np.add.at(g_mu, sub.loser_idx, -dll_ddelta)
    g = np.zeros(lay.n_params, dtype=float)
    g_mu_nll = -g_mu
    g[lay.mu0 : lay.mu0 + n - 1] = g_mu_nll[:-1] - g_mu_nll[-1]
    return g


def bounds_for(lay: ParamLayout) -> list[tuple[float, float]]:
    b = [(-8.0, 8.0)] * lay.n_params
    n_free = lay.n_items - 1
    if lay.use_hierarchy:
        for i in range(n_free):
            b[lay.mu0 + i] = (-8.0, 8.0)
        if lay.log_sigma_u is not None:
            b[lay.log_sigma_u] = (float(np.log(0.08)), float(np.log(3.5)))
    b[lay.logit_lapse] = (_logit(0.001), _logit(0.35))
    b[lay.log_kappa] = (float(np.log(0.25)), float(np.log(4.0)))
    b[lay.beta_l] = (-2.0, 2.0)
    return b
