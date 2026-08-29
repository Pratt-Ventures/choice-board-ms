"""Issue and validate sort groups for pair-comparison ranking."""
from __future__ import annotations

import math
import random
import uuid
from datetime import datetime
from typing import Any

import secrets

from .comparison_question import normalize_comparison_question
from .sort_compare import (
    clamp_max_recommended_passes,
    clamp_min_expected_passes,
    clamp_questions_per_group,
    clamp_questions_per_group_stored,
    estimated_comparisons,
    hard_max_passes,
    max_items_for_question_budget,
    resolve_questions_per_group,
    select_sort_algorithm,
)

ALGORITHM_VERSION = "1.1-adaptive"
GROUP_TOKEN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
RANKING_MODES = ("find_best", "find_top_3", "find_top_half", "rank_all")
OVERALL_CRITERION_ID = 0
MIN_OPTIONS_AFTER_EXCLUSION = 2
BOTTOM_PCT_PER_PASS = 0.15
BOTTOM_PCT_CAP = 0.45


def _as_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(getattr(item, "__dict__", {}) or {})


def _active_items(rows: list | None) -> list[dict]:
    out = []
    for r in rows or []:
        d = _as_dict(r)
        if d.get("disabled"):
            continue
        if d.get("deleted_date"):
            continue
        out.append(d)
    return out


def _item_id(d: dict) -> int:
    return int(d.get("id") or d.get("alternative_id") or d.get("factor_id") or 0)


def _item_title(d: dict) -> str:
    return (
        d.get("alternative_title")
        or d.get("factor_title")
        or d.get("title")
        or d.get("name")
        or f"Item {_item_id(d)}"
    )


def _item_description(d: dict) -> str | None:
    return d.get("alternative_description") or d.get("factor_description") or d.get("description")


def serialize_item(d: dict) -> dict:
    from .compare_prompt import normalize_compare_prompt
    # For options, prefer concise compare_prompt as display title when set
    cp = normalize_compare_prompt(d.get("compare_prompt"))
    title = _item_title(d)
    if cp and (d.get("alternative_title") is not None or "alternative_title" in d):
        title = cp
    return {
        "id": _item_id(d),
        "title": title,
        "description": _item_description(d),
        "compare_prompt": cp,
        "alternative_title": d.get("alternative_title"),
        "alternative_description": d.get("alternative_description"),
        "factor_title": d.get("factor_title"),
        "factor_description": d.get("factor_description"),
    }


def serialize_criterion(d: dict) -> dict:
    from .compare_prompt import normalize_compare_prompt
    return {
        "id": _item_id(d),
        "title": _item_title(d),
        "description": _item_description(d),
        "comparison_question": None,
        "compare_prompt": normalize_compare_prompt(d.get("compare_prompt")),
    }


def new_group_token(length: int = 10) -> str:
    return "".join(secrets.choice(GROUP_TOKEN_ALPHABET) for _ in range(length))


def normalize_ranking_mode(mode: Any, *, exclusive_mode: bool | None = None) -> str:
    raw = mode.value if hasattr(mode, "value") else mode
    m = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "winner": "find_best",
        "pick_one": "find_best",
        "exclusive": "find_best",
        "top_3": "find_top_3",
        "top3": "find_top_3",
        "findtop3": "find_top_3",
        "top_half": "find_top_half",
        "findtophalf": "find_top_half",
        "full": "rank_all",
        "rank": "rank_all",
        "rankall": "rank_all",
    }
    m = aliases.get(m, m)
    if m in RANKING_MODES:
        return m
    if exclusive_mode:
        return "find_best"
    return "rank_all"


def exclusive_from_ranking_mode(mode: Any) -> bool:
    return normalize_ranking_mode(mode) == "find_best"


