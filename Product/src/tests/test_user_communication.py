from contextlib import contextmanager
from io import BytesIO

from sqlmodel import select

from src.config.config_settings import settings
from src.pvf.db.models.user_communication import PvfBugReport, PvfSuggestion
from src.pvf.db.models.application_event_log import PvfApplicationLogEvent
from src.pvf.depends.api_session_dependencies import get_next_session
from src.tests.helpers.auth_client import as_user, clear_auth
from src.tests.helpers.factories import uid

_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@contextmanager
def _max_per_day(value: int):
    prior = settings.MAX_REPORTS_PER_DAY
    settings.MAX_REPORTS_PER_DAY = value
    try:
        yield
    finally:
        settings.MAX_REPORTS_PER_DAY = prior


def _submit_bug(client, **overrides):
    data = {
        "summary": overrides.pop("summary", f"Bug {uid()}"),
        "what_happened": overrides.pop("what_happened", "It broke"),
        "expected_happened": overrides.pop("expected_happened", "It should work"),
        "steps_to_reproduce": overrides.pop("steps_to_reproduce", "1. Open\n2. Click"),
        "impact": overrides.pop("impact", "moderate"),
    }
    files = overrides.pop("files", None)
    return client.post("/ws/user-comm/bug-report-submit", data=data, files=files)


def _submit_suggestion(client, **overrides):
    data = {
        "suggestion": overrides.pop("suggestion", f"Add {uid()}"),
        "accomplish_goal": overrides.pop("accomplish_goal", "Faster setup"),
        "product_area": overrides.pop("product_area", "projects"),
        "importance": overrides.pop("importance", "important"),
    }
    files = overrides.pop("files", None)
    return client.post("/ws/user-comm/suggestion-submit", data=data, files=files)


def test_unauthenticated_submit_rejected(client):
    clear_auth(client)
    response = _submit_bug(client)
    assert response.status_code in (401, 403)


def test_member_submit_and_count(client, account):
    as_user(client, account.member.id)
    with _max_per_day(10):
        response = _submit_bug(client, summary="PvfLogin spinner never stops")
    assert response.status_code == 200, response.text
    body = response.json()
    assert not body.get("failure_reason"), body
    assert body.get("stored") is True
    assert body.get("limit_warning") is False
    assert body.get("submitted_in_window") >= 1
    assert body.get("max_per_day") == 10
    assert body.get("submission_id")


def test_rate_limit_warns_then_discards(client, account):
    as_user(client, account.member.id)
    marker = uid("limit")
    with _max_per_day(2):
        first = _submit_bug(client, summary=f"{marker}-1")
        second = _submit_bug(client, summary=f"{marker}-2")
        third = _submit_bug(client, summary=f"{marker}-3")
        fourth = _submit_bug(client, summary=f"{marker}-4")
    assert first.status_code == 200 and first.json().get("stored") is True
    assert not first.json().get("failure_reason")
    assert second.json().get("stored") is True
    assert second.json().get("submitted_in_window") >= 2
    assert second.json().get("max_per_day") == 2
    assert third.status_code == 200
    assert third.json().get("stored") is True
    assert third.json().get("limit_warning") is True
    assert "daily submission limit" in (third.json().get("failure_reason") or "")
    assert third.json().get("submitted_in_window") >= 3
    assert third.json().get("max_per_day") == 2
    assert fourth.status_code == 200
    assert fourth.json().get("stored") is False
    assert "discarded" in (fourth.json().get("failure_reason") or "").lower()
    assert fourth.json().get("max_per_day") == 2
    log_id = fourth.json().get("log_id")
    assert log_id
    session = get_next_session()
    try:
        event = PvfApplicationLogEvent.get_log_event_by_id(session, id=log_id, clear_lock=False)
        assert event is not None
        details = event.details_json or {}
        assert details.get("type") == "bug_report"
        assert details.get("title") == f"{marker}-4"
        assert details.get("fields", {}).get("summary") == f"{marker}-4"
    finally:
        session.close()


def test_member_retrieves_own_only(client, account):
    as_user(client, account.member.id)
    mine = _submit_bug(client, summary="member-only-row")
    assert mine.status_code == 200
    as_user(client, account.admin.id)
    _submit_bug(client, summary="admin-row")
    as_user(client, account.member.id)
    listed = client.post("/ws/user-comm/bug-report-retrieve")
    assert listed.status_code == 200
    items = listed.json().get("items") or []
    summaries = {row.get("summary") for row in items}
    assert "member-only-row" in summaries
    assert "admin-row" not in summaries
    assert all(row.get("user_id") == account.member.id for row in items)


