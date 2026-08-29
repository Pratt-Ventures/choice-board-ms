"""Unit tests for private participation redaction helpers."""
from src.utils.private_participation import (
    PRIVATE_PARTICIPATION_LOCK_MSG,
    private_participant_label,
    redact_participant_list,
    redact_pivot_detail_identities,
    redact_report_identities,
)


def test_private_participant_label():
    assert private_participant_label(1) == "unique participant 1"
    assert private_participant_label(12) == "unique participant 12"


def test_private_participation_lock_message():
    assert "locked" in PRIVATE_PARTICIPATION_LOCK_MSG.lower()
    assert "system admin" not in PRIVATE_PARTICIPATION_LOCK_MSG.lower()


def test_redact_participant_list_view_local_index():
    rows = [
        {"id": 50, "display_name": "Ann", "email": "a@x.com"},
        {"id": 9, "display_name": "Bob", "email": "b@x.com"},
    ]
    out = redact_participant_list(rows)
    assert out[0]["id"] == 50
    assert out[0]["display_name"] == "unique participant 1"
    assert out[0]["email"] is None
    assert out[1]["display_name"] == "unique participant 2"


def test_redact_report_and_pivot():
    report = {
        "participants": [
            {"id": 1, "display_name": "Ann", "email": "a@x.com"},
            {"id": 2, "display_name": "Bob", "email": "b@x.com"},
        ],
        "pivot": {
            "by_participant": [
                {"id": 2, "display_name": "Bob", "email": "b@x.com"},
                {"id": 1, "display_name": "Ann", "email": "a@x.com"},
            ]
        },
    }
    out = redact_report_identities(report)
    assert out["private_participation"] is True
    assert out["participants"][0]["display_name"] == "unique participant 1"
    assert out["pivot"]["by_participant"][0]["display_name"] == "unique participant 1"
    assert out["pivot"]["by_participant"][1]["display_name"] == "unique participant 2"

    detail = {
        "primary_axis": "participants",
        "row_id": 2,
        "selected_title": "Bob",
        "participants": [
            {"id": 2, "display_name": "Bob", "email": "b@x.com"},
        ],
    }
    d2 = redact_pivot_detail_identities(detail)
    assert d2["selected_title"] == "unique participant 1"
    assert d2["participants"][0]["email"] is None
