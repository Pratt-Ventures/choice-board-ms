from __future__ import annotations

from datetime import datetime, timedelta, timezone

COLLECTION_CLOSED_MSG = "Comparison collection has ended."
COLLECTION_GRACE = timedelta(hours=1)
PAST_DATE_MSG = "End date must be today or a future date"


def utc_now_naive(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if now.tzinfo is not None:
        return now.astimezone(timezone.utc).replace(tzinfo=None)
    return now


def as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def end_time_date_is_past(value: datetime, *, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if value.tzinfo is not None:
        today = now.astimezone(value.tzinfo).date() if now.tzinfo else now.replace(tzinfo=timezone.utc).astimezone(value.tzinfo).date()
        return value.date() < today
    now_utc = now.astimezone(timezone.utc) if now.tzinfo else now
    return value.date() < now_utc.date()


def normalize_project_end_time(
    value: datetime | None,
    *,
    now: datetime | None = None,
) -> tuple[datetime | None, str | None]:
    if value is None:
        return None, None
    if end_time_date_is_past(value, now=now):
        return None, PAST_DATE_MSG
    if value.tzinfo is not None:
        return as_naive_utc(value), None
    return value.replace(hour=23, minute=59, second=0, microsecond=0), None


def collection_is_closed(end_time: datetime | None, now: datetime | None = None) -> bool:
    if end_time is None:
        return False
    current = utc_now_naive(now)
    return current > as_naive_utc(end_time) + COLLECTION_GRACE


def collection_ending_soon(end_time: datetime | None, now: datetime | None = None) -> bool:
    if end_time is None:
        return False
    current = utc_now_naive(now)
    close_at = as_naive_utc(end_time)
    return close_at - COLLECTION_GRACE <= current <= close_at + COLLECTION_GRACE


def collection_block_reason(end_time: datetime | None, now: datetime | None = None) -> str | None:
    if collection_is_closed(end_time, now=now):
        return COLLECTION_CLOSED_MSG
    return None


def project_input_block_reason(project, now: datetime | None = None) -> str | None:
    if project is None:
        return None
    if getattr(project, "disabled", False):
        return "Project is locked; new votes are not accepted"
    return collection_block_reason(getattr(project, "end_time", None), now=now)


def end_time_iso(end_time: datetime | None) -> str | None:
    if end_time is None:
        return None
    return as_naive_utc(end_time).isoformat()


def project_end_time_payload(project, now: datetime | None = None) -> dict:
    end_time = getattr(project, "end_time", None) if project is not None else None
    return {
        "end_time": end_time_iso(end_time),
        "collection_ending_soon": collection_ending_soon(end_time, now=now),
        "collection_closed": collection_is_closed(end_time, now=now),
    }