def test_customer_admin_retrieves_tenant(client, account):
    as_user(client, account.member.id)
    _submit_suggestion(client, suggestion="from-member")
    as_user(client, account.admin.id)
    _submit_suggestion(client, suggestion="from-admin")
    listed = client.post("/ws/user-comm/suggestion-retrieve")
    assert listed.status_code == 200
    texts = {row.get("suggestion") for row in (listed.json().get("items") or [])}
    assert "from-member" in texts
    assert "from-admin" in texts
    assert all(row.get("customer_id") == account.customer.id for row in listed.json().get("items") or [])
    assert any(row.get("user_name") for row in listed.json().get("items") or [])


def test_cross_tenant_retrieve_empty(client, account, other_account):
    as_user(client, account.admin.id)
    _submit_bug(client, summary="tenant-a-secret")
    as_user(client, other_account.admin.id)
    listed = client.post("/ws/user-comm/bug-report-retrieve")
    assert listed.status_code == 200
    summaries = {row.get("summary") for row in (listed.json().get("items") or [])}
    assert "tenant-a-secret" not in summaries


def test_owner_delete_before_admin_action(client, account):
    as_user(client, account.member.id)
    created = _submit_bug(client, summary="deletable")
    submission_id = created.json().get("submission_id")
    deleted = client.post("/ws/user-comm/bug-report-delete", json={"id": submission_id})
    assert deleted.status_code == 200
    body = deleted.json()
    assert body.get("success") is True
    listed = client.post("/ws/user-comm/bug-report-retrieve")
    ids = {row.get("id") for row in (listed.json().get("items") or [])}
    assert submission_id not in ids


def test_owner_delete_after_ack_denied(client, account, sysadmin_account):
    as_user(client, account.member.id)
    created = _submit_suggestion(client, suggestion="already-acked")
    submission_id = created.json().get("submission_id")
    as_user(client, sysadmin_account.admin.id)
    modified = client.post(
        "/ws/user-comm/suggestion-admin-modify",
        json={"id": submission_id, "acknowledge_date_action": "set", "acknowledge_note": "Got it"},
    )
    assert modified.status_code == 200
    assert not modified.json().get("failure_reason"), modified.json()
    as_user(client, account.member.id)
    denied = client.post("/ws/user-comm/suggestion-delete", json={"id": submission_id})
    assert denied.status_code == 200
    assert denied.json().get("success") is False
    assert denied.json().get("failure_reason")


def test_sysadmin_delete_any(client, account, sysadmin_account):
    as_user(client, account.member.id)
    created = _submit_bug(client, summary="sysadmin-can-delete")
    submission_id = created.json().get("submission_id")
    as_user(client, sysadmin_account.admin.id)
    deleted = client.post("/ws/user-comm/bug-report-delete", json={"id": submission_id})
    assert deleted.status_code == 200
    assert deleted.json().get("success") is True


def test_sysadmin_modify_set_clear_and_notes_only(client, account, sysadmin_account):
    as_user(client, account.admin.id)
    created = _submit_bug(client, summary="lifecycle")
    submission_id = created.json().get("submission_id")
    as_user(client, sysadmin_account.admin.id)
    notes_only = client.post(
        "/ws/user-comm/bug-report-admin-modify",
        json={"id": submission_id, "response_note": "Looking into this"},
    )
    assert notes_only.status_code == 200
    item = notes_only.json().get("item") or {}
    assert item.get("response_note") == "Looking into this"
    assert item.get("response_date") in (None, "")
    stamped = client.post(
        "/ws/user-comm/bug-report-admin-modify",
        json={"id": submission_id, "response_date_action": "set", "resolution_date_action": "set"},
    )
    item = stamped.json().get("item") or {}
    assert item.get("response_date")
    assert item.get("resolution_date")
    assert item.get("response_user_id") == sysadmin_account.admin.id
    cleared = client.post(
        "/ws/user-comm/bug-report-admin-modify",
        json={"id": submission_id, "response_date_action": "clear", "response_note": ""},
    )
    item = cleared.json().get("item") or {}
    assert item.get("response_date") in (None, "")
    assert item.get("response_user_id") in (None, 0)
    assert item.get("response_note") in (None, "")
    assert item.get("resolution_date")


