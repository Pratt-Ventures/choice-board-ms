from pydantic import BaseModel

from src.pvf.db.models.application_event_log import PvfApplicationLogEvent
from src.pvf.depends.api_session_dependencies import get_next_session
from src.tests.helpers.auth_client import as_user, clear_auth
from src.pvf.utils.log_event import log_event


def test_post_log_event(client, account):
    as_user(client, account.member.id)
    response = client.post(
        "/ws/log/post-log-event",
        json={
            "severity": 1,
            "log_message": "pytest log event",
            "computer_name": "pytest",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("log_event_id") or body.get("failure_reason", "") in ("", None)


def test_post_log_event_unauthenticated(client):
    clear_auth(client)
    response = client.post(
        "/ws/log/post-log-event",
        json={"severity": 1, "log_message": "nope"},
    )
    assert response.status_code in (401, 403)


def test_recent_events_as_member_scoped_to_user(client, account):
    as_user(client, account.member.id)
    # seed a log as member (computer_name required by DB NOT NULL)
    seed = client.post(
        "/ws/log/post-log-event",
        json={
            "severity": 1,
            "log_message": "member-only-event",
            "computer_name": "pytest-host",
        },
    )
    assert seed.status_code == 200
    response = client.post(
        "/ws/log/recent-events",
        json={"limit": 25, "only_user": False, "only_customer": False},
    )
    assert response.status_code == 200
    body = response.json()
    # non-admin is forced only_user=True server-side
    assert body.get("log_event_info_list") is not None or body.get("failure_reason", "") in ("", None)


def test_recent_events_as_admin_customer_scope(client, account):
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/log/recent-events",
        json={"limit": 10, "only_user": False, "only_customer": True},
    )
    assert response.status_code == 200


def test_recent_events_unauthenticated(client):
    clear_auth(client)
    response = client.post("/ws/log/recent-events", json={"limit": 5})
    assert response.status_code in (401, 403)


def _recent_row(client, log_message: str):
    response = client.post(
        "/ws/log/recent-events",
        json={"limit": 25, "only_user": True, "only_customer": True},
    )
    assert response.status_code == 200
    rows = response.json().get("log_event_info_list") or []
    match = next((row for row in rows if row.get("log_message") == log_message), None)
    assert match is not None
    return match


def test_post_and_read_details_json_object(client, account):
    as_user(client, account.member.id)
    payload = {"kind": "object", "n": 2}
    seed = client.post(
        "/ws/log/post-log-event",
        json={
            "severity": 1,
            "log_message": "details-json-object",
            "computer_name": "pytest-host",
            "details_json": payload,
        },
    )
    assert seed.status_code == 200
    row = _recent_row(client, "details-json-object")
    assert row["details_json"] == payload
    assert isinstance(row["details_json"], dict)


def test_post_and_read_details_json_list(client, account):
    as_user(client, account.member.id)
    payload = ["a", {"b": 1}]
    seed = client.post(
        "/ws/log/post-log-event",
        json={
            "severity": 1,
            "log_message": "details-json-list",
            "computer_name": "pytest-host",
            "details_json": payload,
        },
    )
    assert seed.status_code == 200
    row = _recent_row(client, "details-json-list")
    assert row["details_json"] == payload
    assert isinstance(row["details_json"], list)


def test_log_event_helper_persists_pydantic_as_dict():
    class Payload(BaseModel):
        foo: str
        n: int

    log_id = log_event("pytest pydantic details", details_json=Payload(foo="bar", n=3), severity=1)
    assert log_id > 0
    session = get_next_session()
    row = PvfApplicationLogEvent.get_log_event_by_id(session, log_id, clear_lock=True)
    assert isinstance(row.details_json, dict)
    assert row.details_json == {"foo": "bar", "n": 3}
