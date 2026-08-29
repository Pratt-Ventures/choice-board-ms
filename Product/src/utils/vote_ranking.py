"""Ranked-group Results: mean ranks, top-half stability, inter-group/participant confidence.

See algos.md at repo root for the full specification.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .sort_compare import (
    clamp_max_recommended_passes,
    clamp_min_expected_passes,
    effective_group_rank_order,
)

DEFAULT_SETTINGS: dict[str, Any] = {
    "participant_influence_mode": "comparisons",
    "participant_influence_min_comparisons": 10,
    "factor_weight_floor_alpha": 0.5,
    "coherence_method": "spearman",
    "top_half_fraction": 0.5,
}

# Factor weight floor alpha: effective_floor = alpha × (n − 1). Range keeps default 0.5 centered.
FACTOR_WEIGHT_FLOOR_ALPHA_MIN = 0.1
FACTOR_WEIGHT_FLOOR_ALPHA_MAX = 0.9
FACTOR_WEIGHT_FLOOR_ALPHA_DEFAULT = 0.5

PARTICIPANT_INFLUENCE_BETA = {
    "comparisons": 1.0,
    "balanced": 0.5,
    "participants_normalized": 0.1,
}

_LN2 = math.log(2.0)


def _as_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(getattr(item, "__dict__", {}) or {})


def _groups(rows: list | None) -> list[dict]:
    out = []
    for g in (rows or []):
        d = _as_dict(g)
        status = d.get("status")
        if hasattr(status, "value"):
            status = status.value
        if str(status or "") == "in_progress":
            continue
        out.append(d)
    return out


def _group_type(g: dict) -> str:
    gt = g.get("group_type") or g.get("type") or "alternative"
    if hasattr(gt, "value"):
        gt = gt.value
    return str(gt)


def _item_id(d: dict) -> int:
    return int(d.get("id") or 0)


def _title(d: dict, kind: str = "alternative") -> str:
    if kind == "factor":
        return d.get("factor_title") or d.get("title") or f"Factor {_item_id(d)}"
    return d.get("alternative_title") or d.get("title") or f"Option {_item_id(d)}"


def normalize_participant_influence_mode(mode: str | None) -> str:
    m = (mode or "comparisons").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "participantsnormalized": "participants_normalized",
        "participant_normalized": "participants_normalized",
        "equal_participants": "participants_normalized",
        "equal_comparisons": "comparisons",
        "comparison": "comparisons",
    }
    m = aliases.get(m, m)
    if m not in PARTICIPANT_INFLUENCE_BETA:
        return "comparisons"
    return m


def participant_influence_beta(mode: str | None) -> float:
    return float(PARTICIPANT_INFLUENCE_BETA.get(normalize_participant_influence_mode(mode), 1.0))


def clamp_influence_min_comparisons(value) -> int:
    try:
        v = int(value if value is not None else 10)
    except (TypeError, ValueError):
        v = 10
    return max(3, min(500, v))


def clamp_factor_weight_floor_alpha(value) -> float:
    try:
        v = float(value if value is not None else FACTOR_WEIGHT_FLOOR_ALPHA_DEFAULT)
    except (TypeError, ValueError):
        v = FACTOR_WEIGHT_FLOOR_ALPHA_DEFAULT
    if not math.isfinite(v):
        v = FACTOR_WEIGHT_FLOOR_ALPHA_DEFAULT
    return max(FACTOR_WEIGHT_FLOOR_ALPHA_MIN, min(FACTOR_WEIGHT_FLOOR_ALPHA_MAX, v))


def ranking_settings_from_customer(client_settings_raw: str | dict | None) -> dict:
    """Legacy customer knobs stripped; only influence / coherence defaults remain."""
    cfg = dict(DEFAULT_SETTINGS)
    data = client_settings_raw
    if isinstance(data, str) and data.strip():
        import json
        try:
            data = json.loads(data)
        except Exception:
            data = {}
    if not isinstance(data, dict):
        return cfg
    if data.get("coherence_method") or data.get("coherenceMethod"):
        m = str(data.get("coherence_method") or data.get("coherenceMethod") or "spearman").lower()
        cfg["coherence_method"] = m if m in ("spearman", "kendall") else "spearman"
    return cfg


def ranking_settings_with_project_influence(base: dict | None, project: Any) -> dict:
    out = dict(DEFAULT_SETTINGS)
    if base:
        out.update(base)
    out["participant_influence_mode"] = normalize_participant_influence_mode(
        getattr(project, "participant_influence_mode", None) if project is not None
        else out.get("participant_influence_mode")
    )
    out["participant_influence_min_comparisons"] = clamp_influence_min_comparisons(
        getattr(project, "participant_influence_min_comparisons", None) if project is not None
        else out.get("participant_influence_min_comparisons")
    )
    out["factor_weight_floor_alpha"] = clamp_factor_weight_floor_alpha(
        getattr(project, "factor_weight_floor_alpha", None) if project is not None
        else out.get("factor_weight_floor_alpha")
    )
    if project is not None:
        try:
            from .vote_sort_session import project_ranking_mode
            out["ranking_mode"] = project_ranking_mode(project)
        except Exception:
            out["ranking_mode"] = getattr(project, "ranking_mode", None)
        out["min_expected_passes"] = clamp_min_expected_passes(
            getattr(project, "min_expected_passes", None)
        )
        out["max_recommended_passes"] = clamp_max_recommended_passes(
            getattr(project, "max_recommended_passes", None),
            out["min_expected_passes"],
        )
    return out


def build_participant_influence_weight_map(
    groups: list | None,
    mode: str | None,
    n_min: int | float | None = 10,
) -> dict[int, float]:
    """Per-participant unit weight w = n_eff^(β−1). Total influence = w × n_comp."""
    beta = participant_influence_beta(mode)
    floor = float(clamp_influence_min_comparisons(n_min))
    by_p: dict[int, int] = defaultdict(int)
    for g in _groups(groups):
        pid = int(g.get("participant_id") or 0)
        n = int(g.get("comparison_count") or len(g.get("pairings") or []) or 0)
        by_p[pid] += max(0, n)
    if not by_p:
        return {}
    weights: dict[int, float] = {}
    for pid, n in by_p.items():
        n_eff = max(float(n), floor)
        weights[pid] = float(n_eff ** (beta - 1.0))
    return weights


def participant_influence_mass(
    n_comp: int,
    unit_weight: float,
    mode: str | None,
) -> float:
    """Total influence mass for a participant (fixes double-β bug)."""
    n = max(0, int(n_comp))
    w = float(unit_weight)
    if n <= 0:
        return 0.0
    # w = n_eff^(β−1); mass = w * n ≈ n^β when n ≥ floor
    _ = mode  # mode already baked into unit_weight
    return w * float(n)


def rank_order_to_map(rank_order: list[int]) -> dict[int, float]:
    """Position i → rank i (0 = best)."""
    return {int(x): float(i) for i, x in enumerate(rank_order or [])}


def mean_rank_maps(maps: list[dict[int, float]]) -> dict[int, float]:
    if not maps:
        return {}
    keys: set[int] = set()
    for m in maps:
        keys.update(m.keys())
    out: dict[int, float] = {}
    for k in keys:
        vals = [m[k] for m in maps if k in m]
        if vals:
            out[k] = sum(vals) / len(vals)
    return out


def preference_from_mean_rank(mean_rank: float, n: int) -> float:
    """Borda-style preference: best rank 0 → n−1, worst → 0."""
    if n <= 1:
        return 1.0
    return max(0.0, float(n - 1) - float(mean_rank))


def score_from_mean_rank(mean_rank: float, n: int) -> float:
    """Normalized preference in [0, 1]: 1 = unanimous best, 0 = unanimous worst."""
    if n <= 1:
        return 1.0
    return preference_from_mean_rank(mean_rank, n) / float(n - 1)


def ranks_to_sorted_entries(
    ranks: dict[int, float],
    *,
    items: list[dict],
    kind: str = "alternative",
    weights: dict[int, float] | None = None,
) -> list[dict]:
    by_id = {_item_id(i): i for i in items}
    # Display order: best mean_rank first; stable id only for remaining ties
    ordered = sorted(ranks.keys(), key=lambda i: (ranks[i], i))
    n = len(ordered)
    out = []
    # Competition ranks: tied mean_ranks share the same rank index
    rank_pos = 0
    prev_mr: float | None = None
    for pos, iid in enumerate(ordered):
        d = by_id.get(iid) or {"id": iid}
        mr = float(ranks[iid])
        if prev_mr is None or abs(mr - prev_mr) > 1e-12:
            rank_pos = pos
            prev_mr = mr
        sc = score_from_mean_rank(mr, n)
        entry = {
            "id": iid,
            "title": _title(d, kind),
            "description": d.get("alternative_description") or d.get("factor_description") or d.get("description"),
            "mean_rank": mr,
            "rank": rank_pos,
            "score": sc,
            "preference": preference_from_mean_rank(mr, n),
            "evidence": 0,
            "data_points": 0,
        }
        if weights is not None and iid in weights:
            entry["normalizedWeight"] = float(weights[iid])
            entry["weight"] = float(weights[iid])
        out.append(entry)
    # Options without rank data in this slice trail unranked (no data), so lists stay
    # complete — e.g. a factor whose sort groups never covered every option.
    if ordered:
        for iid in by_id:
            if iid in ranks:
                continue
            d = by_id[iid]
            out.append({
                "id": iid,
                "title": _title(d, kind),
                "description": d.get("alternative_description") or d.get("factor_description") or d.get("description"),
                "mean_rank": None,
                "rank": len(out),  # display position; not a competition rank
                "score": 0.0,
                "preference": 0.0,
                "evidence": 0,
                "data_points": 0,
            })
    return out


def tied_leader_ids_from_ranking(ranking: list | None) -> list[int]:
    """Option ids tied for best mean_rank (else best score) in a ranking list."""
    rows = [r for r in (ranking or []) if isinstance(r, dict) and r.get("id") is not None]
    if not rows:
        return []
    with_mean = [r for r in rows if r.get("mean_rank") is not None]
    if with_mean:
        best = min(float(r["mean_rank"]) for r in with_mean)
        return [
            int(r["id"])
            for r in with_mean
            if abs(float(r["mean_rank"]) - best) < 1e-9
        ]
    with_score = [r for r in rows if r.get("score") is not None]
    if with_score:
        best = max(float(r["score"]) for r in with_score)
        return [
            int(r["id"])
            for r in with_score
            if abs(float(r["score"]) - best) < 1e-9
        ]
    return [int(rows[0]["id"])]


def factor_weights_from_ranks(
    factor_ranks: dict[int, float],
    floor_alpha: float | None = None,
) -> dict[int, float]:
    """Normalize factor importance weights from mean ranks.

    raw_i = preference(rank_i, n) + alpha × (n − 1)
    weight_i = raw_i / Σ raw

    alpha default 0.5 → two clear ranks yield 75% / 25%. Lower alpha spreads more;
    higher alpha compresses toward equal.
    """
    if not factor_ranks:
        return {}
    n = len(factor_ranks)
    alpha = clamp_factor_weight_floor_alpha(floor_alpha)
    floor = alpha * float(max(0, n - 1))
    raw = {k: preference_from_mean_rank(float(v), n) + floor for k, v in factor_ranks.items()}
    s = sum(raw.values()) or 1.0
    return {k: v / s for k, v in raw.items()}


def weighted_option_ranks(
    option_ranks_by_factor: dict[int | None, dict[int, float]],
    factor_weights: dict[int, float],
) -> dict[int, float]:
    if not option_ranks_by_factor:
        return {}
    if len(option_ranks_by_factor) == 1 and (None in option_ranks_by_factor or 0 in option_ranks_by_factor):
        return dict(next(iter(option_ranks_by_factor.values())))
    use_weights = dict(factor_weights or {})
    if not use_weights:
        keys = [k for k in option_ranks_by_factor.keys() if k is not None and int(k) != 0]
        if keys:
            eq = 1.0 / len(keys)
            use_weights = {int(k): eq for k in keys}
    acc: dict[int, float] = defaultdict(float)
    wsum: dict[int, float] = defaultdict(float)
    for fid, ranks in option_ranks_by_factor.items():
        if fid is None or int(fid) == 0:
            w = 1.0
        else:
            w = float(use_weights.get(int(fid), 0.0))
            if w <= 0 and use_weights:
                continue
            if w <= 0:
                w = 1.0
        for oid, r in ranks.items():
            acc[oid] += w * r
            wsum[oid] += w
    return {oid: acc[oid] / wsum[oid] for oid in acc if wsum[oid] > 0}


def equal_weight_option_ranks(
    option_ranks_by_factor: dict[int | None, dict[int, float]],
) -> dict[int, float]:
    """Mean option ranks with equal factor weights (ignore factor importance)."""
    keys = [k for k in option_ranks_by_factor.keys() if k is not None and int(k) != 0]
    if not keys:
        if None in option_ranks_by_factor:
            return dict(option_ranks_by_factor[None])
        if 0 in option_ranks_by_factor:
            return dict(option_ranks_by_factor[0])
        return {}
    eq = {int(k): 1.0 / len(keys) for k in keys}
    return weighted_option_ranks(option_ranks_by_factor, eq)


def groups_for_participant(groups: list | None, participant_id: int) -> list[dict]:
    return [g for g in _groups(groups) if int(g.get("participant_id") or 0) == int(participant_id)]


def participant_rank_bundle(
    groups: list | None,
    *,
    alternatives: list | None,
    factors: list | None,
    settings: dict | None = None,
    floor_alpha: float | None = None,
) -> dict:
    """Per-participant mean ranks from their completed sort groups."""
    gs = _groups(groups)
    alts = [_as_dict(a) for a in (alternatives or []) if not _as_dict(a).get("disabled")]
    facs = [_as_dict(f) for f in (factors or []) if not _as_dict(f).get("disabled")]
    cfg = dict(DEFAULT_SETTINGS)
    if settings:
        cfg.update(settings)
    alpha = clamp_factor_weight_floor_alpha(
        floor_alpha if floor_alpha is not None else cfg.get("factor_weight_floor_alpha")
    )
    opt_by_factor: dict[int | None, list[dict[int, float]]] = defaultdict(list)
    factor_maps: list[dict[int, float]] = []
    group_data_points = 0
    for g in gs:
        # Recompute from pairings when present (repairs pre-fix FJ rank_order bug)
        order = effective_group_rank_order(g)
        if not order:
            continue
        rm = rank_order_to_map(order)
        n_comp = int(g.get("comparison_count") or len(g.get("pairings") or []) or max(0, len(order) - 1))
        group_data_points += max(1, n_comp)
        if _group_type(g) == "criteria":
            factor_maps.append(rm)
        else:
            cid = g.get("criterion_id")
            key = None if cid is None else int(cid)
            opt_by_factor[key].append(rm)

    option_mean_by_factor = {k: mean_rank_maps(v) for k, v in opt_by_factor.items()}
    # annotate data points per factor bucket
    factor_group_counts = {k: len(v) for k, v in opt_by_factor.items()}
    factor_mean = mean_rank_maps(factor_maps)
    weights = factor_weights_from_ranks(factor_mean, floor_alpha=alpha) if factor_mean else {}
    overall = weighted_option_ranks(option_mean_by_factor, weights)
    overall_equal = equal_weight_option_ranks(option_mean_by_factor)

    option_ranking = ranks_to_sorted_entries(overall, items=alts, kind="alternative")
    for e in option_ranking:
        if e.get("mean_rank") is None:
            continue
        e["data_points"] = group_data_points
        e["evidence"] = group_data_points
    factor_ranking = ranks_to_sorted_entries(factor_mean, items=facs, kind="factor", weights=weights)
    for e in factor_ranking:
        e["data_points"] = len(factor_maps)
        e["evidence"] = len(factor_maps)

    return {
        "option_ranks_by_factor": option_mean_by_factor,
        "factor_group_counts": factor_group_counts,
        "factor_ranks": factor_mean,
        "factor_weights": weights,
        "overall_option_ranks": overall,
        "overall_option_ranks_equal": overall_equal,
        "option_ranking": option_ranking,
        "option_ranking_equal": ranks_to_sorted_entries(overall_equal, items=alts, kind="alternative"),
        "factor_ranking": factor_ranking,
        "group_count": len(gs),
        "comparison_count": sum(
            int(g.get("comparison_count") or len(g.get("pairings") or []) or 0) for g in gs
        ),
        "passes": max((int(g.get("pass_index") or 1) for g in gs), default=0),
        "data_points": group_data_points,
    }


def _normalize_dist(ranks: dict[int, float]) -> dict[int, float]:
    """Convert mean ranks → preference probability mass (higher = better)."""
    if not ranks:
        return {}
    n = len(ranks)
    raw = {k: max(1e-12, preference_from_mean_rank(float(v), n) + 1e-12) for k, v in ranks.items()}
    s = sum(raw.values()) or 1.0
    return {k: v / s for k, v in raw.items()}


def top_half_dist(ranks: dict[int, float], fraction: float = 0.5) -> dict[int, float]:
    """Keep top ceil(fraction·n) items by preference; renormalize. Empty → {}."""
    if not ranks:
        return {}
    n = len(ranks)
    k = max(1, int(math.ceil(n * max(0.05, min(1.0, fraction)))))
    ordered = sorted(ranks.keys(), key=lambda i: (ranks[i], i))
    top_ids = set(ordered[:k])
    pref = _normalize_dist(ranks)
    clipped = {i: pref[i] for i in top_ids if i in pref}
    s = sum(clipped.values()) or 1.0
    return {i: v / s for i, v in clipped.items()}


def kl_divergence(p: dict[int, float], q: dict[int, float]) -> float:
    keys = set(p) | set(q)
    if not keys:
        return 0.0
    eps = 1e-12
    ps = {k: p.get(k, 0.0) + eps for k in keys}
    qs = {k: q.get(k, 0.0) + eps for k in keys}
    sp = sum(ps.values())
    sq = sum(qs.values())
    ps = {k: v / sp for k, v in ps.items()}
    qs = {k: v / sq for k, v in qs.items()}
    return float(sum(ps[k] * math.log(ps[k] / qs[k]) for k in keys))


def js_divergence(p: dict[int, float], q: dict[int, float]) -> float:
    keys = set(p) | set(q)
    if not keys:
        return 0.0
    m = {k: 0.5 * (p.get(k, 0.0) + q.get(k, 0.0)) for k in keys}
    return 0.5 * kl_divergence(p, m) + 0.5 * kl_divergence(q, m)


def _js_agreement(dists: list[dict[int, float]]) -> float:
    """1 − mean pairwise JS / ln2, clamped to [0, 1]."""
    if len(dists) < 2:
        return 1.0 if len(dists) == 1 else 0.0
    divs: list[float] = []
    for i in range(len(dists)):
        for j in range(i + 1, len(dists)):
            divs.append(js_divergence(dists[i], dists[j]))
    mean_js = sum(divs) / len(divs) if divs else 0.0
    return float(max(0.0, min(1.0, 1.0 - mean_js / _LN2)))


def multi_pass_consistency(groups: list | None) -> float:
    """
    Same-channel multi-pass agreement only (0–1).
    Channel = (group_type, criterion_id). Never compares different factors to each other.
    """
    gs = _groups(groups)
    by_key: dict[tuple, list[dict[int, float]]] = defaultdict(list)
    for g in gs:
        gt = _group_type(g)
        cid = g.get("criterion_id")
        key = (gt, None if cid is None else int(cid))
        order = effective_group_rank_order(g)
        if order:
            by_key[key].append(_normalize_dist(rank_order_to_map(order)))
    divergences: list[float] = []
    for maps in by_key.values():
        if len(maps) < 2:
            continue
        for i in range(len(maps)):
            for j in range(i + 1, len(maps)):
                divergences.append(js_divergence(maps[i], maps[j]))
    if not divergences:
        return 0.0
    mean_js = sum(divergences) / len(divergences)
    return float(max(0.0, min(1.0, 1.0 - mean_js / _LN2)))


# Back-compat alias
def within_participant_stability(groups: list | None) -> float:
    return multi_pass_consistency(groups)


def multi_pass_consistency_by_channel(groups: list | None) -> dict[tuple, float]:
    """Per-channel multi-pass agreement. Keys: ('criteria', None) or ('alternative', factor_id|None)."""
    gs = _groups(groups)
    by_key: dict[tuple, list[dict[int, float]]] = defaultdict(list)
    for g in gs:
        gt = _group_type(g)
        cid = g.get("criterion_id")
        key = (gt, None if cid is None else int(cid))
        order = effective_group_rank_order(g)
        if order:
            by_key[key].append(_normalize_dist(rank_order_to_map(order)))
    out: dict[tuple, float] = {}
    for key, maps in by_key.items():
        if len(maps) < 2:
            continue
        out[key] = _js_agreement(maps)
    return out


def top_half_alignment_from_rank_maps(
    rank_maps: list[dict[int, float]],
    *,
    fraction: float = 0.5,
) -> float | None:
    """Top-half JS agreement across rank maps. None if fewer than 2 maps."""
    dists = [top_half_dist(r, fraction=fraction) for r in rank_maps if r]
    if len(dists) < 2:
        return None
    return _js_agreement(dists)


def cross_participant_channel_stability(
    participant_bundles: list[dict],
    *,
    fraction: float = 0.5,
) -> tuple[float, str, dict]:
    """
    Stability = agreement across participants within the same channel only:
      - factor-importance rankings (criteria)
      - option rankings under each factor (and overall-null bucket)
    Does NOT compare one factor's option list to another's.

    Returns (stability, basis, detail) where basis is
    cross_participant | multi_pass | none.
    """
    channel_scores: list[float] = []
    detail: dict[str, Any] = {"channels": {}}

    # Factor importance channel
    factor_maps = [b.get("factor_ranks") or {} for b in participant_bundles]
    factor_maps = [m for m in factor_maps if m]
    fa = top_half_alignment_from_rank_maps(factor_maps, fraction=fraction)
    if fa is not None:
        channel_scores.append(fa)
        detail["channels"]["factors"] = fa

    # Collect option-by-factor keys present
    factor_ids: set[int | None] = set()
    for b in participant_bundles:
        for k in (b.get("option_ranks_by_factor") or {}):
            factor_ids.add(k if k is None else int(k))

    for fid in sorted(factor_ids, key=lambda x: (x is None, x or 0)):
        maps = []
        for b in participant_bundles:
            rm = (b.get("option_ranks_by_factor") or {}).get(fid)
            if rm:
                maps.append(rm)
        aa = top_half_alignment_from_rank_maps(maps, fraction=fraction)
        if aa is not None:
            channel_scores.append(aa)
            label = "overall" if fid is None or int(fid) == 0 else f"factor:{int(fid)}"
            detail["channels"][label] = aa

    if channel_scores:
        stab = float(sum(channel_scores) / len(channel_scores))
        return stab, "cross_participant", detail

    # Single participant (or no peer overlap): multi-pass same-channel only
    # Caller may also pass multi_pass separately; here return 0 with basis none
    # if we cannot form any cross-participant channel.
    return 0.0, "none", detail


def factor_option_divergence(
    option_ranks_by_factor: dict[int | None, dict[int, float]],
) -> float:
    """
    How differently factors rank options (0 = collinear/identical, 1 = max opposition).

    Uses mean pairwise Spearman: divergence = (1 − ρ) / 2.
    JS on soft preference mass understates pure order disagreement; rank correlation
    better surfaces landscape split when leaders differ across factors.
    """
    keys = [k for k in option_ranks_by_factor.keys() if option_ranks_by_factor.get(k)]
    fac_keys = [k for k in keys if k is not None and int(k) != 0]
    use_keys = fac_keys if len(fac_keys) >= 2 else list(keys)
    if len(use_keys) < 2:
        return 0.0
    divs: list[float] = []
    for i in range(len(use_keys)):
        for j in range(i + 1, len(use_keys)):
            rho = spearman_rho(option_ranks_by_factor[use_keys[i]], option_ranks_by_factor[use_keys[j]])
            if rho is None:
                continue
            divs.append((1.0 - float(rho)) / 2.0)
    if not divs:
        return 0.0
    return float(max(0.0, min(1.0, sum(divs) / len(divs))))


def top_half_alignment(
    participant_bundles: list[dict],
    *,
    fraction: float = 0.5,
    rank_key: str = "overall_option_ranks",
) -> float:
    """Top-half alignment of a single rank_key across participants."""
    dists = []
    for b in participant_bundles:
        ranks = b.get(rank_key) or {}
        if ranks:
            dists.append(top_half_dist(ranks, fraction=fraction))
    return _js_agreement(dists)


def cross_participant_agreement(
    participant_bundles: list[dict],
    *,
    rank_key: str = "overall_option_ranks",
) -> float:
    """Full-rank cross-participant agreement via JS on preference distributions."""
    dists = []
    for b in participant_bundles:
        ranks = b.get(rank_key) or {}
        if ranks:
            dists.append(_normalize_dist(ranks))
    return _js_agreement(dists)


def spearman_rho(ranks_a: dict[int, float], ranks_b: dict[int, float]) -> float | None:
    keys = sorted(set(ranks_a) & set(ranks_b))
    n = len(keys)
    if n < 2:
        return None
    # average ranks for ties not needed (mean ranks may be fractional)
    xs = [float(ranks_a[k]) for k in keys]
    ys = [float(ranks_b[k]) for k in keys]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx < 1e-12 or dy < 1e-12:
        return 1.0 if dx < 1e-12 and dy < 1e-12 else None
    return float(max(-1.0, min(1.0, num / (dx * dy))))


def kendall_tau(ranks_a: dict[int, float], ranks_b: dict[int, float]) -> float | None:
    keys = sorted(set(ranks_a) & set(ranks_b))
    n = len(keys)
    if n < 2:
        return None
    conc = disc = 0
    for i in range(n):
        for j in range(i + 1, n):
            da = ranks_a[keys[i]] - ranks_a[keys[j]]
            db = ranks_b[keys[i]] - ranks_b[keys[j]]
            prod = da * db
            if prod > 0:
                conc += 1
            elif prod < 0:
                disc += 1
    denom = conc + disc
    if denom == 0:
        return 1.0
    return float((conc - disc) / denom)


def coherence_to_group(
    participant_ranks: dict[int, float],
    group_ranks: dict[int, float],
    method: str = "spearman",
) -> float | None:
    m = (method or "spearman").lower()
    if m == "kendall":
        return kendall_tau(participant_ranks, group_ranks)
    return spearman_rho(participant_ranks, group_ranks)


def compute_dispersion(participant_bundles: list[dict]) -> dict:
    """Rank dispersion / clustering from per-participant overall rankings."""
    leaders: list[int] = []
    rank_lists: dict[int, list[float]] = defaultdict(list)
    for b in participant_bundles:
        ranking = b.get("option_ranking") or []
        if ranking:
            leaders.append(int(ranking[0]["id"]))
        ranks = b.get("overall_option_ranks") or {}
        for oid, r in ranks.items():
            rank_lists[int(oid)].append(float(r))
    unique_leaders = len(set(leaders)) if leaders else 0
    n_parts = max(1, len([b for b in participant_bundles if b.get("overall_option_ranks")]))
    # clustering: share of participants on the modal leader
    clustering = 0.0
    if leaders:
        from collections import Counter
        top_count = Counter(leaders).most_common(1)[0][1]
        clustering = top_count / len(leaders)
    # dispersion index: mean normalized rank stdev across options
    stds = []
    for oid, vals in rank_lists.items():
        if len(vals) < 2:
            continue
        mu = sum(vals) / len(vals)
        var = sum((v - mu) ** 2 for v in vals) / len(vals)
        n_items = max(1, len(rank_lists) - 1)
        stds.append(math.sqrt(var) / n_items)
    dispersion_index = float(sum(stds) / len(stds)) if stds else 0.0
    mean_rank_by_alternative = {
        str(oid): (sum(vals) / len(vals)) for oid, vals in rank_lists.items() if vals
    }
    return {
        "dispersion_index": max(0.0, min(1.0, dispersion_index)),
        "clustering_index": max(0.0, min(1.0, clustering)),
        "unique_leaders": unique_leaders,
        "participant_count": n_parts,
        "mean_rank_by_alternative": mean_rank_by_alternative,
    }


def project_metrics(
    groups: list | None,
    *,
    alternatives: list | None = None,
    factors: list | None = None,
    exclusive_mode: bool = False,
    participants: list | None = None,
    settings: dict | None = None,
    **_kwargs,
) -> dict:
    """
    Metrics (all 0–1 fractions unless noted):
      stability         — same-channel top-half alignment across participants
      multi_pass        — same-channel multi-pass consistency (never cross-factor)
      factor_divergence — how differently factors rank options (landscape split)
      confidence        — multi_pass + inter-participant + depth
      agreement         — full overall-rank cross-participant agreement
      completion        — mean passes / min_expected_passes
    """
    gs = _groups(groups)
    parts = [_as_dict(p) for p in (participants or [])]
    cfg = dict(DEFAULT_SETTINGS)
    if settings:
        cfg.update(settings)
    frac = float(cfg.get("top_half_fraction") or 0.5)

    pids = sorted({int(g.get("participant_id") or 0) for g in gs if g.get("participant_id")})
    bundles = []
    multi_passes = []
    for pid in pids:
        pgroups = groups_for_participant(gs, pid)
        b = participant_rank_bundle(
            pgroups, alternatives=alternatives, factors=factors, settings=cfg
        )
        bundles.append(b)
        mp = multi_pass_consistency(pgroups)
        multi_passes.append(mp)
        b["multi_pass"] = mp

    stability, stab_basis, stab_detail = cross_participant_channel_stability(bundles, fraction=frac)
    # Single-participant projects: report multi-pass as stability with explicit basis
    multi_pass = sum(multi_passes) / len(multi_passes) if multi_passes else 0.0
    if stab_basis == "none" and multi_pass > 0:
        stability = multi_pass
        stab_basis = "multi_pass"

    agreement = cross_participant_agreement(bundles)
    # With one participant, agreement is trivially 1 — down-weight in confidence via n_parts
    n_parts = len(pids) if pids else 0
    if n_parts < 2:
        agreement_for_conf = multi_pass  # no peer signal; lean on repeatability
    else:
        agreement_for_conf = agreement

    # Factor divergence from pooled mean ranks per factor (group landscape)
    pooled_by_factor: dict[int | None, list[dict[int, float]]] = defaultdict(list)
    for b in bundles:
        for fid, rm in (b.get("option_ranks_by_factor") or {}).items():
            if rm:
                pooled_by_factor[fid].append(rm)
    merged_by_factor = {k: mean_rank_maps(v) for k, v in pooled_by_factor.items()}
    f_div = factor_option_divergence(merged_by_factor)

    min_p = clamp_min_expected_passes(cfg.get("min_expected_passes"))
    pass_fracs = []
    for b in bundles:
        passes = int(b.get("passes") or 0)
        pass_fracs.append(min(1.0, passes / float(min_p)))
    if not pass_fracs and parts:
        pass_fracs = [0.0]
    completion = sum(pass_fracs) / len(pass_fracs) if pass_fracs else 0.0

    n_facs = len([f for f in (factors or []) if not _as_dict(f).get("disabled")])
    expected_per = max(1, (n_facs if n_facs else 1) + (1 if n_facs > 1 else 0))
    expected_total = expected_per * max(1, n_parts or 1) * max(1, min_p)
    depth = min(1.0, len(gs) / float(expected_total)) if expected_total else 0.0

    # Confidence: multi-pass + peer agreement + depth (no cross-factor penalty/reward)
    if exclusive_mode:
        confidence = 0.30 * multi_pass + 0.50 * agreement_for_conf + 0.20 * depth
    else:
        confidence = 0.35 * multi_pass + 0.45 * agreement_for_conf + 0.20 * depth

    n_groups = len(gs)
    n_comps = sum(int(g.get("comparison_count") or 0) for g in gs)
    return {
        "stability": float(max(0.0, min(1.0, stability))),
        "stability_basis": stab_basis,
        "stability_channels": stab_detail.get("channels") or {},
        "confidence": float(max(0.0, min(1.0, confidence))),
        "agreement": float(max(0.0, min(1.0, agreement if n_parts >= 2 else multi_pass))),
        "multi_pass": float(max(0.0, min(1.0, multi_pass))),
        "inter_group": float(max(0.0, min(1.0, multi_pass))),  # alias
        "inter_participant": float(max(0.0, min(1.0, agreement if n_parts >= 2 else 0.0))),
        "factor_divergence": float(max(0.0, min(1.0, f_div))),
        "depth": float(max(0.0, min(1.0, depth))),
        "completion": float(max(0.0, min(1.0, completion))),
        "coverage": float(max(0.0, min(1.0, completion))),
        "unique_participants": n_parts if n_parts else len(parts),
        "group_count": n_groups,
        "comparison_count": n_comps,
        "observation_count": n_comps,
    }


def build_personal_submitter_summary(
    *,
    alternatives: list | None,
    factors: list | None,
    groups: list | None = None,
    observations: list | None = None,
    exclusive_mode: bool = False,
    settings: dict | None = None,
) -> dict:
    _ = observations
    report = build_report(
        alternatives=alternatives,
        factors=factors,
        exclusive_mode=exclusive_mode,
        all_groups=groups,
        settings=settings,
    )
    ranking = report.get("option_ranking") or []
    return {
        "alternative_leaderboard": ranking,
        "factor_leaderboard": report.get("factor_ranking") or [],
        "group_count": report.get("group_count") or 0,
        "comparison_count": report.get("comparison_count") or 0,
        "exclusive_mode": exclusive_mode,
        "ranking_mode": report.get("ranking_mode"),
        "top_n": report.get("top_n"),
        "confidence": report.get("confidence"),
        "stability": report.get("stability"),
        "multi_pass": report.get("multi_pass"),
    }


def _merge_weighted(pairs: list[tuple[dict[int, float], float]]) -> dict[int, float]:
    if not pairs:
        return {}
    acc: dict[int, float] = defaultdict(float)
    wsum: dict[int, float] = defaultdict(float)
    for ranks, w in pairs:
        if w <= 0:
            continue
        for k, r in ranks.items():
            acc[k] += w * r
            wsum[k] += w
    return {k: acc[k] / wsum[k] for k in acc if wsum[k] > 0}


def build_report(
    *,
    alternatives: list | None,
    factors: list | None,
    exclusive_mode: bool = False,
    all_groups: list | None = None,
    all_observations: list | None = None,
    participants: list | None = None,
    settings: dict | None = None,
) -> dict:
    from .bt_inference.interface import build_report_v2

    return build_report_v2(
        alternatives=alternatives,
        factors=factors,
        exclusive_mode=exclusive_mode,
        all_groups=all_groups,
        all_observations=all_observations,
        participants=participants,
        settings=settings,
    )


def build_report_mean_ranks(
    *,
    alternatives: list | None,
    factors: list | None,
    exclusive_mode: bool = False,
    all_groups: list | None = None,
    all_observations: list | None = None,
    participants: list | None = None,
    settings: dict | None = None,
) -> dict:
    gs = _groups(all_groups if all_groups is not None else all_observations)
    alts = [_as_dict(a) for a in (alternatives or []) if not _as_dict(a).get("disabled")]
    facs = [_as_dict(f) for f in (factors or []) if not _as_dict(f).get("disabled")]
    parts = [_as_dict(p) for p in (participants or [])]
    cfg = dict(DEFAULT_SETTINGS)
    if settings:
        cfg.update(settings)
    coherence_method = str(cfg.get("coherence_method") or "spearman").lower()
    if coherence_method not in ("spearman", "kendall"):
        coherence_method = "spearman"

    weight_map = build_participant_influence_weight_map(
        gs,
        cfg.get("participant_influence_mode"),
        cfg.get("participant_influence_min_comparisons"),
    )
    mode = normalize_participant_influence_mode(cfg.get("participant_influence_mode"))

    pids = sorted({int(g.get("participant_id") or 0) for g in gs if g.get("participant_id")})
    if not pids and parts:
        pids = [int(p.get("id") or 0) for p in parts if p.get("id")]

    participant_rows = []
    bundles_by_pid: dict[int, dict] = {}
    weighted_overall: list[tuple[dict[int, float], float]] = []
    weighted_overall_eq: list[tuple[dict[int, float], float]] = []
    weighted_factors: list[tuple[dict[int, float], float]] = []
    by_factor_maps: dict[int | None, list[tuple[dict[int, float], float]]] = defaultdict(list)
    bundle_list: list[dict] = []

    floor_alpha = clamp_factor_weight_floor_alpha(cfg.get("factor_weight_floor_alpha"))

    for pid in pids:
        pgroups = groups_for_participant(gs, pid)
        bundle = participant_rank_bundle(
            pgroups, alternatives=alts, factors=facs, settings=cfg, floor_alpha=floor_alpha
        )
        bundles_by_pid[pid] = bundle
        bundle_list.append(bundle)
        n_comp = max(0, int(bundle.get("comparison_count") or 0))
        unit_w = float(weight_map.get(pid, 1.0))
        influence = participant_influence_mass(n_comp or 1 if bundle.get("group_count") else 0, unit_w, mode)
        if influence <= 0 and bundle.get("group_count"):
            influence = unit_w  # at least unit mass if groups exist without comparison_count

        overall = bundle.get("overall_option_ranks") or {}
        if overall:
            weighted_overall.append((overall, influence))
        overall_eq = bundle.get("overall_option_ranks_equal") or overall
        if overall_eq:
            weighted_overall_eq.append((overall_eq, influence))
        fr = bundle.get("factor_ranks") or {}
        if fr:
            weighted_factors.append((fr, influence))
        for fid, rm in (bundle.get("option_ranks_by_factor") or {}).items():
            by_factor_maps[fid].append((rm, influence))

        mp = multi_pass_consistency(pgroups)
        channel_mp = multi_pass_consistency_by_channel(pgroups)
        part = next((p for p in parts if int(p.get("id") or 0) == pid), {"id": pid})
        ranking = bundle.get("option_ranking") or []
        leader = ranking[0] if ranking else None
        participant_rows.append({
            **{k: part.get(k) for k in ("id", "display_name", "email", "source", "is_complete")},
            "id": pid,
            "group_count": bundle.get("group_count"),
            "comparison_count": bundle.get("comparison_count"),
            "observation_count": bundle.get("comparison_count"),
            "data_points": bundle.get("data_points") or bundle.get("comparison_count") or 0,
            "option_ranking": ranking,
            "option_ranking_equal": bundle.get("option_ranking_equal") or ranking,
            "ranking": ranking,  # UI alias
            "factor_ranking": bundle.get("factor_ranking"),
            "option_ranks_by_factor": bundle.get("option_ranks_by_factor"),
            "leader": leader,
            "stability": mp,  # individual: multi-pass same-channel only
            "confidence": mp,
            "multi_pass": mp,
            "multi_pass_by_channel": {
                f"{gt}:{'' if cid is None else cid}": v for (gt, cid), v in channel_mp.items()
            },
            "influence_weight": influence,
            "coherence": None,  # filled after group ranks known
        })

    overall_ranks = _merge_weighted(weighted_overall)
    overall_ranks_eq = _merge_weighted(weighted_overall_eq)
    factor_ranks = _merge_weighted(weighted_factors)
    factor_weights = factor_weights_from_ranks(factor_ranks, floor_alpha=floor_alpha)
    by_factor_rankings = {
        (fid if fid is not None else 0): ranks_to_sorted_entries(
            _merge_weighted(pairs), items=alts, kind="alternative"
        )
        for fid, pairs in by_factor_maps.items()
    }

    # Per-factor multi-pass consistency (pooled across participants' same-channel passes)
    channel_mp_all = multi_pass_consistency_by_channel(gs)
    for fid, ranking in by_factor_rankings.items():
        n_g = sum(1 for g in gs if _group_type(g) != "criteria" and (
            (g.get("criterion_id") is None and int(fid) == 0)
            or (g.get("criterion_id") is not None and int(g.get("criterion_id")) == int(fid))
        ))
        ck = ("alternative", None if int(fid) == 0 else int(fid))
        pass_cons = channel_mp_all.get(ck)
        for e in ranking:
            if e.get("mean_rank") is None:
                continue
            e["data_points"] = n_g
            e["evidence"] = n_g
            if pass_cons is not None:
                e["pass_consistency"] = pass_cons

    metrics = project_metrics(
        gs,
        alternatives=alts,
        factors=facs,
        exclusive_mode=exclusive_mode,
        participants=parts,
        settings=cfg,
    )
    dispersion = compute_dispersion(bundle_list)

    option_ranking = ranks_to_sorted_entries(overall_ranks, items=alts, kind="alternative")
    option_ranking_equal = ranks_to_sorted_entries(overall_ranks_eq, items=alts, kind="alternative")
    factor_ranking = ranks_to_sorted_entries(
        factor_ranks, items=facs, kind="factor", weights=factor_weights
    )

    # Factor-importance channel: cross-participant stability (not cross-factor options)
    factor_maps_for_stab = [b.get("factor_ranks") or {} for b in bundle_list if b.get("factor_ranks")]
    factor_stab_val = top_half_alignment_from_rank_maps(
        factor_maps_for_stab,
        fraction=float(cfg.get("top_half_fraction") or 0.5),
    )
    if factor_stab_val is None:
        # multi-pass on criteria channel
        factor_stab_val = channel_mp_all.get(("criteria", None), 0.0)
    factor_agree_val = cross_participant_agreement(
        [{"overall_option_ranks": b.get("factor_ranks") or {}} for b in bundle_list if b.get("factor_ranks")],
    ) if len(factor_maps_for_stab) >= 2 else channel_mp_all.get(("criteria", None), 0.0)

    # Per-factor option-list peer stability
    for e in factor_ranking:
        fid = int(e["id"])
        if e.get("mean_rank") is None:
            continue
        maps = []
        for b in bundle_list:
            rm = (b.get("option_ranks_by_factor") or {}).get(fid)
            if rm:
                maps.append(rm)
        opt_stab = top_half_alignment_from_rank_maps(
            maps, fraction=float(cfg.get("top_half_fraction") or 0.5),
        )
        if opt_stab is None:
            opt_stab = channel_mp_all.get(("alternative", fid), 0.0)
        e["stability"] = round(float(opt_stab or 0) * 100)
        e["confidence"] = round(float(factor_agree_val or 0) * 100)
        e["importance_stability"] = round(float(factor_stab_val or 0) * 100)
        e["pass_consistency"] = channel_mp_all.get(("alternative", fid))
        e["data_points"] = sum(
            1 for g in gs
            if _group_type(g) != "criteria"
            and g.get("criterion_id") is not None
            and int(g.get("criterion_id")) == fid
        )
        e["evidence"] = e["data_points"]
        # leader under this factor
        fr = by_factor_rankings.get(fid) or []
        if fr:
            e["leader"] = {"id": fr[0]["id"], "title": fr[0]["title"], "score": fr[0]["score"], "mean_rank": fr[0]["mean_rank"]}

    n_opt_groups = sum(1 for g in gs if _group_type(g) != "criteria")
    for e in option_ranking:
        if e.get("mean_rank") is None:
            continue
        e["data_points"] = n_opt_groups
        e["evidence"] = n_opt_groups
    for e in option_ranking_equal:
        if e.get("mean_rank") is None:
            continue
        e["data_points"] = n_opt_groups
        e["evidence"] = n_opt_groups

    # coherence of each participant vs group overall
    for row in participant_rows:
        pid = int(row["id"])
        b = bundles_by_pid.get(pid) or {}
        pr = b.get("overall_option_ranks") or {}
        coh = coherence_to_group(pr, overall_ranks, coherence_method) if pr and overall_ranks else None
        # map ρ/τ from [-1,1] → [0,1] display-friendly agreement
        if coh is not None:
            row["coherence_raw"] = coh
            row["coherence"] = max(0.0, min(1.0, (coh + 1.0) / 2.0))
        else:
            row["coherence"] = None

    def _pct01(v) -> int | None:
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
                "rank": int(e["rank"]) + 1,  # 1-based for display
                "score": e["score"],
                "data_points": e.get("data_points") or 0,
                "leader_count": sum(
                    1
                    for b in bundle_list
                    if e["id"] in tied_leader_ids_from_ranking(b.get("option_ranking"))
                ),
            }
            for e in option_ranking
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
        "participant_influence_min_comparisons": clamp_influence_min_comparisons(
            cfg.get("participant_influence_min_comparisons")
        ),
        "factor_weight_floor_alpha": floor_alpha,
        "private_participation": False,
        # legacy-shaped convenience for share report UI
        "results": {
            "importance_adjusted": option_ranking,
            "equal_weight": option_ranking_equal,
            "leader": leader,
            "criterion_weights": factor_ranking,
        },
    }


def _lookup_keyed(maps: dict | None, key: Any) -> Any:
    """Tolerate int/str/None keys after JSON round-trips."""
    if not maps:
        return None
    if key in maps:
        return maps[key]
    if key is None:
        if "null" in maps:
            return maps["null"]
        if 0 in maps:
            return maps[0]
        if "0" in maps:
            return maps["0"]
        return None
    sk = str(key)
    if sk in maps:
        return maps[sk]
    try:
        ik = int(key)
    except (TypeError, ValueError):
        return None
    if ik in maps:
        return maps[ik]
    return None


def _ranking_from_mean_map(ranks: dict | None, alts: list[dict]) -> list[dict]:
    if not ranks:
        return []
    clean: dict[int, float] = {}
    for k, v in ranks.items():
        try:
            clean[int(k)] = float(v)
        except (TypeError, ValueError):
            continue
    if not clean:
        return []
    return ranks_to_sorted_entries(clean, items=alts, kind="alternative")


def _participant_leader_entry(participant: dict, factor_id: int | None, alts: list[dict]) -> dict | None:
    if factor_id is None:
        leader = participant.get("leader")
        if isinstance(leader, dict) and leader.get("id") is not None:
            return leader
        ranking = participant.get("option_ranking") or participant.get("ranking") or []
        return ranking[0] if ranking else None
    ranks = _lookup_keyed(participant.get("option_ranks_by_factor"), factor_id)
    ranking = _ranking_from_mean_map(ranks if isinstance(ranks, dict) else None, alts)
    return ranking[0] if ranking else None


def _pct_metric(value: Any) -> Any:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return value
    if f <= 1:
        return round(f * 100)
    return f


def build_pivot_detail(
    *,
    alternatives: list | None,
    factors: list | None,
    exclusive_mode: bool = False,
    all_groups: list | None = None,
    all_observations: list | None = None,
    participants: list | None = None,
    settings: dict | None = None,
    primary_axis: str = "participants",
    row_id: int | None = None,
    alternative_id: int | None = None,
    factor_id: int | None = None,
    participant_id: int | None = None,
) -> dict:
    report = build_report(
        alternatives=alternatives,
        factors=factors,
        exclusive_mode=exclusive_mode,
        all_groups=all_groups if all_groups is not None else all_observations,
        participants=participants,
        settings=settings,
    )
    axis = (primary_axis or "participants").lower()
    alts = [_as_dict(a) for a in (alternatives or []) if not _as_dict(a).get("disabled")]
    facs = [_as_dict(f) for f in (factors or []) if not _as_dict(f).get("disabled")]
    metrics = report.get("metrics") or {}
    by_factor = report.get("by_factor") or {}
    detail: dict[str, Any] = {
        "primary_axis": axis,
        "row_id": row_id,
        "alternative_id": alternative_id,
        "factor_id": factor_id,
        "participant_id": participant_id,
        "exclusive_mode": exclusive_mode,
        "participants": report.get("participants") or [],
        "option_ranking": report.get("option_ranking") or [],
        "factor_ranking": report.get("factor_ranking") or [],
        "metrics": {
            "confidence": round(float(metrics.get("confidence") or 0) * 100),
            "stability": round(float(metrics.get("stability") or 0) * 100),
        },
        "data_points": report.get("comparison_count") or 0,
        "private_participation": False,
        "filters": {
            "alternative_id": alternative_id,
            "factor_id": factor_id,
            "participant_id": participant_id,
        },
    }
    if axis in ("participants", "participant"):
        pid = int(participant_id if participant_id is not None else (row_id or 0))
        hit = next((p for p in (report.get("participants") or []) if int(p.get("id") or 0) == pid), None)
        detail["selected_title"] = (hit or {}).get("display_name") or f"Participant {pid}"
        if hit and factor_id is not None:
            ranks = _lookup_keyed(hit.get("option_ranks_by_factor"), int(factor_id))
            detail["option_ranking"] = _ranking_from_mean_map(ranks if isinstance(ranks, dict) else None, alts)
        else:
            detail["option_ranking"] = (hit or {}).get("option_ranking") or []
        detail["factor_ranking"] = (hit or {}).get("factor_ranking") or []
        detail["data_points"] = (hit or {}).get("data_points") or (hit or {}).get("comparison_count") or 0
        if hit:
            detail["metrics"] = {
                "confidence": _pct_metric(hit.get("confidence")),
                "stability": _pct_metric(hit.get("stability")),
            }
        leader = _participant_leader_entry(hit or {}, int(factor_id) if factor_id is not None else None, alts)
        row = {**(hit or {}), "leader": leader} if hit else None
        if row is not None and alternative_id is not None:
            ranking = detail["option_ranking"] or []
            idx = next((i for i, r in enumerate(ranking) if int(r.get("id") or 0) == int(alternative_id)), None)
            row["selected_alternative_rank"] = (idx + 1) if idx is not None else None
        detail["participants"] = [row] if row else []
    elif axis in ("factors", "factor", "criteria"):
        fid = int(factor_id if factor_id is not None else (row_id or 0))
        detail["selected_title"] = next(
            (_title(f, "factor") for f in facs if _item_id(f) == fid),
            "Overall" if fid == 0 else f"Factor {fid}",
        )
        detail["option_ranking"] = _lookup_keyed(by_factor, fid) or []
        parts_out = []
        for p in report.get("participants") or []:
            leader = _participant_leader_entry(p, fid, alts)
            if leader is None:
                continue
            if alternative_id is not None and int(leader.get("id") or 0) != int(alternative_id):
                continue
            if participant_id is not None and int(p.get("id") or 0) != int(participant_id):
                continue
            parts_out.append({
                **p,
                "leader": leader,
                "confidence": _pct_metric(p.get("confidence")),
                "data_points": p.get("data_points") or 0,
            })
        detail["participants"] = parts_out
    else:
        aid = int(alternative_id if alternative_id is not None else (row_id or 0))
        detail["selected_title"] = next(
            (_title(a, "alternative") for a in alts if _item_id(a) == aid),
            f"Option {aid}",
        )
        if factor_id is not None:
            detail["option_ranking"] = _lookup_keyed(by_factor, int(factor_id)) or []
        rows = []
        for fid_key, ranking in by_factor.items():
            if factor_id is not None and int(fid_key) != int(factor_id):
                continue
            hit = next((r for r in ranking if int(r.get("id") or 0) == aid), None)
            if hit:
                rows.append({
                    "factor_id": fid_key,
                    "mean_rank": hit.get("mean_rank"),
                    "rank": hit.get("rank"),
                    "score": hit.get("score"),
                    "title": next(
                        (_title(f, "factor") for f in facs if _item_id(f) == int(fid_key)),
                        str(fid_key),
                    ),
                })
        detail["factor_rows"] = rows
        parts_out = []
        for p in report.get("participants") or []:
            if participant_id is not None and int(p.get("id") or 0) != int(participant_id):
                continue
            if factor_id is not None:
                ranks = _lookup_keyed(p.get("option_ranks_by_factor"), int(factor_id))
                ranking = _ranking_from_mean_map(ranks if isinstance(ranks, dict) else None, alts)
                leader = ranking[0] if ranking else None
            else:
                ranking = p.get("option_ranking") or []
                leader = p.get("leader") if isinstance(p.get("leader"), dict) else (ranking[0] if ranking else None)
            if not ranking:
                continue
            idx = next((i for i, r in enumerate(ranking) if int(r.get("id") or 0) == aid), None)
            parts_out.append({
                **p,
                "selected_alternative_rank": (idx + 1) if idx is not None else None,
                "leader": leader,
                "confidence": _pct_metric(p.get("confidence")),
                "data_points": p.get("data_points") or 0,
            })
        detail["participants"] = parts_out
    return detail