def test_member_and_customer_admin_admin_routes_forbidden(client, account):
    as_user(client, account.member.id)
    created = _submit_bug(client, summary="no-admin")
    submission_id = created.json().get("submission_id")
    retrieve = client.post("/ws/user-comm/bug-report-admin-retrieve", json={"offset": 0, "limit": 25})
    assert retrieve.status_code == 403
    modify = client.post(
        "/ws/user-comm/bug-report-admin-modify",
        json={"id": submission_id, "acknowledge_note": "nope"},
    )
    assert modify.status_code == 403
    as_user(client, account.admin.id)
    retrieve_admin = client.post("/ws/user-comm/suggestion-admin-retrieve", json={"offset": 0, "limit": 10})
    assert retrieve_admin.status_code == 403
    modify_admin = client.post(
        "/ws/user-comm/suggestion-admin-modify",
        json={"id": 1, "acknowledge_note": "nope"},
    )
    assert modify_admin.status_code == 403


def test_sysadmin_admin_retrieve_paginated(client, account, sysadmin_account):
    as_user(client, account.admin.id)
    _submit_suggestion(client, suggestion="newest-one")
    as_user(client, sysadmin_account.admin.id)
    listed = client.post("/ws/user-comm/suggestion-admin-retrieve", json={"offset": 0, "limit": 25})
    assert listed.status_code == 200
    body = listed.json()
    assert not body.get("failure_reason"), body
    assert body.get("total_count") >= 1
    items = body.get("items") or []
    assert items
    assert items[0].get("create_date")
    if len(items) > 1:
        assert items[0]["create_date"] >= items[1]["create_date"]


def test_attachment_acl(client, account, other_account, sysadmin_account):
    as_user(client, account.member.id)
    created = _submit_bug(
        client,
        summary="with-shot",
        files={"file": ("shot.png", BytesIO(_PNG), "image/png")},
    )
    assert created.status_code == 200, created.text
    assert created.json().get("stored") is True
    submission_id = created.json().get("submission_id")
    own = client.get(f"/ws/user-comm/bug-report-attachment/{submission_id}")
    assert own.status_code == 200
    assert own.content == _PNG
    as_user(client, account.admin.id)
    tenant_admin = client.get(f"/ws/user-comm/bug-report-attachment/{submission_id}")
    assert tenant_admin.status_code == 200
    as_user(client, other_account.admin.id)
    other = client.get(f"/ws/user-comm/bug-report-attachment/{submission_id}")
    assert other.status_code == 404
    as_user(client, sysadmin_account.admin.id)
    sysadmin = client.get(f"/ws/user-comm/bug-report-attachment/{submission_id}")
    assert sysadmin.status_code == 200
    as_user(client, account.admin.id)
    listed = client.post("/ws/user-comm/bug-report-retrieve")
    row = next(r for r in (listed.json().get("items") or []) if r.get("id") == submission_id)
    assert row.get("has_attachment") is True
    assert "attachment_bytes" not in row


def test_window_counts_include_soft_deleted(client, account):
    as_user(client, account.member.id)
    with _max_per_day(1):
        first = _submit_suggestion(client, suggestion="keep-count-1")
        assert first.json().get("stored") is True
        deleted = client.post("/ws/user-comm/suggestion-delete", json={"id": first.json().get("submission_id")})
        assert deleted.json().get("success") is True
        second = _submit_suggestion(client, suggestion="keep-count-2")
        assert second.json().get("stored") is True
        assert second.json().get("limit_warning") is True
        third = _submit_suggestion(client, suggestion="keep-count-3")
        assert third.json().get("stored") is False
        assert "discarded" in (third.json().get("failure_reason") or "").lower()


def test_context_exposes_enable_user_communication(client, account):
    as_user(client, account.admin.id)
    response = client.post("/ws/core/get-user-customer-context", json={"include_account_status": False})
    assert response.status_code == 200
    flags = response.json().get("settings") or {}
    assert "enable_user_communication" in flags
    assert flags["enable_user_communication"] is settings.ACTIVATE_CUSTOMER_COMMUNICATION
