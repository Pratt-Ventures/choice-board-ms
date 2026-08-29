"""Unit tests for optional project end_time helpers."""
from datetime import datetime, timedelta, timezone

from src.utils.project_end_time import (
    COLLECTION_CLOSED_MSG,
    PAST_DATE_MSG,
    collection_block_reason,
    collection_ending_soon,
    collection_is_closed,
    end_time_date_is_past,
    normalize_project_end_time,
    project_input_block_reason,
)


class _Proj:
    def __init__(self, *, disabled=False, end_time=None):
        self.disabled = disabled
        self.end_time = end_time


def test_normalize_none():
    stored, err = normalize_project_end_time(None)
    assert stored is None
    assert err is None


def test_normalize_naive_forces_2359():
    now = datetime(2026, 8, 15, 12, 0, 0)
    stored, err = normalize_project_end_time(datetime(2026, 12, 15, 10, 30, 12), now=now)
    assert err is None
    assert stored == datetime(2026, 12, 15, 23, 59, 0)


def test_normalize_aware_keeps_utc_instant():
    now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    local = datetime(2026, 12, 15, 23, 59, 0, tzinfo=timezone(timedelta(hours=-7)))
    stored, err = normalize_project_end_time(local, now=now)
    assert err is None
    assert stored == local.astimezone(timezone.utc).replace(tzinfo=None)


def test_normalize_rejects_past_date():
    now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    stored, err = normalize_project_end_time(datetime(2026, 8, 13, 23, 59, 0), now=now)
    assert stored is None
    assert err == PAST_DATE_MSG


def test_normalize_allows_today():
    now = datetime(2026, 8, 15, 8, 0, 0)
    stored, err = normalize_project_end_time(datetime(2026, 8, 15, 1, 0, 0), now=now)
    assert err is None
    assert stored == datetime(2026, 8, 15, 23, 59, 0)


def test_past_date_uses_value_timezone():
    now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    yesterday_local = datetime(2026, 8, 14, 23, 59, 0, tzinfo=timezone(timedelta(hours=-7)))
    assert end_time_date_is_past(yesterday_local, now=now) is True


def test_collection_closed_after_grace():
    end = datetime(2026, 8, 15, 23, 59, 0)
    assert collection_is_closed(end, now=datetime(2026, 8, 16, 0, 30, 0)) is False
    assert collection_is_closed(end, now=datetime(2026, 8, 16, 1, 0, 1)) is True
    assert collection_is_closed(None, now=datetime(2026, 8, 16, 12, 0, 0)) is False


def test_collection_ending_soon_window():
    end = datetime(2026, 8, 15, 23, 59, 0)
    assert collection_ending_soon(end, now=datetime(2026, 8, 15, 22, 58, 0)) is False
    assert collection_ending_soon(end, now=datetime(2026, 8, 15, 23, 0, 0)) is True
    assert collection_ending_soon(end, now=datetime(2026, 8, 16, 0, 30, 0)) is True
    assert collection_ending_soon(end, now=datetime(2026, 8, 16, 1, 0, 1)) is False
    assert collection_ending_soon(None, now=datetime(2026, 8, 15, 23, 30, 0)) is False


def test_block_reasons_independent_of_disabled():
    end = datetime(2026, 8, 15, 23, 59, 0)
    now = datetime(2026, 8, 16, 2, 0, 0)
    assert collection_block_reason(end, now=now) == COLLECTION_CLOSED_MSG
    assert project_input_block_reason(_Proj(disabled=True, end_time=None), now=now) == (
        "Project is locked; new votes are not accepted"
    )
    assert project_input_block_reason(_Proj(disabled=True, end_time=end), now=now) == (
        "Project is locked; new votes are not accepted"
    )
    assert project_input_block_reason(_Proj(disabled=False, end_time=end), now=now) == COLLECTION_CLOSED_MSG
    assert project_input_block_reason(_Proj(disabled=False, end_time=None), now=now) is None
