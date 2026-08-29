from __future__ import annotations

from typing import Any

from .identity import participant_is_complete, partition_vote_data


def _group_complete(row: Any) -> bool:
    status = getattr(row, "status", None)
    if status is None and isinstance(row, dict):
        status = row.get("status")
    raw = getattr(status, "value", status)
    return str(raw or "") == "complete"


def _as_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(getattr(item, "__dict__", {}) or {})


def _slice_payload(report: dict) -> dict:
    return {
        "option_ranking": report.get("option_ranking") or [],
        "option_ranking_equal": report.get("option_ranking_equal") or [],
        "factor_ranking": report.get("factor_ranking") or [],
        "by_factor": report.get("by_factor") or {},
        "unique_participants": report.get("unique_participants") or 0,
        "group_count": report.get("group_count") or 0,
        "comparison_count": report.get("comparison_count") or 0,
        "metrics": report.get("metrics") or {},
        "participants": report.get("participants") or [],
    }


def _rank_index(ranking: list | None) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for i, raw in enumerate(ranking or [], start=1):
        row = _as_dict(raw)
        try:
            rid = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        rank = row.get("rank")
        try:
            rank_n = int(rank) if rank is not None else i
        except (TypeError, ValueError):
            rank_n = i
        out[rid] = {
            "id": rid,
            "title": row.get("title") or row.get("alternative_title") or row.get("factor_title") or str(rid),
            "rank": rank_n,
            "score": row.get("score"),
        }
    return out


def _catalog_title(rows: list | None, rid: int) -> str:
    for raw in rows or []:
        row = _as_dict(raw)
        try:
            if int(row.get("id")) != rid:
                continue
        except (TypeError, ValueError):
            continue
        return str(
            row.get("title")
            or row.get("alternative_title")
            or row.get("factor_title")
            or rid
        )
    return str(rid)


def _compare_rankings(human_rows: list | None, agent_rows: list | None, catalog: list | None) -> list[dict]:
    human = _rank_index(human_rows)
    agent = _rank_index(agent_rows)
    ids = list(dict.fromkeys([*human.keys(), *agent.keys()]))
    if not ids and catalog:
        for raw in catalog:
            row = _as_dict(raw)
            try:
                ids.append(int(row.get("id")))
            except (TypeError, ValueError):
                continue
    out = []
    for rid in ids:
        h = human.get(rid)
        a = agent.get(rid)
        title = (h or a or {}).get("title") or _catalog_title(catalog, rid)
        human_rank = h["rank"] if h else None
        agent_rank = a["rank"] if a else None
        delta = None
        if human_rank is not None and agent_rank is not None:
            delta = human_rank - agent_rank
        out.append({
            "id": rid,
            "title": title,
            "human_rank": human_rank,
            "agent_rank": agent_rank,
            "rank_delta": delta,
            "human_score": h.get("score") if h else None,
            "agent_score": a.get("score") if a else None,
        })
    out.sort(key=lambda r: (r["human_rank"] is None, r["human_rank"] or 0, r["title"]))
    return out


def build_report_with_ai_baseline(
    *,
    alternatives: list | None,
    factors: list | None,
    exclusive_mode: bool = False,
    all_groups: list | None = None,
    participants: list | None = None,
    settings: dict | None = None,
) -> dict:
    from ..vote_ranking import build_report

    human_parts, human_groups, ai_parts, ai_groups = partition_vote_data(participants, all_groups)
    report = build_report(
        alternatives=alternatives,
        factors=factors,
        exclusive_mode=exclusive_mode,
        all_groups=human_groups,
        participants=human_parts,
        settings=settings,
    )
    human_slice = _slice_payload(report)
    complete_ai = [p for p in ai_parts if participant_is_complete(p)]
    complete_groups = [g for g in ai_groups if _group_complete(g)]
    agents_report = None
    combined_report = None
    if complete_ai and complete_groups:
        agents_report = build_report(
            alternatives=alternatives,
            factors=factors,
            exclusive_mode=exclusive_mode,
            all_groups=complete_groups,
            participants=complete_ai,
            settings=settings,
        )
        combined_report = build_report(
            alternatives=alternatives,
            factors=factors,
            exclusive_mode=exclusive_mode,
            all_groups=[*human_groups, *complete_groups],
            participants=[*human_parts, *complete_ai],
            settings=settings,
        )
        agents_slice = _slice_payload(agents_report)
        combined_slice = _slice_payload(combined_report)
        report["analysis"] = {
            "human": human_slice,
            "agents": agents_slice,
            "combined": combined_slice,
            "comparison": {
                "option_ranking": _compare_rankings(
                    human_slice.get("option_ranking"),
                    agents_slice.get("option_ranking"),
                    alternatives,
                ),
                "factor_ranking": _compare_rankings(
                    human_slice.get("factor_ranking"),
                    agents_slice.get("factor_ranking"),
                    factors,
                ),
            },
        }
        report["ai_baseline"] = {
            "available": True,
            "status": "complete",
            "label": "Agents",
            **agents_slice,
        }
        return report
    report["analysis"] = {
        "human": human_slice,
        "agents": None,
        "combined": None,
        "comparison": None,
    }
    if ai_parts:
        report["ai_baseline"] = {
            "available": False,
            "status": "in_progress",
            "label": "Agents",
        }
    else:
        report["ai_baseline"] = None
    return report
