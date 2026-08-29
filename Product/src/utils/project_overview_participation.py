from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db.models.ai_agent_jobs import AiAgentJob
from ..db.models.project_vote_events import ProjectVoteParticipant, VoteSource
from ..pvf.bindings.pvf_services import PvfShareLink, PvfShareLinkMagicKey
from ..pvf.db.models.email_activity_log import PvfEmailActivityLog
from .ai.config import normalize_model_key
from .ai.identity import ai_display_name, build_ai_participant_key, is_ai_participant


_VOTE_SHARE_TYPES = frozenset({"vote", "vote_view"})
_LOCKED_EMAIL_MODES = frozenset({
    "email_matching",
    "email_matching_verified",
    "recipient_email_verified",
    "password_with_email_matching",
    "password_with_email_matching_verified",
    "password_with_recipient_email_verified",
})
_OPEN_VERIFIED_MODES = frozenset({
    "email_any_verified",
    "password_with_email_any_verified",
})
_ANONYMOUS_MODES = frozenset({
    "open_access",
    "email_any_unverified",
    "password_only",
    "password_with_email_any_unverified",
})
_SHARE_INVITE_EMAIL_TYPES = (
    "share_project_vote",
    "share_project_vote_view",
    "share_project_report",
    "resending_invitation",
)
_IN_FLIGHT_STATUSES = frozenset({"queued", "in_progress"})


class AiAgentCounts(BaseModel):
    requested: int = 0
    in_flight: int = 0
    completed: int = 0


class HumanParticipantActiveItem(BaseModel):
    label: str
    comparison_count: int = 0
    participant_id: int | None = None


class HumanParticipantPendingItem(BaseModel):
    label: str
    days_pending: int = 0
    email: str | None = None
    participant_id: int | None = None
    share_id: int | None = None


class AnonymousShareItem(BaseModel):
    label: str
    activated: int = 0
    share_id: int | None = None


class HumanParticipantsSummary(BaseModel):
    active: list[HumanParticipantActiveItem] = Field(default_factory=list)
    pending: list[HumanParticipantPendingItem] = Field(default_factory=list)
    anonymous_shares: list[AnonymousShareItem] = Field(default_factory=list)


class AiParticipantStatusItem(BaseModel):
    model_key: str = ""
    display_name: str = ""
    status: str = ""
    pairs_answered: int = 0
    pairs_remaining: int = 0


def _mode_value(share: Any) -> str:
    mode = getattr(share, "access_mode", None)
    return str(getattr(mode, "value", mode) or "")


def _share_type(share: Any) -> str:
    raw = getattr(share, "shared_type", None)
    return str(getattr(raw, "value", raw) or "")


def _naive_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if getattr(value, "tzinfo", None) is not None:
        return value.replace(tzinfo=None)
    return value


