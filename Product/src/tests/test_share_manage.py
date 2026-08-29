"""Authenticated share-link management: create, extend/disable, activity, tenancy."""
from sqlmodel import select

from src.config.config_settings import settings
from src.pvf.db.models.email_activity_log import PvfEmailActivityLog
from src.pvf.depends.api_session_dependencies import get_next_session
from src.tests.helpers.auth_client import as_user, clear_auth
from src.tests.helpers.factories import create_alternative, create_factor, create_project, uid


def _create_share_payload(project_id: int, **overrides) -> dict:
    body = {
        "shared_type": "vote",
        "shared_entity_db_id": project_id,
        "access_mode": "open_access",
        "link_auto_send": False,
        "share_link_name": f"share-{uid()}",
        "shared_with_email": f"{uid('rcpt')}@example.com",
        "shared_with_person_name": "Recipient",
        "shared_with_company_name": "Acme",
    }
    body.update(overrides)
    return body


def _create_share(client, project_id: int, **overrides) -> dict:
    response = client.post("/ws/create-share-link", json=_create_share_payload(project_id, **overrides))
    assert response.status_code == 200, response.text
    body = response.json()
    assert not body.get("failure_reason"), body
    assert body.get("link_info", {}).get("magic_token")
    assert body.get("link_url")
    return body


def test_create_share_link_unauthenticated(client, account):
    project = create_project(account)
    clear_auth(client)
    response = client.post("/ws/create-share-link", json=_create_share_payload(project.id))
    assert response.status_code in (401, 403)


def test_create_share_link_open_access_happy_path(client, account):
    project = create_project(account)
    create_alternative(account, project_id=project.id)
    create_factor(account, project_id=project.id)
    as_user(client, account.admin.id)
    body = _create_share(client, project.id, shared_type="vote", access_mode="open_access")
    link = body["link_info"]
    assert link["shared_entity_db_id"] == project.id
    assert link["customer_id"] == account.customer.id
    assert link["user_id"] == account.admin.id
    assert link["share_link_enabled"] is True
    assert link["access_mode"] == "open_access"
    assert "/share/vote/" in body["link_url"]
    assert link["magic_token"] in body["link_url"]