def resolve_ranking_target(
    project: Any,
    *,
    n_items: int,
    group_type: str,
) -> tuple[str, int | None]:
    if str(group_type) == "criteria":
        return "full", None
    mode = normalize_ranking_mode(
        getattr(project, "ranking_mode", None),
        exclusive_mode=bool(getattr(project, "project_exclusive_mode", False)),
    )
    n = max(0, int(n_items or 0))
    if mode == "find_best":
        return "winner", 1
    if mode == "find_top_3":
        return "top_n", min(3, max(1, n // 2)) if n else 1
    if mode == "find_top_half":
        return "top_n", max(1, n // 2) if n else 1
    return "full", None


def project_ranking_mode(project: Any) -> str:
    return normalize_ranking_mode(
        getattr(project, "ranking_mode", None),
        exclusive_mode=bool(getattr(project, "project_exclusive_mode", False)),
    )


def project_pass_settings(project: Any) -> dict:
    mn = clamp_min_expected_passes(getattr(project, "min_expected_passes", None))
    mx = clamp_max_recommended_passes(getattr(project, "max_recommended_passes", None), mn)
    return {
        "min_expected_passes": mn,
        "max_recommended_passes": mx,
        "hard_max_passes": hard_max_passes(mx, mn),
        "option_questions_per_group": clamp_questions_per_group_stored(
            getattr(project, "option_questions_per_group", None)
        ),
        "factor_questions_per_group": clamp_questions_per_group_stored(
            getattr(project, "factor_questions_per_group", None)
        ),
        "option_questions_per_group_explicit": bool(
            getattr(project, "option_questions_per_group_explicit", False)
        ),
        "factor_questions_per_group_explicit": bool(
            getattr(project, "factor_questions_per_group_explicit", False)
        ),
        "ranking_mode": project_ranking_mode(project),
    }


def resolved_question_budgets(project: Any, option_n: int, factor_n: int) -> tuple[int, int]:
    return (
        resolve_questions_per_group(
            getattr(project, "option_questions_per_group", None),
            option_n,
            bool(getattr(project, "option_questions_per_group_explicit", False)),
        ),
        resolve_questions_per_group(
            getattr(project, "factor_questions_per_group", None),
            factor_n,
            bool(getattr(project, "factor_questions_per_group_explicit", False)),
        ),
    )


def _is_complete_group(g: dict) -> bool:
    status = g.get("status")
    if hasattr(status, "value"):
        status = status.value
    if status in (None, ""):
        return True
    return str(status) == "complete"


def _complete_group_dicts(groups: list | None) -> list[dict]:
    return [g for g in _group_dicts(groups) if _is_complete_group(g)]


def _in_progress_group_dicts(groups: list | None) -> list[dict]:
    out = []
    for g in _group_dicts(groups):
        status = g.get("status")
        if hasattr(status, "value"):
            status = status.value
        if str(status or "") == "in_progress":
            out.append(g)
    return out


def partition_item_ids(item_ids: list[int], question_budget: int, rng: random.Random) -> list[list[int]]:
    """One group per channel per pass: a random subset up to the budget's item bound.

    FJ(n) is informational only — a group never splits a factor into batches;
    coverage comes from repeated passes over different random subsets.
    """
    ids = [int(i) for i in item_ids]
    if len(ids) < 2:
        return []
    budget = max(1, int(question_budget or 1))
    shuffled = list(ids)
    rng.shuffle(shuffled)
    k = max_items_for_question_budget(budget)
    return [shuffled[:k]] if len(shuffled) > k else [shuffled]


def option_batch_count(option_n: int, question_budget: int) -> int:
    return 1 if option_n >= 2 else 0


def _group_key(group_type: str, criterion_id: int | None, pass_index: int, batch_index: int = 0) -> str:
    c = criterion_id if criterion_id is not None else OVERALL_CRITERION_ID
    return f"{pass_index}:{group_type}:{c}:{int(batch_index or 0)}"


def _group_dicts(groups: list | None) -> list[dict]:
    return [_as_dict(g) for g in (groups or [])]


def max_completed_pass(groups: list | None) -> int:
    done = _complete_group_dicts(groups)
    if not done:
        return 0
    return max(int(g.get("pass_index") or 1) for g in done)


def completed_keys_for_pass(groups: list | None, pass_index: int) -> set[str]:
    keys: set[str] = set()
    for g in _complete_group_dicts(groups):
        if int(g.get("pass_index") or 1) != pass_index:
            continue
        gt = g.get("group_type")
        if hasattr(gt, "value"):
            gt = gt.value
        cid = g.get("criterion_id")
        keys.add(_group_key(str(gt), cid, pass_index, int(g.get("batch_index") or 0)))
    return keys


def _group_item_ids(g: dict) -> set[int]:
    raw = g.get("item_ids_initial") or g.get("item_ids") or g.get("rank_order") or []
    return {int(x) for x in raw}


def channel_covered_item_ids(
    groups: list | None,
    *,
    pass_index: int,
    group_type: str,
    criterion_id: int | None,
) -> set[int]:
    covered: set[int] = set()
    for g in _complete_group_dicts(groups):
        if int(g.get("pass_index") or 1) != pass_index:
            continue
        gt = g.get("group_type")
        if hasattr(gt, "value"):
            gt = gt.value
        if str(gt) != str(group_type):
            continue
        if g.get("criterion_id") != criterion_id:
            continue
        covered |= _group_item_ids(g)
    return covered


def required_slots_for_pass(
    *,
    pass_index: int,
    alternative_ids: list[int],
    factor_ids: list[int],
    option_question_budget: int | None = None,
    factor_question_budget: int | None = None,
    seed: Any = None,
    rng: random.Random | None = None,
) -> list[dict]:
    """Option groups first (shuffled by caller), then factor group if needed.

    When ``seed`` is provided the per-channel item shuffle is deterministic for
    that seed, so repeated calls produce identical batches and completed-group
    coverage checks match across issuances.
    """
    slots: list[dict] = []
    opt_budget = int(option_question_budget or clamp_questions_per_group_stored(None))
    fac_budget = int(factor_question_budget or clamp_questions_per_group_stored(None))
    channels: list[tuple[str, int | None, list[int], int]] = []
    if factor_ids:
        for fid in factor_ids:
            channels.append(("alternative", int(fid), list(alternative_ids), opt_budget))
    else:
        channels.append(("alternative", None, list(alternative_ids), opt_budget))
    if len(factor_ids) >= 2:
        channels.append(("criteria", None, list(factor_ids), fac_budget))
    for group_type, criterion_id, item_ids, budget in channels:
        channel_rng = (
            random.Random(f"{seed}:{pass_index}:{group_type}:{criterion_id}")
            if seed is not None
            else (rng or random.Random())
        )
        n = len(item_ids)
        if group_type == "criteria":
            # The factor list itself is the target; never truncate or split it.
            if n >= 2:
                slots.append({
                    "group_type": group_type,
                    "criterion_id": criterion_id,
                    "pass_index": pass_index,
                    "batch_index": 0,
                    "item_ids": list(item_ids),
                    "question_budget": clamp_questions_per_group(budget, n),
                })
            continue
        q = clamp_questions_per_group(budget, n) if n >= 2 else 0
        batches = partition_item_ids(item_ids, q or 1, channel_rng) if n >= 2 else []
        for batch_i, batch_ids in enumerate(batches):
            slots.append({
                "group_type": group_type,
                "criterion_id": criterion_id,
                "pass_index": pass_index,
                "batch_index": batch_i,
                "item_ids": list(batch_ids),
                "question_budget": clamp_questions_per_group(budget, len(batch_ids)),
            })
    return slots


def mean_ranks_from_order(rank_order: list[int]) -> dict[int, float]:
    return {int(item_id): float(i) for i, item_id in enumerate(rank_order)}


def participant_option_ranks_for_pass(
    groups: list | None,
    *,
    pass_index: int,
    option_ids: list[int],
) -> dict[int, float]:
    """Mean rank across option-sort groups in a pass (lower better)."""
    acc: dict[int, list[float]] = {int(i): [] for i in option_ids}
    for g in _group_dicts(groups):
        if int(g.get("pass_index") or 1) != pass_index:
            continue
        gt = g.get("group_type")
        if hasattr(gt, "value"):
            gt = gt.value
        if str(gt) != "alternative":
            continue
        from .sort_compare import effective_group_rank_order
        order = effective_group_rank_order(g)
        ranks = mean_ranks_from_order(order)
        for oid, r in ranks.items():
            if oid in acc:
                acc[oid].append(r)
    out: dict[int, float] = {}
    for oid, vals in acc.items():
        if vals:
            out[oid] = sum(vals) / len(vals)
        else:
            out[oid] = float(len(option_ids))  # unknown → worst
    return out


def excluded_option_ids(
    *,
    exclusive_mode: bool,
    all_option_ids: list[int],
    groups: list | None,
    before_pass: int | None = None,
) -> set[int]:
    """Options dropped for exclusive mode.

    before_pass: only exclusions earned by completed passes strictly below this
    pass may apply. Keeps a pass's own results from shrinking the remaining slots
    of the same pass (e.g. F1's pass-1 result must not drop options from F2's
    pass-1 group — every factor gets full option coverage in its first pass).
    """
    if not exclusive_mode or not all_option_ids:
        return set()
    gs = _group_dicts(groups)
    if before_pass is not None:
        gs = [g for g in gs if int(g.get("pass_index") or 1) < before_pass]
    n = len(all_option_ids)
    max_exclude = min(n - MIN_OPTIONS_AFTER_EXCLUSION, int(math.floor(n * BOTTOM_PCT_CAP)))
    if max_exclude <= 0:
        return set()

    completed_pass = max_completed_pass(gs)
    if completed_pass < 1:
        return set()

    # Cumulative exclusion: each completed pass may add bottom 15% of original n
    excluded: set[int] = set()
    per_pass = max(1, int(math.floor(n * BOTTOM_PCT_PER_PASS))) if n >= 3 else 0
    if per_pass <= 0:
        return set()

    remaining = list(all_option_ids)
    for p in range(1, completed_pass + 1):
        if len(excluded) >= max_exclude:
            break
        ranks = participant_option_ranks_for_pass(gs, pass_index=p, option_ids=remaining)
        # worst first
        ordered = sorted(remaining, key=lambda i: (-ranks.get(i, 0.0), i))
        budget = min(per_pass, max_exclude - len(excluded), max(0, len(remaining) - MIN_OPTIONS_AFTER_EXCLUSION))
        if budget <= 0:
            break
        drop = ordered[:budget]
        for d in drop:
            excluded.add(d)
        remaining = [i for i in remaining if i not in excluded]
    return excluded


def estimate_pass_comparisons(
    option_n: int,
    factor_n: int,
    option_question_budget: int | None = None,
    factor_question_budget: int | None = None,
) -> int:
    opt_stored = clamp_questions_per_group_stored(option_question_budget)
    fac_stored = clamp_questions_per_group_stored(factor_question_budget)
    total = 0
    channels = factor_n if factor_n >= 1 else 1
    if option_n >= 2:
        opt_q = clamp_questions_per_group(opt_stored, option_n)
        batches = option_batch_count(option_n, opt_q)
        total += channels * batches * opt_q
    if factor_n >= 2:
        total += clamp_questions_per_group(fac_stored, factor_n)
    return total


def build_progress(
    *,
    project: Any,
    groups: list | None,
    option_ids: list[int],
    factor_ids: list[int],
    exclusive_mode: bool,
    comparisons_done: int | None = None,
    groups_done: int | None = None,
    in_group_total: int = 0,
    in_group_done: int = 0,
    seed: Any = None,
) -> dict:
    ps = project_pass_settings(project)
    done_groups = _group_dicts(groups)
    g_done = groups_done if groups_done is not None else len(done_groups)
    c_done = comparisons_done if comparisons_done is not None else sum(
        int(g.get("comparison_count") or len(g.get("pairings") or []) or 0) for g in done_groups
    )
    completed_pass = max_completed_pass(done_groups)
    current_pass = completed_pass
    all_opts = list(option_ids)
    active_opts = list(all_opts)
    factor_n = len(factor_ids)
    opt_n = max(0, len(active_opts))
    opt_budget, fac_budget = resolved_question_budgets(project, opt_n, factor_n)

    def _remaining_slots(pass_index: int) -> list[dict]:
        slots = required_slots_for_pass(
            pass_index=pass_index,
            alternative_ids=active_opts,
            factor_ids=factor_ids,
            option_question_budget=opt_budget,
            factor_question_budget=fac_budget,
            seed=seed,
        )
        return [
            s for s in slots
            if not (set(s["item_ids"]) <= channel_covered_item_ids(
                done_groups,
                pass_index=pass_index,
                group_type=s["group_type"],
                criterion_id=s["criterion_id"],
            ))
        ]

    if completed_pass == 0:
        current_pass = 1
    else:
        remaining = _remaining_slots(completed_pass)
        current_pass = completed_pass if remaining else completed_pass + 1

    def comps_for_future_pass(p: int) -> int:
        return estimate_pass_comparisons(opt_n, factor_n, opt_budget, fac_budget)

    # remaining in current pass
    remaining_slots = _remaining_slots(current_pass)
    remaining_comps = 0
    for s in remaining_slots:
        remaining_comps += int(s.get("question_budget") or estimated_comparisons(len(s["item_ids"])))

    target_max = ps["max_recommended_passes"]
    target_min = ps["min_expected_passes"]
    hard = ps["hard_max_passes"]

    def comps_done_through_pass(end_pass: int) -> int:
        """Actual comparisons recorded in completed groups up to end_pass inclusive."""
        total = 0
        for g in done_groups:
            if int(g.get("pass_index") or 1) <= end_pass:
                total += int(g.get("comparison_count") or len(g.get("pairings") or []) or 0)
        return total

    def total_to_pass(end_pass: int) -> int:
        """Estimate total comparisons from session start through end of end_pass."""
        if end_pass < 1:
            return 0
        # Already past this target: freeze at work actually done through that pass
        # (do not inflate with optional later-pass remaining work).
        if current_pass > end_pass:
            return comps_done_through_pass(end_pass)
        # Still working toward end_pass: done so far + rest of current + future full passes
        t = c_done + remaining_comps
        for p in range(current_pass + 1, end_pass + 1):
            t += comps_for_future_pass(p)
        return t

    est_at_min = total_to_pass(target_min)
    est_at_max = total_to_pass(target_max)
    est_total = est_at_max  # primary overall bar targets recommended max

    # When still short of a target, keep estimate >= done so the bar never exceeds 100%
    # early if the participant overshot the algorithm upper bound. Once past the target
    # pass, leave the frozen total as-is so the UI can stay full on optional work.
    if current_pass <= target_min:
        est_at_min = max(est_at_min, c_done)
    if current_pass <= target_max:
        est_at_max = max(est_at_max, c_done)
        est_total = max(est_total, c_done)

    return {
        "participant_comparisons_done": c_done,
        "participant_groups_done": g_done,
        "pass_index": current_pass,
        "passes_completed": completed_pass if not remaining_slots and completed_pass == current_pass else max(0, current_pass - 1) if remaining_slots else completed_pass,
        "min_expected_passes": target_min,
        "max_recommended_passes": target_max,
        "hard_max_passes": hard,
        "estimated_comparisons_total": est_total,
        "estimated_comparisons_at_min": est_at_min,
        "estimated_comparisons_at_max": est_at_max,
        "in_group": {"done": in_group_done, "total": in_group_total},
        "ranking_evidence": ranking_evidence_from_groups(done_groups),
        "ranking_option_ids": [int(x) for x in all_opts],
        "ranking_factor_ids": [int(x) for x in factor_ids],
    }


def ranking_evidence_from_groups(groups: list | None) -> list[dict]:
    """Compact per-group pairing snapshot for this participant's compare-session confidence bar."""
    out: list[dict] = []
    for g in _group_dicts(groups):
        gt = g.get("group_type")
        if hasattr(gt, "value"):
            gt = gt.value
        rt = g.get("ranking_target")
        if hasattr(rt, "value"):
            rt = rt.value
        item_ids = [int(x) for x in (g.get("item_ids_initial") or g.get("item_ids") or []) if x is not None]
        pairings: list[dict] = []
        for p in (g.get("pairings") or []):
            if not isinstance(p, dict):
                continue
            row: dict[str, Any] = {"response": str(getattr(p.get("response"), "value", p.get("response") or "winner"))}
            for k in ("winner_id", "loser_id", "item_a_id", "item_b_id", "presented_left_id", "presented_right_id"):
                v = p.get(k)
                if v is None:
                    continue
                try:
                    row[k] = int(v)
                except (TypeError, ValueError):
                    continue
            pairings.append(row)
        token = str(g.get("group_token") or g.get("client_group_id") or "")
        out.append({
            "group_type": str(gt or "alternative"),
            "criterion_id": g.get("criterion_id"),
            "pass_index": int(g.get("pass_index") or 1),
            "item_ids": item_ids,
            "pairings": pairings,
            "question_budget": int(
                g.get("requested_pairing_count") or g.get("question_budget") or g.get("estimated_comparisons") or 0
            ),
            "ranking_target": str(rt or "full"),
            "top_n": g.get("top_n"),
            "client_group_id": token or None,
        })
    return out


def historical_pairings_for_channel(
    groups: list | None,
    *,
    group_type: str,
    criterion_id: int | None,
) -> list[dict]:
    out: list[dict] = []
    for g in _complete_group_dicts(groups):
        gt = g.get("group_type")
        if hasattr(gt, "value"):
            gt = gt.value
        if str(gt) != str(group_type):
            continue
        if g.get("criterion_id") != criterion_id:
            continue
        for p in (g.get("pairings") or []):
            if isinstance(p, dict):
                out.append(normalize_pairing(p))
    return out


def serialize_issued_group(
    *,
    project: Any,
    slot: dict,
    items: list[dict],
    criterion: dict | None,
    prior_pairings: list[dict],
    existing: dict | None = None,
) -> dict:
    item_ids = [int(it["id"]) for it in items]
    n = len(item_ids)
    target, top_n = resolve_ranking_target(project, n_items=n, group_type=slot["group_type"])
    budget = int(slot.get("question_budget") or resolve_questions_per_group(
        getattr(project, "option_questions_per_group", None)
        if slot["group_type"] != "criteria"
        else getattr(project, "factor_questions_per_group", None),
        n,
        bool(getattr(project, "option_questions_per_group_explicit", False))
        if slot["group_type"] != "criteria"
        else bool(getattr(project, "factor_questions_per_group_explicit", False)),
    ))
    token = str((existing or {}).get("group_token") or (existing or {}).get("client_group_id") or new_group_token())
    pairings = list((existing or {}).get("pairings") or [])
    return {
        "client_group_id": token,
        "group_token": token,
        "pass_index": int(slot["pass_index"]),
        "group_type": slot["group_type"],
        "criterion_id": slot["criterion_id"],
        "criterion": criterion,
        "sort_algorithm": select_sort_algorithm(n),
        "items": items,
        "item_ids": item_ids,
        "n_items": n,
        "batch_index": int(slot.get("batch_index") or 0),
        "question_budget": budget,
        "estimated_comparisons": budget,
        "ranking_target": target,
        "top_n": top_n,
        "require_coverage": int(slot["pass_index"]) == 1,
        "prior_pairings": prior_pairings,
        "pairings": pairings,
        "algorithm_version": str((existing or {}).get("algorithm_version") or ALGORITHM_VERSION),
        "status": str((existing or {}).get("status") or "in_progress"),
    }


def _slot_items_and_criterion(slot: dict, alt_by_id: dict, fac_by_id: dict, factor_ids: list[int]):
    item_ids = list(slot["item_ids"])
    if slot["group_type"] == "criteria":
        items = [serialize_item(fac_by_id[i]) for i in item_ids if i in fac_by_id]
        return items, None
    items = [serialize_item(alt_by_id[i]) for i in item_ids if i in alt_by_id]
    cid = slot["criterion_id"]
    if cid is not None and cid in fac_by_id:
        criterion = serialize_criterion(fac_by_id[cid])
    elif cid is None and not factor_ids:
        criterion = {
            "id": OVERALL_CRITERION_ID,
            "title": "Overall",
            "description": None,
            "comparison_question": None,
        }
    else:
        criterion = serialize_criterion(fac_by_id[cid]) if cid in fac_by_id else None
    return items, criterion


def pick_next_sort_group(
    *,
    project: Any,
    alternatives: list | None,
    factors: list | None,
    groups: list | None,
    exclusive_mode: bool | None = None,
    rng: random.Random | None = None,
    max_pass_index: int | None = None,
    seed: Any = None,
) -> dict:
    """
    Return {group, progress, session_complete} for the next compare group.
    group is None when no more groups (hard max or nothing left).
    """
    rng = rng or random.Random()
    excl_mode = bool(project.project_exclusive_mode if exclusive_mode is None else exclusive_mode)
    alts = _active_items(alternatives)
    facs = _active_items(factors)
    alt_by_id = {_item_id(a): a for a in alts if _item_id(a)}
    fac_by_id = {_item_id(f): f for f in facs if _item_id(f)}
    all_option_ids = list(alt_by_id.keys())
    factor_ids = list(fac_by_id.keys())
    done = _group_dicts(groups)
    ps = project_pass_settings(project)

    progress = build_progress(
        project=project,
        groups=done,
        option_ids=all_option_ids,
        factor_ids=factor_ids,
        exclusive_mode=excl_mode,
        seed=seed,
    )

    if not all_option_ids:
        return {"group": None, "progress": progress, "session_complete": True, "failure_reason": "No options to compare"}

    in_prog = _in_progress_group_dicts(done)
    if in_prog:
        g0 = in_prog[0]
        slot = {
            "group_type": (g0.get("group_type").value if hasattr(g0.get("group_type"), "value") else g0.get("group_type") or "alternative"),
            "criterion_id": g0.get("criterion_id"),
            "pass_index": int(g0.get("pass_index") or 1),
            "batch_index": int(g0.get("batch_index") or 0),
            "item_ids": list(g0.get("item_ids_initial") or g0.get("item_ids") or []),
            "question_budget": int(g0.get("requested_pairing_count") or 0),
        }
        items, criterion = _slot_items_and_criterion(slot, alt_by_id, fac_by_id, factor_ids)
        prior = historical_pairings_for_channel(
            done, group_type=slot["group_type"], criterion_id=slot["criterion_id"]
        )
        group = serialize_issued_group(
            project=project, slot=slot, items=items, criterion=criterion,
            prior_pairings=prior, existing=g0,
        )
        progress = build_progress(
            project=project,
            groups=done,
            option_ids=all_option_ids,
            factor_ids=factor_ids,
            exclusive_mode=excl_mode,
            in_group_total=group["question_budget"],
            in_group_done=len(group.get("pairings") or []),
            seed=seed,
        )
        progress["pass_index"] = slot["pass_index"]
        return {"group": group, "progress": progress, "session_complete": False}

    opt_budget, fac_budget = resolved_question_budgets(
        project, len(all_option_ids), len(factor_ids)
    )
    pass_cap = int(ps["hard_max_passes"])
    if max_pass_index is not None:
        try:
            pass_cap = max(1, min(pass_cap, int(max_pass_index)))
        except (TypeError, ValueError):
            pass_cap = int(ps["hard_max_passes"])

    for pass_index in range(1, pass_cap + 1):
        slots = required_slots_for_pass(
            pass_index=pass_index,
            alternative_ids=all_option_ids,
            factor_ids=factor_ids,
            option_question_budget=opt_budget,
            factor_question_budget=fac_budget,
            seed=seed,
        )
        opt_slots = [s for s in slots if s["group_type"] == "alternative"]
        crit_slots = [s for s in slots if s["group_type"] == "criteria"]
        rng.shuffle(opt_slots)
        # Full-size groups first; remainder tails surface at the end of the pass.
        opt_slots.sort(key=lambda s: -len(s["item_ids"]))
        ordered = opt_slots + crit_slots
        for slot in ordered:
            covered = channel_covered_item_ids(
                done,
                pass_index=pass_index,
                group_type=slot["group_type"],
                criterion_id=slot["criterion_id"],
            )
            if set(slot["item_ids"]) <= covered:
                continue
            item_ids = list(slot["item_ids"])
            if len(item_ids) < 2:
                continue
            items, criterion = _slot_items_and_criterion(slot, alt_by_id, fac_by_id, factor_ids)
            prior = historical_pairings_for_channel(
                done, group_type=slot["group_type"], criterion_id=slot["criterion_id"]
            )
            group = serialize_issued_group(
                project=project, slot=slot, items=items, criterion=criterion,
                prior_pairings=prior,
            )
            progress = build_progress(
                project=project,
                groups=done,
                option_ids=all_option_ids,
                factor_ids=factor_ids,
                exclusive_mode=excl_mode,
                in_group_total=group["question_budget"],
                in_group_done=0,
                seed=seed,
            )
            progress["pass_index"] = pass_index
            return {"group": group, "progress": progress, "session_complete": False}

        if pass_index >= pass_cap:
            break

    progress = build_progress(
        project=project,
        groups=done,
        option_ids=all_option_ids,
        factor_ids=factor_ids,
        exclusive_mode=excl_mode,
        seed=seed,
    )
    return {"group": None, "progress": progress, "session_complete": True}


def package_group_id(package: dict | None) -> str:
    if not package:
        return ""
    return str(package.get("group_token") or package.get("client_group_id") or "").strip()


def validate_group_package(
    issued_group: dict | None,
    package: dict,
    *,
    require_rank_order: bool = True,
) -> str | None:
    """Return failure reason or None if ok."""
    if not package:
        return "Group package required"
    client_id = package_group_id(package)
    if not client_id:
        return "group_token is required"
    issued_token = package_group_id(issued_group) if issued_group else ""
    if issued_group and issued_token and issued_token != client_id:
        issued_ids = [int(x) for x in (issued_group.get("item_ids") or issued_group.get("item_ids_initial") or [])]
        initial = [int(x) for x in (package.get("item_ids_initial") or package.get("item_ids") or [])]
        if sorted(issued_ids) != sorted(initial):
            return "Group does not match the issued compare group"
    initial = [int(x) for x in (package.get("item_ids_initial") or package.get("item_ids") or [])]
    order = [int(x) for x in (package.get("rank_order") or [])]
    if require_rank_order:
        if not order:
            return "rank_order is required"
        if sorted(order) != sorted(initial):
            return "rank_order must be a permutation of the group's items"
    allowed = set(order or initial)
    pairings = package.get("pairings") or []
    if not isinstance(pairings, list):
        return "pairings must be a list"
    for p in pairings:
        if not isinstance(p, dict):
            return "invalid pairing entry"
        w = p.get("winner_id")
        l = p.get("loser_id")
        a = p.get("item_a_id")
        b = p.get("item_b_id")
        ids = [x for x in (w, l, a, b) if x is not None]
        if w is None or l is None:
            if a is None or b is None:
                return "each pairing needs a pair of item ids"
        if allowed:
            for x in ids:
                if int(x) not in allowed:
                    return "pairing ids must be in the group"
    return None


def normalize_pairing(p: dict) -> dict:
    resp = p.get("response") or "winner"
    if hasattr(resp, "value"):
        resp = resp.value
    return {
        "winner_id": int(p["winner_id"]),
        "loser_id": int(p["loser_id"]),
        "response": str(resp),
        "decision_seconds": float(p.get("decision_seconds") or p.get("decisionSeconds") or 0.0),
        "presented_left_id": int(p["presented_left_id"]) if p.get("presented_left_id") is not None else (
            int(p["presentedLeftId"]) if p.get("presentedLeftId") is not None else None
        ),
        "presented_right_id": int(p["presented_right_id"]) if p.get("presented_right_id") is not None else (
            int(p["presentedRightId"]) if p.get("presentedRightId") is not None else None
        ),
        "item_a_id": int(p["item_a_id"]) if p.get("item_a_id") is not None else None,
        "item_b_id": int(p["item_b_id"]) if p.get("item_b_id") is not None else None,
    }


def parse_event_timestamp(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        s = str(raw).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None