def _days_since(value: datetime | None) -> int:
    ts = _naive_dt(value)
    if ts is None:
        return 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    seconds = (now - ts).total_seconds()
    return max(0, int(seconds // 86400))


def _norm_email(value: str | None) -> str:
    return (value or "").strip().lower()


def _label(*parts: str | None) -> str:
    for part in parts:
        text = (part or "").strip()
        if text:
            return text
    return ""


def _invite_sent_by_token(session: Session, customer_id: int, shares: list) -> dict[str, datetime]:
    emails = {
        _norm_email(getattr(share, "shared_with_email", None))
        for share in shares
        if _norm_email(getattr(share, "shared_with_email", None))
    }
    tokens = {share.magic_token for share in shares if getattr(share, "magic_token", None)}
    if not emails or not tokens:
        return {}
    rows = session.exec(
        select(PvfEmailActivityLog)
        .where(
            PvfEmailActivityLog.customer_id == customer_id,
            PvfEmailActivityLog.email_address.in_(list(emails)),
            PvfEmailActivityLog.email_type.in_(_SHARE_INVITE_EMAIL_TYPES),
        )
        .order_by(PvfEmailActivityLog.id.desc())
    ).all()
    latest: dict[str, datetime] = {}
    for row in rows:
        token = (row.email_params_json or {}).get("magic_token")
        if token in tokens and token not in latest:
            latest[str(token)] = row.create_date
    return latest


def _vote_shares(shares: list) -> list:
    return [s for s in shares if _share_type(s) in _VOTE_SHARE_TYPES]


def _parts_for_share(humans: list[ProjectVoteParticipant], share_id: int) -> list[ProjectVoteParticipant]:
    return [p for p in humans if int(getattr(p, "share_id", 0) or 0) == int(share_id)]


def _active_count(parts: list[ProjectVoteParticipant]) -> int:
    return sum(1 for p in parts if int(p.comparison_count or 0) >= 1)


def build_human_participants(
    session: Session,
    *,
    customer_id: int,
    project_id: int,
    humans: list[ProjectVoteParticipant],
) -> HumanParticipantsSummary:
    shares = list(session.exec(
        select(PvfShareLink).where(
            PvfShareLink.customer_id == customer_id,
            PvfShareLink.shared_entity_db_id == project_id,
        )
    ).all())
    vote_shares = _vote_shares(shares)
    share_ids = [int(s.id) for s in vote_shares if s.id is not None]
    magic_keys = list(session.exec(
        select(PvfShareLinkMagicKey).where(PvfShareLinkMagicKey.share_id.in_(share_ids))
    ).all()) if share_ids else []
    keys_by_share: dict[int, list] = {}
    for key in magic_keys:
        sid = int(getattr(key, "share_id", 0) or 0)
        keys_by_share.setdefault(sid, []).append(key)
    invite_by_token = _invite_sent_by_token(session, customer_id, vote_shares)

    active: list[HumanParticipantActiveItem] = []
    pending: list[HumanParticipantPendingItem] = []
    anonymous: list[AnonymousShareItem] = []
    claimed_active: set[int] = set()
    claimed_pending_emails: set[tuple[int, str]] = set()

    for part in humans:
        if part.source == VoteSource.session and int(part.comparison_count or 0) >= 1:
            active.append(HumanParticipantActiveItem(
                label=_label(part.display_name, part.email, "Team member"),
                comparison_count=int(part.comparison_count or 0),
                participant_id=part.id,
            ))
            if part.id is not None:
                claimed_active.add(int(part.id))

    for share in vote_shares:
        mode = _mode_value(share)
        sid = int(share.id)
        parts = _parts_for_share(humans, sid)
        if mode in _LOCKED_EMAIL_MODES or mode in _OPEN_VERIFIED_MODES:
            for part in parts:
                if int(part.comparison_count or 0) < 1:
                    continue
                if part.id is not None and int(part.id) in claimed_active:
                    continue
                active.append(HumanParticipantActiveItem(
                    label=_label(part.display_name, part.email, share.shared_with_person_name, share.shared_with_email, "Participant"),
                    comparison_count=int(part.comparison_count or 0),
                    participant_id=part.id,
                ))
                if part.id is not None:
                    claimed_active.add(int(part.id))
                    email = _norm_email(part.email)
                    if email:
                        claimed_pending_emails.add((sid, email))

    for part in humans:
        if part.source != VoteSource.session:
            continue
        if int(part.comparison_count or 0) >= 1:
            continue
        pending.append(HumanParticipantPendingItem(
            label=_label(part.display_name, part.email, "Team member"),
            days_pending=_days_since(part.create_date),
            email=part.email,
            participant_id=part.id,
        ))

    for share in vote_shares:
        mode = _mode_value(share)
        sid = int(share.id)
        token = getattr(share, "magic_token", None)
        invite_at = invite_by_token.get(token) if token else None
        parts = _parts_for_share(humans, sid)
        if mode in _LOCKED_EMAIL_MODES:
            if _active_count(parts) >= 1:
                continue
            zero_part = next((p for p in parts if int(p.comparison_count or 0) == 0), None)
            pending.append(HumanParticipantPendingItem(
                label=_label(
                    getattr(zero_part, "display_name", None) if zero_part else None,
                    getattr(zero_part, "email", None) if zero_part else None,
                    share.shared_with_person_name,
                    share.shared_with_email,
                    share.share_link_name,
                    "Invited participant",
                ),
                days_pending=_days_since(invite_at or share.create_date),
                email=_label(getattr(zero_part, "email", None) if zero_part else None, share.shared_with_email) or None,
                participant_id=zero_part.id if zero_part is not None else None,
                share_id=sid,
            ))
            continue
        if mode in _OPEN_VERIFIED_MODES:
            for key in keys_by_share.get(sid, []):
                if getattr(key, "accessed_date", None) is None:
                    continue
                email = _norm_email(key.captured_email)
                if email and (sid, email) in claimed_pending_emails:
                    continue
                matched = None
                for part in parts:
                    if email and _norm_email(part.email) == email:
                        matched = part
                        break
                if matched is not None and int(matched.comparison_count or 0) >= 1:
                    continue
                pending.append(HumanParticipantPendingItem(
                    label=_label(
                        key.captured_display_name,
                        key.captured_email,
                        getattr(matched, "display_name", None) if matched else None,
                        getattr(matched, "email", None) if matched else None,
                        "Verified participant",
                    ),
                    days_pending=_days_since(key.accessed_date or invite_at or share.create_date),
                    email=key.captured_email or (matched.email if matched is not None else None),
                    participant_id=matched.id if matched is not None else None,
                    share_id=sid,
                ))
                if email:
                    claimed_pending_emails.add((sid, email))
            continue
        if mode in _ANONYMOUS_MODES:
            anonymous.append(AnonymousShareItem(
                label=_label(share.share_link_name, share.shared_with_person_name, "Open share"),
                activated=_active_count(parts),
                share_id=sid,
            ))

    active.sort(key=lambda row: (row.label.lower(), row.participant_id or 0))
    pending.sort(key=lambda row: (-row.days_pending, row.label.lower()))
    anonymous.sort(key=lambda row: (row.label.lower(), row.share_id or 0))
    return HumanParticipantsSummary(active=active, pending=pending, anonymous_shares=anonymous)


def _latest_jobs_by_model(jobs: list[AiAgentJob]) -> dict[str, AiAgentJob]:
    latest: dict[str, AiAgentJob] = {}
    for job in jobs:
        key = normalize_model_key(getattr(job, "model_key", None))
        if key not in latest:
            latest[key] = job
    return latest


def _ai_part_for_model(parts: list[ProjectVoteParticipant], model_key: str) -> ProjectVoteParticipant | None:
    want_key = build_ai_participant_key(model_key)
    want_model = normalize_model_key(model_key)
    keyed = None
    modeled = None
    for part in parts:
        if str(getattr(part, "participant_key", "") or "") == want_key:
            keyed = part
            break
        if normalize_model_key(getattr(part, "ai_model", None)) == want_model:
            modeled = modeled or part
    return keyed or modeled


def _job_status(job: AiAgentJob | None, *, participant_complete: bool) -> str:
    if participant_complete:
        return "complete"
    if job is None:
        return "complete" if participant_complete else "queued"
    status = str(job.status or "")
    if status == "complete" or participant_complete:
        return "complete"
    if status in ("queued", "in_progress", "failed"):
        return status
    return status or "queued"


def _pairs_answered(job: AiAgentJob | None, part: ProjectVoteParticipant | None) -> int:
    if job is not None:
        pairs = int(job.pair_count or 0)
        if pairs > 0:
            return pairs
    if part is not None:
        return int(part.comparison_count or 0)
    return 0


def build_ai_participation(
    session: Session,
    *,
    customer_id: int,
    project_id: int,
    participants: list[ProjectVoteParticipant],
    target_comparisons_est: int,
) -> tuple[AiAgentCounts, list[AiParticipantStatusItem]]:
    jobs = AiAgentJob.list_for_project(
        session=session,
        customer_id=customer_id,
        project_id=project_id,
        clear_lock=False,
    )
    latest = _latest_jobs_by_model(jobs)
    ai_parts = [p for p in participants if is_ai_participant(p)]
    model_keys: list[str] = []
    seen: set[str] = set()
    for key in latest:
        if key not in seen:
            seen.add(key)
            model_keys.append(key)
    for part in ai_parts:
        key = normalize_model_key(getattr(part, "ai_model", None))
        if key not in seen:
            seen.add(key)
            model_keys.append(key)

    rows: list[AiParticipantStatusItem] = []
    in_flight = 0
    completed = 0
    for model_key in model_keys:
        job = latest.get(model_key)
        part = _ai_part_for_model(ai_parts, model_key)
        participant_complete = bool(part and part.is_complete)
        status = _job_status(job, participant_complete=participant_complete)
        if status in _IN_FLIGHT_STATUSES:
            in_flight += 1
        elif status == "complete":
            completed += 1
        pairs = _pairs_answered(job, part)
        remaining = 0 if status == "complete" else max(0, int(target_comparisons_est or 0) - pairs)
        details = getattr(job, "details_json", None) or {}
        display = (
            (details.get("display_name") if isinstance(details, dict) else None)
            or getattr(part, "display_name", None)
            or ai_display_name(model_key)
        )
        rows.append(AiParticipantStatusItem(
            model_key=model_key,
            display_name=str(display),
            status=status,
            pairs_answered=pairs,
            pairs_remaining=remaining,
        ))
    rows.sort(key=lambda row: (row.display_name.lower(), row.model_key))
    counts = AiAgentCounts(
        requested=len(model_keys),
        in_flight=in_flight,
        completed=completed,
    )
    return counts, rows