def test_create_share_link_types_vote_view_and_report(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    for share_type in ("vote_view", "report"):
        body = _create_share(client, project.id, shared_type=share_type)
        assert body["link_info"]["shared_type"] == share_type
        assert f"/share/{share_type}/" in body["link_url"]


def test_create_share_link_password_is_hashed(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    plain = "S3cret-share-pw"
    body = _create_share(
        client,
        project.id,
        access_mode="password_only",
        share_password=plain,
    )
    stored = body["link_info"].get("share_password")
    assert stored not in (None, "", plain)
    assert stored != plain


def test_create_share_link_invalid_type(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/create-share-link",
        json=_create_share_payload(project.id, shared_type="not_set"),
    )
    assert response.status_code in (200, 422)
    if response.status_code == 200:
        assert response.json().get("failure_reason")


def test_create_share_link_auto_send_email_duration_matches_expiration(client, account):
    """The auto-send invite email reports the link's actual valid duration, not a static message."""
    project = create_project(account)
    as_user(client, account.admin.id)
    recipient = f"{uid('rcpt')}@mailinator.com"
    created = _create_share(
        client,
        project.id,
        shared_type="vote",
        access_mode="email_any_unverified",
        shared_with_email=recipient,
        link_auto_send=True,
        share_link_expiration=14,
    )
    assert created["link_info"]["share_link_expiration"] == 14

    session = get_next_session()
    log_row = session.exec(
        select(PvfEmailActivityLog)
        .where(
            PvfEmailActivityLog.email_address == recipient,
            PvfEmailActivityLog.email_type == "share_project_vote",
        )
        .order_by(PvfEmailActivityLog.id.desc())
    ).first()
    session.close()
    assert log_row is not None
    params = log_row.email_params_json or {}
    assert params.get("valid_duration") == "14 days"


def test_create_share_link_stores_cookie_duration(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    body = _create_share(client, project.id, cookie_duration=3)
    assert body["link_info"]["cookie_duration"] == 3


def test_build_share_landing_url_uses_query_key():
    from src.pvf.api.share_link_manage import build_share_landing_url, share_cookie_max_age_seconds

    url = build_share_landing_url(share_type="vote", magic_token="tokABC", access_magic_key="k9x2")
    assert "/share/vote/tokABC" in url
    assert url.endswith("?key=k9x2") or "?key=k9x2" in url
    assert "/tokABC/k9x2" not in url
    assert share_cookie_max_age_seconds(2) == 2 * 3600 * 24
    assert share_cookie_max_age_seconds(-1) == 10 * 365 * 24 * 3600
    assert share_cookie_max_age_seconds(0) == settings.SHARE_LINK_COOKIE_EXPIRATION_DAYS * 3600 * 24


def test_create_share_link_cross_tenant_project_denied(client, account, other_account):
    foreign = create_project(other_account)
    as_user(client, account.admin.id)
    response = client.post("/ws/create-share-link", json=_create_share_payload(foreign.id))
    assert response.status_code in (200, 403, 422)
    if response.status_code == 200:
        body = response.json()
        assert body.get("failure_reason") or body.get("link_info") is None


def test_create_share_link_as_member_same_customer(client, account):
    """Any authenticated account user may create a share for their project."""
    project = create_project(account)
    as_user(client, account.member.id)
    body = _create_share(client, project.id)
    assert body["link_info"]["user_id"] == account.member.id


def test_extend_or_disable_share_link_by_id(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(client, project.id)
    share_id = created["link_info"]["id"]

    disable = client.post(
        "/ws/extend-or-disable-share-link",
        json={"share_id": share_id, "share_link_enabled": False},
    )
    assert disable.status_code == 200
    assert not disable.json().get("failure_reason"), disable.json()
    assert disable.json().get("link_id") == share_id

    reenable = client.post(
        "/ws/extend-or-disable-share-link",
        json={"share_id": share_id, "share_link_enabled": True, "share_link_expiration": 14},
    )
    assert reenable.status_code == 200
    assert not reenable.json().get("failure_reason"), reenable.json()


def test_extend_or_disable_share_link_by_magic_token(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(client, project.id)
    token = created["link_info"]["magic_token"]
    response = client.post(
        "/ws/extend-or-disable-share-link",
        json={"magic_token": token, "share_link_enabled": False},
    )
    assert response.status_code == 200
    assert not response.json().get("failure_reason"), response.json()


def test_extend_or_disable_unauthenticated(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(client, project.id)
    clear_auth(client)
    response = client.post(
        "/ws/extend-or-disable-share-link",
        json={"share_id": created["link_info"]["id"], "share_link_enabled": False},
    )
    assert response.status_code in (401, 403)


def test_extend_or_disable_cross_tenant_denied(client, account, other_account):
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(client, project.id)
    share_id = created["link_info"]["id"]

    as_user(client, other_account.admin.id)
    response = client.post(
        "/ws/extend-or-disable-share-link",
        json={"share_id": share_id, "share_link_enabled": False},
    )
    assert response.status_code in (200, 403)
    if response.status_code == 200:
        assert response.json().get("failure_reason")


def test_extend_or_disable_non_creator_same_customer_denied(client, account):
    """Update is bound to the creating user, not just the customer."""
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(client, project.id)
    share_id = created["link_info"]["id"]

    as_user(client, account.member.id)
    response = client.post(
        "/ws/extend-or-disable-share-link",
        json={"share_id": share_id, "share_link_enabled": False},
    )
    assert response.status_code in (200, 403)
    if response.status_code == 200:
        assert response.json().get("failure_reason")


def test_get_share_activity_single_project(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(client, project.id)
    response = client.get(
        "/ws/get-share-activity-single-project",
        params={"project_id": project.id},
    )
    assert response.status_code == 200
    body = response.json()
    assert not body.get("failure_reason"), body
    shares = body.get("share_info_list") or []
    match = next(s for s in shares if s.get("share_id") == created["link_info"]["id"])
    # Activity responses redact password hash; expose set/not-set only.
    assert match.get("share_link", {}).get("share_password") in (None, "")
    assert "password_set" in match
    assert "session_count" in match
    assert "observation_count" in match
    assert match.get("invite_email_sent") is False
    assert "share_link_expired" in match


def test_get_share_activity_password_set_flag(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(
        client,
        project.id,
        access_mode="password_only",
        share_password="S3cret-share-pw",
    )
    response = client.get(
        "/ws/get-share-activity-single-project",
        params={"project_id": project.id},
    )
    assert response.status_code == 200
    body = response.json()
    shares = body.get("share_info_list") or []
    match = next(s for s in shares if s.get("share_id") == created["link_info"]["id"])
    assert match.get("password_set") is True
    assert match.get("share_link", {}).get("share_password") in (None, "")


def test_get_share_activity_multiple_projects(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(client, project.id)
    response = client.post(
        "/ws/get-share-activity-multiple-projects",
        json=[project.id],
    )
    assert response.status_code == 200
    body = response.json()
    assert not body.get("failure_reason"), body
    by_project = body.get("share_info_list_per_project_id") or {}
    # JSON object keys are strings
    entries = by_project.get(str(project.id)) or by_project.get(project.id) or []
    assert any(e.get("share_id") == created["link_info"]["id"] for e in entries)


def test_get_share_activity_cross_tenant_empty_or_denied(client, account, other_account):
    project = create_project(account)
    as_user(client, account.admin.id)
    _create_share(client, project.id)

    as_user(client, other_account.admin.id)
    response = client.get(
        "/ws/get-share-activity-single-project",
        params={"project_id": project.id},
    )
    assert response.status_code == 200
    body = response.json()
    shares = body.get("share_info_list") or []
    assert body.get("failure_reason") or len(shares) == 0


# --- share actions model (possible actions on the share; used actions journaled) ---

def test_share_actions_default_from_action_matrix(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    body = _create_share(client, project.id)
    # no share_actions supplied -> defaulted from the registered action matrix
    assert body["link_info"]["share_actions"] == ["vote", "view", "report"]


def test_share_actions_explicit_subset_accepted(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    body = _create_share(client, project.id, share_actions=["view"])
    assert body["link_info"]["share_actions"] == ["view"]


def test_share_actions_unknown_action_rejected(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    response = client.post("/ws/create-share-link", json=_create_share_payload(project.id, share_actions=["dance"]))
    assert response.status_code == 422


def test_share_create_fails_descriptively_without_entity_resolver(client, account, monkeypatch):
    from src.pvf.db.models import share_link_tracking
    from src.pvf.bindings.pvf_invocation import PvfHookRegistry

    monkeypatch.setattr(share_link_tracking, "get_hooks", lambda: PvfHookRegistry())
    project = create_project(account)
    as_user(client, account.admin.id)
    response = client.post("/ws/create-share-link", json=_create_share_payload(project.id))
    assert response.status_code == 500
    assert "not fully configured" in response.json()["detail"]


def test_operation_journaled_on_share_access(client, account):
    from src.pvf.db.models.share_link_tracking import PvfShareLinkAccessed

    project = create_project(account)
    as_user(client, account.admin.id)
    body = _create_share(client, project.id, shared_type="vote_view", access_mode="open_access")
    token = body["link_info"]["magic_token"]
    clear_auth(client)
    response = client.post(f"/ext-ws/share/{token}/vote-view", json={"display_name": "Viewer"})
    assert response.status_code == 200, response.text

    with get_next_session() as session:
        rows = session.exec(select(PvfShareLinkAccessed).where(PvfShareLinkAccessed.share_magic_token == token)).all()
    assert rows, "expected a share access record"
    assert "view" in (rows[0].access_operation or [])


def _latest_invite_log(recipient: str, email_type: str | None = None):
    session = get_next_session()
    query = select(PvfEmailActivityLog).where(PvfEmailActivityLog.email_address == recipient.lower())
    if email_type is not None:
        query = query.where(PvfEmailActivityLog.email_type == email_type)
    log_row = session.exec(query.order_by(PvfEmailActivityLog.id.desc())).first()
    session.close()
    return log_row


def test_send_share_invitation_first_send_uses_share_type_template(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    recipient = f"{uid('rcpt')}@mailinator.com"
    created = _create_share(
        client,
        project.id,
        shared_type="vote",
        access_mode="email_any_unverified",
        shared_with_email=recipient,
        link_auto_send=False,
        share_link_expiration=14,
    )
    share_id = created["link_info"]["id"]
    token = created["link_info"]["magic_token"]

    response = client.post("/ws/send-share-invitation", json={"share_id": share_id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert not body.get("failure_reason"), body
    assert body.get("link_email_sent") is True
    assert body.get("was_resend") is False
    assert body.get("email_type") == "share_project_vote"

    log_row = _latest_invite_log(recipient, "share_project_vote")
    assert log_row is not None
    params = log_row.email_params_json or {}
    assert params.get("valid_duration") == "14 days"
    assert params.get("magic_token") == token
    assert params.get("share_id") == share_id
    assert "Password:" not in (params.get("share_password_note") or "")


def test_send_share_invitation_resend_uses_resending_invitation(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    recipient = f"{uid('rcpt')}@mailinator.com"
    created = _create_share(
        client,
        project.id,
        shared_type="vote_view",
        access_mode="email_any_unverified",
        shared_with_email=recipient,
        link_auto_send=True,
    )
    share_id = created["link_info"]["id"]
    token_before = created["link_info"]["magic_token"]

    response = client.post("/ws/send-share-invitation", json={"share_id": share_id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert not body.get("failure_reason"), body
    assert body.get("was_resend") is True
    assert body.get("email_type") == "resending_invitation"
    assert created["link_info"]["magic_token"] == token_before

    log_row = _latest_invite_log(recipient, "resending_invitation")
    assert log_row is not None
    params = log_row.email_params_json or {}
    assert params.get("magic_token") == token_before
    assert params.get("shared_type") == "vote_view"

    activity = client.get("/ws/get-share-activity-single-project", params={"project_id": project.id})
    assert activity.status_code == 200
    match = next(s for s in (activity.json().get("share_info_list") or []) if s.get("share_id") == share_id)
    assert match.get("invite_email_sent") is True
    assert match.get("invite_email_last_sent")


def test_send_share_invitation_report_type_and_by_magic_token(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    recipient = f"{uid('rcpt')}@mailinator.com"
    created = _create_share(
        client,
        project.id,
        shared_type="report",
        access_mode="email_any_unverified",
        shared_with_email=recipient,
    )
    token = created["link_info"]["magic_token"]
    response = client.post("/ws/send-share-invitation", json={"magic_token": token})
    assert response.status_code == 200, response.text
    body = response.json()
    assert not body.get("failure_reason"), body
    assert body.get("email_type") == "share_project_report"


def test_send_share_invitation_password_never_included_on_later_send(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    recipient = f"{uid('rcpt')}@mailinator.com"
    created = _create_share(
        client,
        project.id,
        access_mode="password_only",
        share_password="S3cret-share-pw",
        share_password_in_email=True,
        shared_with_email=recipient,
    )
    response = client.post("/ws/send-share-invitation", json={"share_id": created["link_info"]["id"]})
    assert response.status_code == 200, response.text
    assert not response.json().get("failure_reason"), response.json()
    log_row = _latest_invite_log(recipient, "share_project_vote")
    assert log_row is not None
    note = (log_row.email_params_json or {}).get("share_password_note") or ""
    assert "S3cret-share-pw" not in note
    assert "Password:" not in note
    assert "separately" in note.lower()


def test_send_share_invitation_missing_recipient_email(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(client, project.id, shared_with_email=None)
    response = client.post("/ws/send-share-invitation", json={"share_id": created["link_info"]["id"]})
    assert response.status_code == 200
    assert response.json().get("failure_reason")


def test_send_share_invitation_disabled_link_refused(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(client, project.id, shared_with_email=f"{uid('rcpt')}@mailinator.com")
    share_id = created["link_info"]["id"]
    disable = client.post("/ws/extend-or-disable-share-link", json={"share_id": share_id, "share_link_enabled": False})
    assert disable.status_code == 200
    assert not disable.json().get("failure_reason"), disable.json()
    response = client.post("/ws/send-share-invitation", json={"share_id": share_id})
    assert response.status_code == 200
    assert "disabled" in (response.json().get("failure_reason") or "").lower()


def test_send_share_invitation_expired_link_refused(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(
        client,
        project.id,
        shared_with_email=f"{uid('rcpt')}@mailinator.com",
        share_link_expiration=1,
    )
    share_id = created["link_info"]["id"]
    from src.pvf.db.models.share_link_tracking import PvfShareLink
    from datetime import datetime, timedelta

    session = get_next_session()
    row = session.get(PvfShareLink, share_id)
    assert row is not None
    row.create_date = datetime.now() - timedelta(days=3)
    session.add(row)
    session.commit()
    session.close()

    response = client.post("/ws/send-share-invitation", json={"share_id": share_id})
    assert response.status_code == 200
    reason = (response.json().get("failure_reason") or "").lower()
    assert "expired" in reason


def test_send_share_invitation_unauthenticated(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(client, project.id, shared_with_email=f"{uid('rcpt')}@mailinator.com")
    clear_auth(client)
    response = client.post("/ws/send-share-invitation", json={"share_id": created["link_info"]["id"]})
    assert response.status_code in (401, 403)


def test_send_share_invitation_cross_tenant_denied(client, account, other_account):
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(client, project.id, shared_with_email=f"{uid('rcpt')}@mailinator.com")
    as_user(client, other_account.admin.id)
    response = client.post("/ws/send-share-invitation", json={"share_id": created["link_info"]["id"]})
    assert response.status_code in (200, 403)
    if response.status_code == 200:
        assert response.json().get("failure_reason")


def test_send_share_invitation_non_creator_member_denied(client, account):
    project = create_project(account)
    as_user(client, account.admin.id)
    created = _create_share(client, project.id, shared_with_email=f"{uid('rcpt')}@mailinator.com")
    as_user(client, account.member.id)
    response = client.post("/ws/send-share-invitation", json={"share_id": created["link_info"]["id"]})
    assert response.status_code == 403


def test_send_share_invitation_creator_member_allowed(client, account):
    project = create_project(account)
    as_user(client, account.member.id)
    created = _create_share(
        client,
        project.id,
        shared_with_email=f"{uid('rcpt')}@mailinator.com",
    )
    response = client.post("/ws/send-share-invitation", json={"share_id": created["link_info"]["id"]})
    assert response.status_code == 200, response.text
    assert not response.json().get("failure_reason"), response.json()
    assert response.json().get("link_email_sent") is True
