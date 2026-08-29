from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import cache as _cache
from . import laplace as bt_laplace
from .laplace import (
    DEFAULT_SAMPLES,
    FitResult,
    approx_loo_winner_shift,
    fit_channel,
    personal_scores,
)
from .model import prepare_channel
from .multifactor import (
    aligned_q_cube,
    combine_factor_draws,
    equal_weight_overall,
    factor_leverage,
)
from .observations import (
    PairObs,
    channel_groups,
    extract_observations,
    fingerprint_observations,
)
from .ranks import pairwise_q_from_p, pairwise_win_matrix, q_per_draw, rank_summary


def _as_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(getattr(item, "__dict__", {}) or {})


def _item_id(d: dict) -> int:
    return int(d.get("id") or 0)


def _title(d: dict, kind: str = "alternative") -> str:
    if kind == "factor":
        return d.get("factor_title") or d.get("title") or f"Factor {_item_id(d)}"
    return d.get("alternative_title") or d.get("title") or f"Option {_item_id(d)}"


def _desc(d: dict) -> Any:
    return d.get("alternative_description") or d.get("factor_description") or d.get("description")


def resolve_top_n(mode: str | None, n: int, exclusive_mode: bool = False) -> tuple[str, int]:
    m = str(mode or "").strip().lower().replace("-", "_")
    if not m:
        m = "find_best" if exclusive_mode else "rank_all"
    n = max(1, int(n or 1))
    if m in ("find_best", "winner", "pick_one"):
        return "find_best", 1
    if m in ("find_top_3", "top_3", "top3"):
        return "find_top_3", min(3, n)
    if m in ("find_top_half", "top_half"):
        return "find_top_half", max(1, n // 2)
    return "rank_all", n


def _seed_from_fp(fp: str) -> int:
    return int(fp[:8], 16) % (2**31)


@dataclass
class ProjectInference:
    option_ranking: list[dict] = field(default_factory=list)
    option_ranking_equal: list[dict] = field(default_factory=list)
    factor_ranking: list[dict] = field(default_factory=list)
    factor_weights: dict[int, float] = field(default_factory=dict)
    by_factor: dict[int, list[dict]] = field(default_factory=dict)
    by_pid: dict[int, dict] = field(default_factory=dict)
    coherence: dict = field(default_factory=dict)
    posterior_stability: dict = field(default_factory=dict)
    diagnostics: dict = field(default_factory=dict)
    top_n: int = 1
    ranking_mode: str = "rank_all"
    pairwise: dict[str, Any] = field(default_factory=dict)
    cache_hit: bool = False


def infer_project(
    *,
    alternatives: list | None,
    factors: list | None,
    all_groups: list | None,
    settings: dict | None = None,
    exclusive_mode: bool = False,
    project_id: int | None = None,
) -> ProjectInference:
    cfg = dict(settings or {})
    alts = [_as_dict(a) for a in (alternatives or []) if not _as_dict(a).get("disabled")]
    facs = [_as_dict(f) for f in (factors or []) if not _as_dict(f).get("disabled")]
    obs = extract_observations(all_groups)
    n_alts = len(alts)
    mode, top_n = resolve_top_n(cfg.get("ranking_mode"), n_alts or 1, exclusive_mode)
    n_samples = int(cfg.get("bt_n_samples") or DEFAULT_SAMPLES)
    n_samples = max(80, min(2000, n_samples))
    extra = f"{project_id or 0}:{mode}:{top_n}:{n_samples}:{n_alts}"
    fp = fingerprint_observations(obs)
    key = _cache.cache_key(fp, extra)
    cached, age_ms = _cache.get(key)
    if cached is not None:
        inf = _inference_from_dict(cached)
        inf.cache_hit = True
        inf.diagnostics = dict(inf.diagnostics)
        inf.diagnostics["cache_hit"] = True
        inf.diagnostics["cache_age_ms"] = age_ms
        return inf

    t0 = time.perf_counter()
    result = _infer_uncached(
        alts=alts,
        facs=facs,
        obs=obs,
        top_n=top_n,
        ranking_mode=mode,
        n_samples=n_samples,
        seed=_seed_from_fp(fp),
    )
    result.diagnostics["fit_ms"] = (time.perf_counter() - t0) * 1000.0
    result.diagnostics["cache_hit"] = False
    result.diagnostics["fingerprint"] = fp
    _cache.put(key, _inference_to_dict(result))
    return result


def _infer_uncached(
    *,
    alts: list[dict],
    facs: list[dict],
    obs: list[PairObs],
    top_n: int,
    ranking_mode: str,
    n_samples: int,
    seed: int,
) -> ProjectInference:
    out = ProjectInference(top_n=top_n, ranking_mode=ranking_mode)
    if not obs or not alts:
        out.diagnostics = {
            "model": "hierarchical_bt_laplace",
            "n_samples": n_samples,
            "legacy_rank_only_groups": 0,
            "in_progress_pairings": 0,
            "empty": True,
        }
        return out

    alt_ids = [_item_id(a) for a in alts]
    fac_ids = [_item_id(f) for f in facs]
    alt_set = set(alt_ids)
    fac_set = set(fac_ids)
    grouped = channel_groups(obs)
    legacy_n = sum(1 for o in obs if o.legacy)

    option_fits: dict[int | None, FitResult] = {}
    factor_fit: FitResult | None = None
    connected: dict[str, bool] = {}
    coverage: dict[str, float] = {}

    for (channel, fid), cob in grouped.items():
        if channel == "factor":
            data = prepare_channel(cob, fac_set or None)
            if data is None:
                continue
            factor_fit = fit_channel(data, n_samples=n_samples, seed=seed + 17)
            connected["factors"] = _graph_connected(data)
            coverage["factors"] = _coverage(data)
        else:
            data = prepare_channel(cob, alt_set)
            if data is None:
                continue
            fit = fit_channel(data, n_samples=n_samples, seed=seed + (int(fid or 0) * 13 + 3))
            option_fits[fid] = fit
            key = f"option:{fid if fid is not None else 0}"
            connected[key] = _graph_connected(data)
            coverage[key] = _coverage(data)

    factor_channels = {k: v for k, v in option_fits.items() if k is not None and int(k) != 0}
    overall_only = option_fits.get(None) or option_fits.get(0)

    by_factor_rankings: dict[int, list[dict]] = {}
    q_list: list[np.ndarray] = []
    q_ids: list[list[int]] = []
    latent_list: list[np.ndarray] = []
    factor_order: list[int] = []

    for fid in (fac_ids if fac_ids else list(factor_channels.keys())):
        fit = factor_channels.get(int(fid))
        if fit is None:
            continue
        q = q_per_draw(fit.mu_samples, fit.kappa_samples, fit.lapse_samples)
        pmat = pairwise_win_matrix(fit.mu_samples, fit.kappa_samples, fit.lapse_samples)
        q_mean = pairwise_q_from_p(pmat)
        summary = rank_summary(fit.mu_samples, top_n)
        ranking = _entries_from_fit(summary, fit.item_ids, alts, "alternative", q_mean, fit.n_obs)
        _append_missing(ranking, alts, "alternative", set(fit.item_ids))
        by_factor_rankings[int(fid)] = ranking
        q_list.append(q)
        q_ids.append(list(fit.item_ids))
        latent_list.append(fit.mu_samples)
        factor_order.append(int(fid))

    factor_ranking: list[dict] = []
    factor_weights: dict[int, float] = {}
    weights_draws = None
    overall_u = None
    overall_u_eq = None
    lev = None

    if factor_fit is not None and factor_order:
        w_latent = _align_factor_latent(factor_fit, factor_order, n_samples)
        cube = aligned_q_cube(q_list, q_ids, alt_ids, w_latent.shape[0])
        weights_draws, overall_u = combine_factor_draws(w_latent, cube)
        overall_u_eq = equal_weight_overall(cube)
        lev = factor_leverage(weights_draws, cube)
        pmat_f = pairwise_win_matrix(factor_fit.mu_samples, factor_fit.kappa_samples, factor_fit.lapse_samples)
        q_f = pairwise_q_from_p(pmat_f)
        f_summary = rank_summary(factor_fit.mu_samples, max(1, len(factor_fit.item_ids)))
        w_mean = {
            int(fid): float(weights_draws[:, i].mean())
            for i, fid in enumerate(factor_order)
        }
        factor_weights = dict(w_mean)
        factor_ranking = _entries_from_fit(
            f_summary, factor_fit.item_ids, facs, "factor", q_f, factor_fit.n_obs, weights=w_mean
        )
        _apply_factor_leverage(factor_ranking, factor_order, lev, factor_fit)
        _append_missing(factor_ranking, facs, "factor", set(factor_fit.item_ids))
    elif factor_fit is not None:
        pmat_f = pairwise_win_matrix(factor_fit.mu_samples, factor_fit.kappa_samples, factor_fit.lapse_samples)
        q_f = pairwise_q_from_p(pmat_f)
        f_summary = rank_summary(factor_fit.mu_samples, max(1, len(factor_fit.item_ids)))
        n_f = max(1, len(factor_fit.item_ids))
        eq_w = {int(i): 1.0 / n_f for i in factor_fit.item_ids}
        factor_weights = eq_w
        factor_ranking = _entries_from_fit(
            f_summary, factor_fit.item_ids, facs, "factor", q_f, factor_fit.n_obs, weights=eq_w
        )
        _append_missing(factor_ranking, facs, "factor", set(factor_fit.item_ids))

    if overall_u is not None:
        summary = rank_summary(overall_u, top_n)
        q_over = overall_u.mean(axis=0)
        option_ranking = _entries_from_fit(summary, alt_ids, alts, "alternative", q_over, _total_obs(option_fits))
        _append_missing(option_ranking, alts, "alternative", set(alt_ids))
        if overall_u_eq is not None:
            s_eq = rank_summary(overall_u_eq, top_n)
            option_ranking_equal = _entries_from_fit(
                s_eq, alt_ids, alts, "alternative", overall_u_eq.mean(axis=0), _total_obs(option_fits)
            )
            _append_missing(option_ranking_equal, alts, "alternative", set(alt_ids))
        else:
            option_ranking_equal = [dict(r) for r in option_ranking]
        score_for_coh = overall_u
        kap_for_p = 1.0
        lam_for_p = 0.0
    elif overall_only is not None:
        pmat = pairwise_win_matrix(
            overall_only.mu_samples, overall_only.kappa_samples, overall_only.lapse_samples
        )
        q_mean = pairwise_q_from_p(pmat)
        summary = rank_summary(overall_only.mu_samples, top_n)
        option_ranking = _entries_from_fit(
            summary, overall_only.item_ids, alts, "alternative", q_mean, overall_only.n_obs
        )
        _append_missing(option_ranking, alts, "alternative", set(overall_only.item_ids))
        option_ranking_equal = [dict(r) for r in option_ranking]
        score_for_coh = overall_only.mu_samples
        kap_for_p = overall_only.kappa_samples
        lam_for_p = overall_only.lapse_samples
    elif factor_channels:
        # no factor-importance data: equal-weight combine
        cube = aligned_q_cube(q_list, q_ids, alt_ids, n_samples)
        overall_u_eq = equal_weight_overall(cube)
        summary = rank_summary(overall_u_eq, top_n)
        option_ranking = _entries_from_fit(
            summary, alt_ids, alts, "alternative", overall_u_eq.mean(axis=0), _total_obs(option_fits)
        )
        _append_missing(option_ranking, alts, "alternative", set(alt_ids))
        option_ranking_equal = [dict(r) for r in option_ranking]
        score_for_coh = overall_u_eq
        kap_for_p = 1.0
        lam_for_p = 0.0
        n_f = len(factor_order)
        if n_f:
            factor_weights = {int(fid): 1.0 / n_f for fid in factor_order}
            if not factor_ranking:
                dummy_scores = np.zeros((n_samples, n_f))
                f_summary = rank_summary(dummy_scores, n_f)
                q_f = np.full(n_f, 0.5)
                factor_ranking = _entries_from_fit(
                    f_summary, factor_order, facs, "factor", q_f, 0, weights=factor_weights
                )
    else:
        option_ranking = []
        option_ranking_equal = []
        score_for_coh = np.zeros((0, 0))
        kap_for_p = 1.0
        lam_for_p = 0.0

    _annotate_polarizing(option_ranking, option_fits, alt_ids)

    by_pid = _personal_bundles(
        alts=alts,
        facs=facs,
        obs=obs,
        option_fits=option_fits,
        factor_fit=factor_fit,
        factor_order=factor_order,
        q_list=q_list,
        q_ids=q_ids,
        alt_ids=alt_ids,
        top_n=top_n,
        n_samples=n_samples,
        seed=seed,
        overall_u=overall_u,
        overall_u_eq=overall_u_eq,
    )

    pmat_overall = None
    if isinstance(score_for_coh, np.ndarray) and score_for_coh.size:
        pmat_overall = pairwise_win_matrix(score_for_coh, kap_for_p, lam_for_p)

    if overall_u is not None:
        score_item_ids: list[int] | None = list(alt_ids)
    elif overall_only is not None:
        score_item_ids = list(overall_only.item_ids)
    elif overall_u_eq is not None:
        score_item_ids = list(alt_ids)
    else:
        score_item_ids = None

    coherence, stability = _coherence_and_stability(
        score_samples=score_for_coh if isinstance(score_for_coh, np.ndarray) else np.zeros((0, 0)),
        pmat=pmat_overall,
        option_ranking=option_ranking,
        by_pid=by_pid,
        top_n=top_n,
        option_fits=option_fits,
        overall_only=overall_only,
        score_item_ids=score_item_ids,
    )

    first_fit = next(iter(option_fits.values()), factor_fit)
    out.option_ranking = option_ranking
    out.option_ranking_equal = option_ranking_equal
    out.factor_ranking = factor_ranking
    out.factor_weights = factor_weights
    out.by_factor = by_factor_rankings
    out.by_pid = by_pid
    out.coherence = coherence
    out.posterior_stability = stability
    out.diagnostics = {
        "model": "hierarchical_bt_laplace",
        "n_samples": n_samples,
        "legacy_rank_only_groups": legacy_n,
        "pairings_used": len(obs),
        "channels": list(connected.keys()),
        "graph_connected": connected,
        "coverage": coverage,
        "left_right_bias": float(first_fit.beta_l_map) if first_fit else 0.0,
        "lapse": float(first_fit.lapse_map) if first_fit else None,
        "kappa": float(first_fit.kappa_map) if first_fit else None,
        "sigma_u": float(first_fit.sigma_u_map) if first_fit and first_fit.sigma_u_map is not None else None,
        "converged": all(
            f.converged for f in list(option_fits.values()) + ([factor_fit] if factor_fit else [])
        ),
        "fit_calls": bt_laplace.FIT_CALLS,
    }
    out.pairwise = {"overall": pmat_overall.tolist() if pmat_overall is not None else None}
    return out


def _total_obs(fits: dict) -> int:
    return sum(f.n_obs for f in fits.values())


def _graph_connected(data) -> bool:
    n = len(data.item_ids)
    if n <= 1:
        return True
    adj = {i: set() for i in range(n)}
    for a, b in zip(data.winner_idx.tolist(), data.loser_idx.tolist()):
        adj[a].add(b)
        adj[b].add(a)
    seen = set()
    stack = [0]
    while stack:
        i = stack.pop()
        if i in seen:
            continue
        seen.add(i)
        stack.extend(adj[i] - seen)
    return len(seen) == n


def _coverage(data) -> float:
    n = len(data.item_ids)
    if n < 2:
        return 1.0
    pairs = {
        tuple(sorted((int(a), int(b))))
        for a, b in zip(data.winner_idx.tolist(), data.loser_idx.tolist())
        if a != b
    }
    return float(len(pairs) / (n * (n - 1) / 2.0))


def _align_factor_latent(fit: FitResult, factor_order: list[int], n_samples: int) -> np.ndarray:
    idx = {int(i): k for k, i in enumerate(fit.item_ids)}
    s = min(n_samples, fit.mu_samples.shape[0])
    out = np.zeros((s, len(factor_order)), dtype=float)
    for j, fid in enumerate(factor_order):
        k = idx.get(int(fid))
        if k is not None:
            out[:, j] = fit.mu_samples[:s, k]
    return out


def _entries_from_fit(
    summary: list[dict],
    item_ids: list[int],
    catalog: list[dict],
    kind: str,
    q_scores: np.ndarray,
    n_obs: int,
    weights: dict[int, float] | None = None,
) -> list[dict]:
    by_id = {_item_id(i): i for i in catalog}
    q = np.asarray(q_scores, dtype=float)
    rows = []
    for s in sorted(summary, key=lambda r: (r["rank"], item_ids[r["item"]])):
        local = int(s["item"])
        iid = int(item_ids[local])
        d = by_id.get(iid) or {"id": iid}
        qi = float(q[local]) if local < q.size else 0.5
        n = max(1, len(item_ids))
        er = float(s["expected_rank"])
        entry = {
            "id": iid,
            "title": _title(d, kind),
            "description": _desc(d),
            "mean_rank": er - 1.0,
            "rank": int(s["rank"]) - 1,
            "score": qi,
            "preference": qi * float(max(1, n - 1)),
            "evidence": int(n_obs),
            "data_points": int(n_obs),
            "expected_rank": er,
            "rank_sd": float(s.get("rank_sd") or 0.0),
            "median_rank": float(s["median_rank"]),
            "p_exact_rank": float(s["p_exact_rank"]),
            "p_best": float(s["p_best"]),
            "p_top_n": float(s["p_top_n"]),
            "rank_ci95": [float(s["rank_ci95"][0]), float(s["rank_ci95"][1])],
            "rank_entropy": float(s.get("rank_entropy") or 0.0),
            "pairwise_win_strength": qi,
        }
        if weights is not None and iid in weights:
            entry["normalizedWeight"] = float(weights[iid])
            entry["weight"] = float(weights[iid])
        rows.append(entry)
    return rows


def _append_missing(rows: list[dict], catalog: list[dict], kind: str, present: set[int]) -> None:
    if not rows and not catalog:
        return
    have = {int(r["id"]) for r in rows}
    for d in catalog:
        iid = _item_id(d)
        if iid in have:
            continue
        rows.append({
            "id": iid,
            "title": _title(d, kind),
            "description": _desc(d),
            "mean_rank": None,
            "rank": len(rows),
            "score": 0.0,
            "preference": 0.0,
            "evidence": 0,
            "data_points": 0,
        })


def _apply_factor_leverage(
    ranking: list[dict],
    factor_order: list[int],
    lev: dict,
    fit: FitResult,
) -> None:
    pos = {int(fid): i for i, fid in enumerate(factor_order)}
    fpos = {int(i): k for k, i in enumerate(fit.item_ids)}
    f_sum = rank_summary(fit.mu_samples, max(1, len(fit.item_ids)))
    f_by_local = {int(s["item"]): s for s in f_sum}
    for row in ranking:
        fid = int(row["id"])
        j = pos.get(fid)
        if j is None:
            continue
        row["weight_ci95"] = [
            float(lev["weight_ci95_lo"][j]),
            float(lev["weight_ci95_hi"][j]),
        ]
        row["discrimination"] = float(lev["discrimination"][j])
        row["leverage"] = float(lev["leverage_norm"][j])
        row["p_most_important"] = float(lev["p_most_important"][j])
        loc = fpos.get(fid)
        if loc is not None and loc in f_by_local:
            row["p_best"] = float(f_by_local[loc]["p_best"])
            row["expected_rank"] = float(f_by_local[loc]["expected_rank"])
            row["rank_sd"] = float(f_by_local[loc].get("rank_sd") or 0.0)
            row["rank_ci95"] = [
                float(f_by_local[loc]["rank_ci95"][0]),
                float(f_by_local[loc]["rank_ci95"][1]),
            ]


def _annotate_polarizing(
    option_ranking: list[dict],
    option_fits: dict[int | None, FitResult],
    alt_ids: list[int],
) -> None:
    personal_ranks: dict[int, list[float]] = {i: [] for i in alt_ids}
    for fit in option_fits.values():
        if fit.u_samples is None:
            continue
        for pi, pid in enumerate(fit.participant_ids):
            scores = fit.mu_samples + fit.u_samples[:, pi, :]
            mean_s = scores.mean(axis=0)
            order = np.argsort(-mean_s, kind="stable")
            ranks = np.empty_like(order)
            ranks[order] = np.arange(1, order.size + 1)
            for local, iid in enumerate(fit.item_ids):
                personal_ranks.setdefault(int(iid), []).append(float(ranks[local]))
    for row in option_ranking:
        vals = personal_ranks.get(int(row["id"])) or []
        if len(vals) >= 2:
            sd = float(np.std(vals))
            row["participant_rank_sd"] = sd
            n = max(1, len(alt_ids) - 1)
            row["polarizing"] = sd > 0.35 * n
        else:
            row["participant_rank_sd"] = 0.0
            row["polarizing"] = False


def _fit_personal_channel(obs: list[PairObs], allowed: set[int], n_samples: int, seed: int) -> FitResult | None:
    data = prepare_channel(obs, allowed)
    if data is None:
        return None
    data.use_hierarchy = False
    return fit_channel(data, n_samples=max(80, min(n_samples, 240)), seed=seed)


def _personal_bundles(
    *,
    alts,
    facs,
    obs: list[PairObs],
    option_fits,
    factor_fit,
    factor_order,
    q_list,
    q_ids,
    alt_ids,
    top_n,
    n_samples,
    seed: int,
    overall_u,
    overall_u_eq,
) -> dict[int, dict]:
    pids: set[int] = set()
    for fit in option_fits.values():
        pids.update(fit.participant_ids)
    if factor_fit is not None:
        pids.update(factor_fit.participant_ids)
    for o in obs:
        pids.add(int(o.participant_id))
    grouped = channel_groups(obs)
    out: dict[int, dict] = {}
    for pid in sorted(pids):
        by_f_ranks: dict[int, dict[int, float]] = {}
        by_f_q: list[np.ndarray] = []
        by_f_ids: list[list[int]] = []
        used_fids: list[int] = []
        for fid, fit in option_fits.items():
            if fid is None or int(fid) == 0:
                continue
            own = [o for o in grouped.get(("option", fid), []) if int(o.participant_id) == int(pid)]
            pfit = _fit_personal_channel(own, set(fit.item_ids), n_samples, seed + 100 + int(pid) + int(fid))
            scores = pfit.mu_samples if pfit is not None else personal_scores(fit, pid)
            kap = pfit.kappa_samples if pfit is not None else fit.kappa_samples
            lam = pfit.lapse_samples if pfit is not None else fit.lapse_samples
            item_ids = list(pfit.item_ids) if pfit is not None else list(fit.item_ids)
            summary = rank_summary(scores, top_n)
            ranks = {int(item_ids[s["item"]]): float(s["expected_rank"] - 1.0) for s in summary}
            by_f_ranks[int(fid)] = ranks
            by_f_q.append(q_per_draw(scores, kap, lam))
            by_f_ids.append(item_ids)
            used_fids.append(int(fid))
        overall_ranks: dict[int, float] = {}
        overall_eq_ranks: dict[int, float] = {}
        if used_fids and factor_fit is not None:
            own_f = [o for o in grouped.get(("factor", None), []) if int(o.participant_id) == int(pid)]
            f_pfit = _fit_personal_channel(
                own_f, set(factor_fit.item_ids), n_samples, seed + 500 + int(pid)
            )
            pers_lat = f_pfit.mu_samples if f_pfit is not None else personal_scores(factor_fit, pid)
            lat_ids = list(f_pfit.item_ids) if f_pfit is not None else list(factor_fit.item_ids)
            idx = {int(i): k for k, i in enumerate(lat_ids)}
            q_len = min(arr.shape[0] for arr in by_f_q) if by_f_q else pers_lat.shape[0]
            take = min(n_samples, pers_lat.shape[0], q_len)
            lat = np.zeros((take, len(used_fids)))
            for j, fid in enumerate(used_fids):
                k = idx.get(int(fid))
                if k is not None:
                    lat[:, j] = pers_lat[:take, k]
            cube = aligned_q_cube(by_f_q, by_f_ids, alt_ids, take)
            w, u = combine_factor_draws(lat, cube)
            u_eq = equal_weight_overall(cube)
            s_u = rank_summary(u, top_n)
            s_eq = rank_summary(u_eq, top_n)
            overall_ranks = {int(alt_ids[s["item"]]): float(s["expected_rank"] - 1.0) for s in s_u}
            overall_eq_ranks = {int(alt_ids[s["item"]]): float(s["expected_rank"] - 1.0) for s in s_eq}
            q_over = u.mean(axis=0)
            option_ranking = _entries_from_fit(s_u, alt_ids, alts, "alternative", q_over, 0)
            option_ranking_equal = _entries_from_fit(s_eq, alt_ids, alts, "alternative", u_eq.mean(axis=0), 0)
        elif option_fits.get(None) or option_fits.get(0):
            fit = option_fits.get(None) or option_fits.get(0)
            own = [
                o for o in (grouped.get(("option", None), []) + grouped.get(("option", 0), []))
                if int(o.participant_id) == int(pid)
            ]
            pfit = _fit_personal_channel(own, set(fit.item_ids), n_samples, seed + 300 + int(pid))
            scores = pfit.mu_samples if pfit is not None else personal_scores(fit, pid)
            if pfit is not None:
                fit = pfit
            pmat = pairwise_win_matrix(scores, fit.kappa_samples, fit.lapse_samples)
            q_mean = pairwise_q_from_p(pmat)
            summary = rank_summary(scores, top_n)
            overall_ranks = {int(fit.item_ids[s["item"]]): float(s["expected_rank"] - 1.0) for s in summary}
            overall_eq_ranks = dict(overall_ranks)
            option_ranking = _entries_from_fit(summary, fit.item_ids, alts, "alternative", q_mean, fit.n_obs)
            option_ranking_equal = [dict(r) for r in option_ranking]
        elif used_fids:
            cube = aligned_q_cube(by_f_q, by_f_ids, alt_ids, n_samples)
            u_eq = equal_weight_overall(cube)
            s_eq = rank_summary(u_eq, top_n)
            overall_ranks = {int(alt_ids[s["item"]]): float(s["expected_rank"] - 1.0) for s in s_eq}
            overall_eq_ranks = dict(overall_ranks)
            option_ranking = _entries_from_fit(s_eq, alt_ids, alts, "alternative", u_eq.mean(axis=0), 0)
            option_ranking_equal = [dict(r) for r in option_ranking]
        else:
            option_ranking = []
            option_ranking_equal = []

        factor_ranks: dict[int, float] = {}
        factor_ranking = []
        fweights: dict[int, float] = {}
        if factor_fit is not None:
            scores = personal_scores(factor_fit, pid)
            pmat = pairwise_win_matrix(scores, factor_fit.kappa_samples, factor_fit.lapse_samples)
            q_f = pairwise_q_from_p(pmat)
            fs = rank_summary(scores, max(1, len(factor_fit.item_ids)))
            factor_ranks = {int(factor_fit.item_ids[s["item"]]): float(s["expected_rank"] - 1.0) for s in fs}
            from .multifactor import softmax
            w = softmax(scores, axis=1).mean(axis=0)
            fweights = {int(i): float(w[k]) for k, i in enumerate(factor_fit.item_ids)}
            factor_ranking = _entries_from_fit(
                fs, factor_fit.item_ids, facs, "factor", q_f, factor_fit.n_obs, weights=fweights
            )

        out[int(pid)] = {
            "option_ranking": option_ranking,
            "option_ranking_equal": option_ranking_equal,
            "factor_ranking": factor_ranking,
            "option_ranks_by_factor": by_f_ranks,
            "overall_option_ranks": overall_ranks,
            "overall_option_ranks_equal": overall_eq_ranks,
            "factor_ranks": factor_ranks,
            "factor_weights": fweights,
        }
    return out


def _coherence_and_stability(
    *,
    score_samples: np.ndarray,
    pmat: np.ndarray | None,
    option_ranking: list[dict],
    by_pid: dict[int, dict],
    top_n: int,
    option_fits: dict,
    overall_only,
    score_item_ids: list[int] | None = None,
) -> tuple[dict, dict]:
    directional = 0.0
    pair_agree = 0.0
    if pmat is not None and pmat.size:
        n = pmat.shape[0]
        vals_c = []
        vals_a = []
        for i in range(n):
            for j in range(i + 1, n):
                p = float(pmat[i, j])
                vals_c.append(abs(2.0 * p - 1.0))
                vals_a.append(p * p + (1.0 - p) * (1.0 - p))
        if vals_c:
            directional = float(sum(vals_c) / len(vals_c))
            pair_agree = float(sum(vals_a) / len(vals_a))

    consensus_ranks = {
        int(r["id"]): float(r["mean_rank"])
        for r in option_ranking
        if r.get("mean_rank") is not None
    }
    kendalls = []
    jaccards = []
    from ..vote_ranking import kendall_tau

    cons_top = _top_ids(consensus_ranks, top_n)
    for bundle in by_pid.values():
        pr = bundle.get("overall_option_ranks") or {}
        if pr and consensus_ranks:
            kt = kendall_tau(pr, consensus_ranks)
            if kt is not None:
                kendalls.append(kt)
            jaccards.append(_jaccard(cons_top, _top_ids(pr, top_n)))
    kendall_mean = float(sum(kendalls) / len(kendalls)) if kendalls else None
    jaccard_mean = float(sum(jaccards) / len(jaccards)) if jaccards else None

    same_winner = 0.0
    same_top_n = 0.0
    if isinstance(score_samples, np.ndarray) and score_samples.size and option_ranking:
        from .ranks import posterior_ranks

        ranks = posterior_ranks(score_samples)
        winner_id = int(option_ranking[0]["id"])
        # Columns correspond to score_item_ids order (alt_ids or fit.item_ids), not ranking order.
        # Using ranking order as column identity was a bug that mapped the winner to the wrong draw column
        # and produced 0.0 for projects where the winner was not the first option.
        if score_item_ids is not None:
            id_to_col = {int(aid): i for i, aid in enumerate(score_item_ids)}
        else:
            scored = [r for r in option_ranking if r.get("mean_rank") is not None]
            id_to_col = {int(r["id"]): i for i, r in enumerate(scored)}
        wcol = id_to_col.get(winner_id)
        if wcol is not None and wcol < ranks.shape[1]:
            same_winner = float(np.mean(ranks[:, wcol] == 1))
        else:
            # Fallback to ranking's marginal p_best when column identity is unavailable
            try:
                same_winner = float(option_ranking[0].get("p_best") or 0.0)
            except Exception:
                same_winner = 0.0
        cons_set = set(range(min(top_n, ranks.shape[1])))
        # top-n columns of consensus — use same column identity as winner
        cons_cols = {id_to_col[i] for i in cons_top if i in id_to_col}
        if cons_cols and score_item_ids is not None:
            hits = 0
            for s in range(ranks.shape[0]):
                draw_top = set(np.where(ranks[s] <= top_n)[0].tolist())
                hits += int(draw_top == cons_cols)
            same_top_n = hits / float(ranks.shape[0])
        elif cons_cols and score_item_ids is None:
            # Without column identity we cannot compute joint top-N correctly; keep 0 rather than a wrong 1.0
            same_top_n = 0.0

    max_inf = 0.0
    fit = overall_only or next(iter(option_fits.values()), None)
    if fit is not None and option_ranking:
        scored = [r for r in option_ranking if r.get("mean_rank") is not None]
        id_to_local = {int(iid): k for k, iid in enumerate(fit.item_ids)}
        wlocal = id_to_local.get(int(option_ranking[0]["id"]))
        if wlocal is not None:
            max_inf = approx_loo_winner_shift(fit, wlocal)

    coherence = {
        "directional": directional,
        "expected_pair_agreement": pair_agree,
        "participant_consensus_kendall": kendall_mean,
        "top_n_jaccard": jaccard_mean,
        "cycle_rate": None,
    }
    stability = {
        "same_winner_repeat_probability": same_winner,
        "same_top_n_repeat_probability": same_top_n,
        "max_single_participant_influence": max_inf,
    }
    return coherence, stability


def _top_ids(ranks: dict[int, float], top_n: int) -> set[int]:
    if not ranks:
        return set()
    ordered = sorted(ranks.keys(), key=lambda i: (ranks[i], i))
    return set(ordered[: max(1, int(top_n))])


def _jaccard(a: set[int], b: set[int]) -> float:
    if not a and not b:
        return 1.0
    u = a | b
    if not u:
        return 1.0
    return len(a & b) / float(len(u))


def _inference_to_dict(inf: ProjectInference) -> dict:
    return {
        "option_ranking": inf.option_ranking,
        "option_ranking_equal": inf.option_ranking_equal,
        "factor_ranking": inf.factor_ranking,
        "factor_weights": inf.factor_weights,
        "by_factor": inf.by_factor,
        "by_pid": inf.by_pid,
        "coherence": inf.coherence,
        "posterior_stability": inf.posterior_stability,
        "diagnostics": inf.diagnostics,
        "top_n": inf.top_n,
        "ranking_mode": inf.ranking_mode,
        "pairwise": inf.pairwise,
    }


def _inference_from_dict(d: dict) -> ProjectInference:
    fw = d.get("factor_weights") or {}
    fw = {int(k): float(v) for k, v in fw.items()}
    by_f = d.get("by_factor") or {}
    by_f = {int(k): v for k, v in by_f.items()}
    by_pid = d.get("by_pid") or {}
    by_pid = {int(k): v for k, v in by_pid.items()}
    return ProjectInference(
        option_ranking=d.get("option_ranking") or [],
        option_ranking_equal=d.get("option_ranking_equal") or [],
        factor_ranking=d.get("factor_ranking") or [],
        factor_weights=fw,
        by_factor=by_f,
        by_pid=by_pid,
        coherence=d.get("coherence") or {},
        posterior_stability=d.get("posterior_stability") or {},
        diagnostics=d.get("diagnostics") or {},
        top_n=int(d.get("top_n") or 1),
        ranking_mode=str(d.get("ranking_mode") or "rank_all"),
        pairwise=d.get("pairwise") or {},
    )


def build_report_v2(
    *,
    alternatives: list | None,
    factors: list | None,
    exclusive_mode: bool = False,
    all_groups: list | None = None,
    all_observations: list | None = None,
    participants: list | None = None,
    settings: dict | None = None,
    project_id: int | None = None,
) -> dict:
    from .. import vote_ranking as vr

    groups = all_groups if all_groups is not None else all_observations
    inferred = infer_project(
        alternatives=alternatives,
        factors=factors,
        all_groups=groups,
        settings=settings,
        exclusive_mode=exclusive_mode,
        project_id=project_id,
    )
    return _assemble_report(
        inferred=inferred,
        alternatives=alternatives,
        factors=factors,
        exclusive_mode=exclusive_mode,
        groups=groups,
        participants=participants,
        settings=settings,
        vr=vr,
    )


def _assemble_report(
    *,
    inferred: ProjectInference,
    alternatives,
    factors,
    exclusive_mode: bool,
    groups,
    participants,
    settings,
    vr,
) -> dict:
    gs = vr._groups(groups)
    alts = [_as_dict(a) for a in (alternatives or []) if not _as_dict(a).get("disabled")]
    facs = [_as_dict(f) for f in (factors or []) if not _as_dict(f).get("disabled")]
    parts = [_as_dict(p) for p in (participants or [])]
    cfg = dict(vr.DEFAULT_SETTINGS)
    if settings:
        cfg.update(settings)
    coherence_method = str(cfg.get("coherence_method") or "spearman").lower()
    if coherence_method not in ("spearman", "kendall"):
        coherence_method = "spearman"
    floor_alpha = vr.clamp_factor_weight_floor_alpha(cfg.get("factor_weight_floor_alpha"))
    weight_map = vr.build_participant_influence_weight_map(
        gs, cfg.get("participant_influence_mode"), cfg.get("participant_influence_min_comparisons"),
    )
    mode = vr.normalize_participant_influence_mode(cfg.get("participant_influence_mode"))

    pids = sorted({int(g.get("participant_id") or 0) for g in gs if g.get("participant_id")})
    extra_pids = sorted(inferred.by_pid.keys())
    for pid in extra_pids:
        if pid not in pids:
            pids.append(pid)
    if not pids and parts:
        pids = [int(p.get("id") or 0) for p in parts if p.get("id")]

    participant_rows = []
    bundle_list = []
    for pid in pids:
        pgroups = vr.groups_for_participant(gs, pid)
        inferred_b = inferred.by_pid.get(int(pid)) or {}
        if inferred_b:
            bundle = {
                "option_ranking": inferred_b.get("option_ranking") or [],
                "option_ranking_equal": inferred_b.get("option_ranking_equal") or [],
                "factor_ranking": inferred_b.get("factor_ranking") or [],
                "option_ranks_by_factor": inferred_b.get("option_ranks_by_factor") or {},
                "overall_option_ranks": inferred_b.get("overall_option_ranks") or {},
                "overall_option_ranks_equal": inferred_b.get("overall_option_ranks_equal") or {},
                "factor_ranks": inferred_b.get("factor_ranks") or {},
                "factor_weights": inferred_b.get("factor_weights") or {},
                "group_count": len(pgroups),
                "comparison_count": sum(
                    int(g.get("comparison_count") or len(g.get("pairings") or []) or 0) for g in pgroups
                ),
            }
        else:
            bundle = vr.participant_rank_bundle(
                pgroups, alternatives=alts, factors=facs, settings=cfg, floor_alpha=floor_alpha
            )
        bundle_list.append(bundle)
        n_comp = max(0, int(bundle.get("comparison_count") or 0))
        unit_w = float(weight_map.get(pid, 1.0))
        influence = vr.participant_influence_mass(n_comp or 1 if bundle.get("group_count") else 0, unit_w, mode)
        if influence <= 0 and bundle.get("group_count"):
            influence = unit_w
        mp = vr.multi_pass_consistency(pgroups)
        channel_mp = vr.multi_pass_consistency_by_channel(pgroups)
        part = next((p for p in parts if int(p.get("id") or 0) == pid), {"id": pid})
        ranking = bundle.get("option_ranking") or []
        leader = ranking[0] if ranking else None
        participant_rows.append({
            **{k: part.get(k) for k in ("id", "display_name", "email", "source", "is_complete")},
            "id": pid,
            "group_count": bundle.get("group_count"),
            "comparison_count": bundle.get("comparison_count"),
            "observation_count": bundle.get("comparison_count"),
            "data_points": bundle.get("comparison_count") or 0,
            "option_ranking": ranking,
            "option_ranking_equal": bundle.get("option_ranking_equal") or ranking,
            "ranking": ranking,
            "factor_ranking": bundle.get("factor_ranking"),
            "option_ranks_by_factor": bundle.get("option_ranks_by_factor"),
            "leader": leader,
            "stability": mp,
            "confidence": mp,
            "multi_pass": mp,
            "multi_pass_by_channel": {
                f"{gt}:{'' if cid is None else cid}": v for (gt, cid), v in channel_mp.items()
            },
            "influence_weight": influence,
            "coherence": None,
        })

    option_ranking = inferred.option_ranking
    option_ranking_equal = inferred.option_ranking_equal
    factor_ranking = inferred.factor_ranking
    factor_weights = inferred.factor_weights
    by_factor_rankings = inferred.by_factor

    metrics = vr.project_metrics(
        gs, alternatives=alts, factors=facs, exclusive_mode=exclusive_mode,
        participants=parts, settings=cfg,
    )
    dispersion = vr.compute_dispersion(bundle_list)

    channel_mp_all = vr.multi_pass_consistency_by_channel(gs)
    for e in factor_ranking:
        fid = int(e["id"])
        if e.get("mean_rank") is None:
            continue
        maps = [b.get("option_ranks_by_factor", {}).get(fid) or {} for b in bundle_list]
        maps = [m for m in maps if m]
        opt_stab = vr.top_half_alignment_from_rank_maps(
            maps, fraction=float(cfg.get("top_half_fraction") or 0.5),
        )
        if opt_stab is None:
            opt_stab = channel_mp_all.get(("alternative", fid), 0.0)
        e["stability"] = round(float(opt_stab or 0) * 100)
        e.setdefault("data_points", e.get("evidence") or 0)
        fr = by_factor_rankings.get(fid) or []
        if fr:
            e["leader"] = {
                "id": fr[0]["id"], "title": fr[0]["title"],
                "score": fr[0]["score"], "mean_rank": fr[0]["mean_rank"],
            }

    overall_ranks = {}
    for e in option_ranking:
        if e.get("mean_rank") is not None:
            overall_ranks[int(e["id"])] = float(e["mean_rank"])

    for row in participant_rows:
        pid = int(row["id"])
        b = inferred.by_pid.get(pid) or {}
        pr = b.get("overall_option_ranks") or {}
        coh = vr.coherence_to_group(pr, overall_ranks, coherence_method) if pr and overall_ranks else None
        if coh is not None:
            row["coherence_raw"] = coh
            row["coherence"] = max(0.0, min(1.0, (coh + 1.0) / 2.0))
        else:
            row["coherence"] = None

    def _pct01(v):
        if v is None:
            return None
        try:
            x = float(v)
        except (TypeError, ValueError):
            return None
        if x <= 1.0:
            return int(round(x * 100))
        return int(round(x))

    pivot_by_factor = []
    for fid, ranking in by_factor_rankings.items():
        fr_meta = next((e for e in factor_ranking if int(e["id"]) == int(fid)), None)
        leader_row = ranking[0] if ranking else None
        pivot_by_factor.append({
            "id": fid,
            "title": next(
                (_title(f, "factor") for f in facs if _item_id(f) == fid),
                "Overall" if fid == 0 else str(fid),
            ),
            "ranking": ranking,
            "normalizedWeight": (
                factor_weights.get(fid)
                if fid in factor_weights
                else (fr_meta or {}).get("normalizedWeight")
            ),
            "rank": next((i + 1 for i, e in enumerate(factor_ranking) if int(e["id"]) == int(fid)), None),
            "score": (fr_meta or {}).get("score"),
            "mean_rank": (fr_meta or {}).get("mean_rank"),
            "leader": (leader_row or {}).get("title"),
            "leader_score": (leader_row or {}).get("score"),
            "leader_mean_rank": (leader_row or {}).get("mean_rank"),
            "data_points": (fr_meta or {}).get("data_points") or (ranking[0].get("data_points") if ranking else 0),
            "stability": (fr_meta or {}).get("stability"),
            "pass_consistency": _pct01((fr_meta or {}).get("pass_consistency") or (ranking[0].get("pass_consistency") if ranking else None)),
            "confidence": (fr_meta or {}).get("confidence"),
            "discrimination": (fr_meta or {}).get("discrimination"),
            "leverage": (fr_meta or {}).get("leverage"),
            "weight_ci95": (fr_meta or {}).get("weight_ci95"),
        })

    pivot = {
        "by_participant": [
            {
                "id": row["id"],
                "title": row.get("display_name") or row.get("email") or f"Participant {row['id']}",
                "display_name": row.get("display_name"),
                "email": row.get("email"),
                "leader": (row.get("leader") or {}).get("title") if isinstance(row.get("leader"), dict) else row.get("leader"),
                "data_points": row.get("data_points") or 0,
                "comparison_count": row.get("comparison_count") or 0,
                "confidence": _pct01(row.get("confidence")),
                "stability": _pct01(row.get("stability")),
                "multi_pass": _pct01(row.get("multi_pass")),
                "coherence": row.get("coherence"),
                "group_count": row.get("group_count") or 0,
            }
            for row in participant_rows
        ],
        "by_factor": pivot_by_factor,
        "by_alternative": [
            {
                "id": e["id"],
                "title": e["title"],
                "mean_rank": e["mean_rank"],
                "rank": int(e["rank"]) + 1,
                "score": e["score"],
                "data_points": e.get("data_points") or 0,
                "leader_count": sum(
                    1
                    for b in bundle_list
                    if e["id"] in vr.tied_leader_ids_from_ranking(b.get("option_ranking"))
                ),
                "p_best": e.get("p_best"),
                "p_top_n": e.get("p_top_n"),
                "rank_ci95": e.get("rank_ci95"),
                "polarizing": e.get("polarizing"),
            }
            for e in option_ranking
            if e.get("mean_rank") is not None or True
        ],
    }

    leader = option_ranking[0] if option_ranking else None
    return {
        "exclusive_mode": exclusive_mode,
        "unique_participants": metrics["unique_participants"],
        "group_count": metrics["group_count"],
        "comparison_count": metrics["comparison_count"],
        "observation_count": metrics["comparison_count"],
        "total_observations": metrics["comparison_count"],
        "metrics": metrics,
        "stability": metrics["stability"],
        "stability_basis": metrics.get("stability_basis"),
        "confidence": metrics["confidence"],
        "agreement": metrics["agreement"],
        "completion": metrics["completion"],
        "multi_pass": metrics.get("multi_pass"),
        "factor_divergence": metrics.get("factor_divergence"),
        "option_ranking": option_ranking,
        "option_ranking_equal": option_ranking_equal,
        "alternative_ranking": option_ranking,
        "factor_ranking": factor_ranking,
        "factor_weights": factor_weights,
        "by_factor": by_factor_rankings,
        "participants": participant_rows,
        "dispersion": dispersion,
        "pivot": pivot,
        "coherence_method": coherence_method,
        "participant_influence_mode": mode,
        "participant_influence_min_comparisons": vr.clamp_influence_min_comparisons(
            cfg.get("participant_influence_min_comparisons")
        ),
        "factor_weight_floor_alpha": floor_alpha,
        "private_participation": False,
        "results": {
            "importance_adjusted": option_ranking,
            "equal_weight": option_ranking_equal,
            "leader": leader,
            "criterion_weights": factor_ranking,
        },
        "coherence": inferred.coherence,
        "posterior_stability": inferred.posterior_stability,
        "diagnostics": inferred.diagnostics,
        "ranking_mode": inferred.ranking_mode,
        "top_n": inferred.top_n,
        "engine": "hierarchical_bt_laplace",
    }
