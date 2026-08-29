"""Redact participant identities when a project has private participation enabled."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlmodel import Session
    from ..db.models.customer_projects import CustomerProject


def private_participant_label(index_1based: int) -> str:
    return f"unique participant {index_1based}"


PRIVATE_PARTICIPATION_LOCK_MSG = (
    "Private participation is locked once comparisons are collected by others."
)


def has_non_creator_comparisons(
    session: "Session",
    *,
    project: "CustomerProject",
    clear_lock: bool = False,
) -> bool:
    """True when any participant other than the project creator has recorded comparisons."""
    from ..db.models.project_vote_events import ProjectVoteParticipant, VoteSource

    creator_id = int(getattr(project, "project_created_by", 0) or 0)
    rows = ProjectVoteParticipant.list_for_project_system(
        session=session,
        customer_id=int(project.customer_id),
        project_id=int(project.id),
        clear_lock=clear_lock,
    )
    for p in rows:
        comps = int(getattr(p, "comparison_count", None) or getattr(p, "observation_count", 0) or 0)
        groups = int(getattr(p, "group_count", 0) or 0)
        if comps <= 0 and groups <= 0:
            continue
        source = getattr(p, "source", None)
        if source == VoteSource.ai or str(getattr(source, "value", source) or "") == "ai":
            continue
        if source == VoteSource.share or getattr(p, "share_id", None) is not None:
            return True
        user_id = getattr(p, "user_id", None)
        if user_id is None or int(user_id) != creator_id:
            return True
    return False


def private_participation_is_locked(
    session: "Session",
    *,
    project: "CustomerProject",
    clear_lock: bool = False,
) -> bool:
    """Private participation cannot be turned off (except system admin) once enabled and others have compared."""
    if not bool(getattr(project, "private_participation", False)):
        return False
    return has_non_creator_comparisons(session, project=project, clear_lock=clear_lock)


def _as_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return dict(item)
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(getattr(item, "__dict__", {}) or {})


def redact_participant_identity(item: Any, index_1based: int) -> Any:
    """Return a copy of a participant payload/model with name/email replaced."""
    label = private_participant_label(index_1based)
    if isinstance(item, dict):
        out = dict(item)
        out["display_name"] = label
        out["email"] = None
        return out
    if hasattr(item, "model_copy"):
        return item.model_copy(update={"display_name": label, "email": None})
    data = _as_dict(item)
    data["display_name"] = label
    data["email"] = None
    return data


def redact_participant_list(items: list | None) -> list:
    if not items:
        return []
    return [redact_participant_identity(p, i) for i, p in enumerate(items, start=1)]


def redact_report_identities(report: dict | None) -> dict:
    """Anonymize participant names in a build_report payload (view-local indexes)."""
    if not report:
        return report or {}
    out = dict(report)
    out["private_participation"] = True
    out["participants"] = redact_participant_list(out.get("participants") or [])
    pivot = out.get("pivot")
    if isinstance(pivot, dict):
        pivot = dict(pivot)
        pivot["by_participant"] = redact_participant_list(pivot.get("by_participant") or [])
        out["pivot"] = pivot
    return out


def redact_pivot_detail_identities(detail: dict | None) -> dict:
    """Anonymize participant names in a pivot-detail payload (view-local indexes)."""
    if not detail:
        return detail or {}
    out = dict(detail)
    out["private_participation"] = True
    participants = redact_participant_list(out.get("participants") or [])
    out["participants"] = participants
    if (out.get("primary_axis") or "") == "participants" and out.get("row_id") is not None:
        rid = int(out["row_id"])
        hit = next((p for p in participants if p.get("id") == rid), None)
        if hit:
            out["selected_title"] = hit.get("display_name")
        else:
            out["selected_title"] = private_participant_label(1)
    return out
