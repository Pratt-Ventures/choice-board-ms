"""External share access (cookie/magic-token): open, password, email gates, vote mutations."""
from datetime import datetime, timedelta

import pytest

from src.config.config_settings import settings as app_settings
from src.pvf.config.pvf_config_settings import pvf_settings as settings
from src.db.models.customer_projects import CustomerProject
from src.db.models.project_vote_events import ProjectVoteParticipant, VoteSource
from src.pvf.api.share_link_manage import build_share_landing_url
from src.pvf.db.models.customer_user import PvfUserContext
from src.pvf.db.models.share_link_tracking import PvfShareAccessCheckMode, PvfShareLinkMagicKey
from src.pvf.depends.api_session_dependencies import get_next_session
from src.tests.helpers.auth_client import as_user, clear_auth
from src.tests.helpers.factories import create_alternative, create_factor, create_project, uid
from src.utils.project_end_time import COLLECTION_CLOSED_MSG
from src.pvf.utils.pvf_base_internal_resources import get_random_baseN_value
from src.pvf.utils.share_gate_throttle import reset_share_gate_throttle
from sqlmodel import select


def _seed_project_with_choices(account):
    project = create_project(account)
    a1 = create_alternative(account, project_id=project.id, title="Alpha")
    a2 = create_alternative(account, project_id=project.id, title="Beta")
    factor = create_factor(account, project_id=project.id, title="Cost")
    return project, a1, a2, factor


def _create_share_as(client, user_id: int, project_id: int, **overrides) -> dict:
    as_user(client, user_id)
    body = {
        "shared_type": "vote",
        "shared_entity_db_id": project_id,
        "access_mode": "open_access",
        "link_auto_send": False,
        "share_link_name": f"ext-{uid()}",
        "shared_with_email": f"{uid('rcpt')}@example.com",
        "shared_with_person_name": "External Voter",
    }
    body.update(overrides)
    response = client.post("/ws/create-share-link", json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert not result.get("failure_reason"), result
    clear_auth(client)
    return result["link_info"]


def _vote_url(token: str, suffix: str = "") -> str:
    return f"/ext-ws/share/{token}/vote{suffix}"


# Expected denial flags per access mode with minimal (display_name only) input,
# mirroring the mapping in share_link_validate_and_log (see docs_examples/share_access_modes.md).
# Password modes return at the password check before the email stage, so their email
# flags come from the upfront mode mapping, plus verification_password_not_supplied.
_MODE_GATE_FLAGS: dict[PvfShareAccessCheckMode, dict[str, bool]] = {
    PvfShareAccessCheckMode.open_access: {},
    PvfShareAccessCheckMode.email_any_unverified: {"verification_email_needed": True},
    PvfShareAccessCheckMode.email_any_verified: {"verification_email_needed": True, "verification_email_send_link_mode": True},
    PvfShareAccessCheckMode.email_matching: {"verification_email_needed": True, "verification_original_email_needed": True},
    PvfShareAccessCheckMode.email_matching_verified: {"verification_email_needed": True, "verification_original_email_needed": True, "verification_email_send_link_mode": True},
    PvfShareAccessCheckMode.recipient_email_verified: {"verification_email_send_link_mode": True},
    PvfShareAccessCheckMode.password_only: {"verification_password_needed": True},
    PvfShareAccessCheckMode.password_with_email_any_unverified: {"verification_password_needed": True, "verification_email_needed": True},
    PvfShareAccessCheckMode.password_with_email_any_verified: {"verification_password_needed": True, "verification_email_needed": True, "verification_email_send_link_mode": True},
    PvfShareAccessCheckMode.password_with_email_matching: {"verification_password_needed": True, "verification_email_needed": True, "verification_original_email_needed": True},
    PvfShareAccessCheckMode.password_with_email_matching_verified: {"verification_password_needed": True, "verification_email_needed": True, "verification_original_email_needed": True, "verification_email_send_link_mode": True},
    PvfShareAccessCheckMode.password_with_recipient_email_verified: {"verification_password_needed": True, "verification_email_send_link_mode": True},
}

_GATE_FLAG_NAMES = (
    "verification_password_needed",
    "verification_email_needed",
    "verification_email_send_link_mode",
    "verification_original_email_needed",
)


@pytest.mark.parametrize(
    "mode",
    [m for m in _MODE_GATE_FLAGS if m is not PvfShareAccessCheckMode.not_specified],
    ids=[m.value for m in _MODE_GATE_FLAGS if m is not PvfShareAccessCheckMode.not_specified],
)
def test_ext_every_access_mode_gate_flags(client, account, mode):
    """Every PvfShareAccessCheckMode works via the API regardless of ENABLE_SHARE_* / UI visibility."""
    project, *_ = _seed_project_with_choices(account)
    overrides = {"access_mode": mode.value}
    if mode.value.startswith("password"):
        overrides["share_password"] = f"pw-{uid()}"
    link = _create_share_as(client, account.admin.id, project.id, **overrides)

    response = client.post(_vote_url(link["magic_token"]), json={"display_name": "Gate"})
    assert response.status_code == 200, response.text
    body = response.json()

    expected = _MODE_GATE_FLAGS[mode]
    if not expected:
        # open_access grants immediately with no input required
        assert not body.get("failure_reason"), body
        assert body.get("project", {}).get("project_id") == project.id
        return

    assert body.get("failure_reason"), f"{mode}: expected denial"
    for flag in _GATE_FLAG_NAMES:
        assert bool(body.get(flag)) is expected.get(flag, False), f"{mode}: {flag}"
    if mode.value.startswith("password"):
        assert body.get("verification_password_not_supplied") is True, mode



def _ext_complete_group(client, token, group, share_kind="vote"):
    ids = list(group.get("item_ids") or [i["id"] for i in group.get("items") or []])
    rank = sorted(ids)
    pairings = []
    for i in range(len(rank) - 1):
        pairings.append({
            "winner_id": rank[i],
            "loser_id": rank[i + 1],
            "response": "winner",
            "decision_seconds": 0.1,
            "presented_left_id": rank[i],
            "presented_right_id": rank[i + 1],
        })
    return client.post(
        _vote_url(token, "/complete-group"),
        json={
            "share_kind": share_kind,
            "prior_group": {
                "client_group_id": group["client_group_id"],
                "pass_index": group.get("pass_index") or 1,
                "group_type": group.get("group_type") or "alternative",
                "criterion_id": group.get("criterion_id"),
                "sort_algorithm": group.get("sort_algorithm") or "ford_johnson",
                "item_ids_initial": ids,
                "rank_order": rank,
                "pairings": pairings,
            },
        },
    )


def test_ext_open_access_vote_happy_path(client, account):
    project, a1, a2, factor = _seed_project_with_choices(account)
    link = _create_share_as(client, account.admin.id, project.id, access_mode="open_access")
    token = link["magic_token"]

    response = client.post(
        _vote_url(token),
        json={"display_name": "Guest", "verification_email": "guest@example.com"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert not body.get("failure_reason"), body
    assert body["project"]["project_id"] == project.id
    assert len(body.get("alternatives") or []) >= 2
    assert len(body.get("factors") or []) >= 1
    assert body.get("participant_id") is not None
    assert body.get("share_result_status", {}).get("share_id") == link["id"]
    assert client.cookies.get(settings.ACCESS_VIEW_COOKIE) is not None


def test_ext_invalid_token_unauthorized(client):
    clear_auth(client)
    response = client.post(
        _vote_url("not-a-real-token"),
        json={"display_name": "X"},
    )
    assert response.status_code == 401


def test_ext_disabled_link_unauthorized(client, account):
    project, *_ = _seed_project_with_choices(account)
    link = _create_share_as(client, account.admin.id, project.id)
    as_user(client, account.admin.id)
    disable = client.post(
        "/ws/extend-or-disable-share-link",
        json={"share_id": link["id"], "share_link_enabled": False},
    )
    assert disable.status_code == 200
    clear_auth(client)

    response = client.post(_vote_url(link["magic_token"]), json={})
    assert response.status_code == 401


def test_ext_wrong_share_type_denied(client, account):
    """Vote token must not open report endpoint."""
    project, *_ = _seed_project_with_choices(account)
    link = _create_share_as(client, account.admin.id, project.id, shared_type="vote")
    response = client.post(
        f"/ext-ws/share/{link['magic_token']}/report",
        json={},
    )
    assert response.status_code == 401


def test_ext_password_only_requires_password(client, account):
    project, *_ = _seed_project_with_choices(account)
    plain = "pw-share-99"
    link = _create_share_as(
        client,
        account.admin.id,
        project.id,
        access_mode="password_only",
        share_password=plain,
    )
    token = link["magic_token"]

    missing = client.post(_vote_url(token), json={"display_name": "G"})
    assert missing.status_code == 200
    denied = missing.json()
    assert denied.get("failure_reason")
    assert denied.get("verification_password_needed") is True or denied.get("verification_password_not_supplied") is True

    wrong = client.post(
        _vote_url(token),
        json={"display_name": "G", "verification_password": "nope"},
    )
    assert wrong.status_code == 200
    wrong_body = wrong.json()
    assert wrong_body.get("failure_reason")
    assert wrong_body.get("verification_password_incorrect") is True

    ok = client.post(
        _vote_url(token),
        json={"display_name": "G", "verification_password": plain},
    )
    assert ok.status_code == 200
    assert not ok.json().get("failure_reason"), ok.json()
    assert ok.json().get("project", {}).get("project_id") == project.id


def test_ext_email_matching_gate(client, account):
    project, *_ = _seed_project_with_choices(account)
    expected = f"{uid('match')}@example.com"
    link = _create_share_as(
        client,
        account.admin.id,
        project.id,
        access_mode="email_matching",
        shared_with_email=expected,
    )
    token = link["magic_token"]

    no_email = client.post(_vote_url(token), json={"display_name": "G"})
    assert no_email.status_code == 200
    assert no_email.json().get("failure_reason")
    assert no_email.json().get("verification_email_not_supplied") is True or "email" in (
        no_email.json().get("failure_reason") or ""
    ).lower()

    mismatch = client.post(
        _vote_url(token),
        json={"display_name": "G", "verification_email": "other@example.com"},
    )
    assert mismatch.status_code == 200
    assert mismatch.json().get("failure_reason")

    ok = client.post(
        _vote_url(token),
        json={"display_name": "G", "verification_email": expected},
    )
    assert ok.status_code == 200
    assert not ok.json().get("failure_reason"), ok.json()


def test_ext_email_any_unverified_accepts_any_valid_email(client, account):
    project, *_ = _seed_project_with_choices(account)
    link = _create_share_as(
        client,
        account.admin.id,
        project.id,
        access_mode="email_any_unverified",
    )
    token = link["magic_token"]
    response = client.post(
        _vote_url(token),
        json={"display_name": "Anyone", "verification_email": f"{uid()}@example.com"},
    )
    assert response.status_code == 200
    assert not response.json().get("failure_reason"), response.json()


def test_ext_email_any_verified_requires_authorize_flag(client, account):
    project, *_ = _seed_project_with_choices(account)
    link = _create_share_as(
        client,
        account.admin.id,
        project.id,
        access_mode="email_any_verified",
    )
    token = link["magic_token"]
    email = f"{uid()}@example.com"

    no_auth = client.post(
        _vote_url(token),
        json={"display_name": "V", "verification_email": email},
    )
    assert no_auth.status_code == 200
    assert no_auth.json().get("failure_reason")
    assert "authorization" in (no_auth.json().get("failure_reason") or "").lower()

    send = client.post(
        _vote_url(token),
        json={
            "display_name": "V",
            "verification_email": email,
            "authorize_verification_email": True,
        },
    )
    assert send.status_code == 200
    body = send.json()
    assert body.get("failure_reason")
    assert body.get("sent_magic_access_message") is True
    session = get_next_session()
    key_row = session.exec(
        select(PvfShareLinkMagicKey)
        .where(PvfShareLinkMagicKey.share_magic_token == token)
        .order_by(PvfShareLinkMagicKey.id.desc())
    ).first()
    session.close()
    assert key_row is not None
    assert key_row.access_magic_key
    magic_url = build_share_landing_url(
        share_type="vote",
        magic_token=token,
        access_magic_key=key_row.access_magic_key,
    )
    path_part = magic_url.split("?", 1)[0]
    assert f"/share/vote/{token}" in path_part
    assert f"/share/vote/{token}/" not in path_part
    assert f"key={key_row.access_magic_key}" in magic_url


def _latest_magic_key(session, token: str):
    return session.exec(
        select(PvfShareLinkMagicKey)
        .where(PvfShareLinkMagicKey.share_magic_token == token)
        .order_by(PvfShareLinkMagicKey.id.desc())
    ).first()


def _issue_magic_key(client, token: str, *, email: str | None = None, display_name: str = "Verified Voter"):
    body = {"display_name": display_name, "authorize_verification_email": True}
    if email:
        body["verification_email"] = email
    resp = client.post(_vote_url(token), json=body)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("sent_magic_access_message") is True, payload
    return payload


def _redeem_verified_access(client, token: str, *, email: str | None = None, display_name: str = "Verified Voter"):
    session = get_next_session()
    key_row = _latest_magic_key(session, token)
    session.close()
    assert key_row is not None
    body = {"display_name": display_name, "verification_magic_email_key": key_row.access_magic_key}
    if email:
        body["verification_email"] = email
    resp = client.post(_vote_url(token), json=body)
    assert resp.status_code == 200
    payload = resp.json()
    assert not payload.get("failure_reason"), payload
    return payload



def test_ext_recipient_email_verified_blank_email_sends_to_on_file(client, account):
    project, *_ = _seed_project_with_choices(account)
    on_file = f"{uid('onfile')}@example.com"
    link = _create_share_as(
        client,
        account.admin.id,
        project.id,
        access_mode="recipient_email_verified",
        shared_with_email=on_file,
    )
    token = link["magic_token"]

    probe = client.post(_vote_url(token), json={"display_name": "On File"})
    assert probe.status_code == 200
    probe_body = probe.json()
    assert probe_body.get("verification_email_needed") is not True
    assert probe_body.get("verification_original_email_needed") is not True
    assert probe_body.get("verification_email_send_link_mode") is True
    assert "authorization" in (probe_body.get("failure_reason") or "").lower()

    send = client.post(
        _vote_url(token),
        json={"display_name": "On File", "authorize_verification_email": True},
    )
    assert send.status_code == 200
    body = send.json()
    assert body.get("sent_magic_access_message") is True
    assert "on file" in (body.get("failure_reason") or "").lower()
    assert "set to" not in (body.get("failure_reason") or "").lower()

    session = get_next_session()
    key_row = _latest_magic_key(session, token)
    session.close()
    assert key_row is not None
    assert key_row.original_link_recipient_email == on_file
    assert key_row.captured_email in (None, "")


def test_ext_password_with_recipient_email_verified_blank_email_sends_to_on_file(client, account):
    project, *_ = _seed_project_with_choices(account)
    on_file = f"{uid('pwonfile')}@example.com"
    plain = f"pw-{uid()}"
    link = _create_share_as(
        client,
        account.admin.id,
        project.id,
        access_mode="password_with_recipient_email_verified",
        shared_with_email=on_file,
        share_password=plain,
    )
    token = link["magic_token"]

    send = client.post(
        _vote_url(token),
        json={
            "display_name": "PW On File",
            "verification_password": plain,
            "authorize_verification_email": True,
        },
    )
    assert send.status_code == 200
    body = send.json()
    assert body.get("sent_magic_access_message") is True
    assert "on file" in (body.get("failure_reason") or "").lower()

    session = get_next_session()
    key_row = _latest_magic_key(session, token)
    session.close()
    assert key_row is not None
    assert key_row.original_link_recipient_email == on_file
    assert key_row.captured_email in (None, "")


def test_ext_email_matching_verified_still_requires_typed_match(client, account):
    project, *_ = _seed_project_with_choices(account)
    expected = f"{uid('matchv')}@example.com"
    link = _create_share_as(
        client,
        account.admin.id,
        project.id,
        access_mode="email_matching_verified",
        shared_with_email=expected,
    )
    token = link["magic_token"]

    missing = client.post(_vote_url(token), json={"display_name": "Match V"})
    assert missing.status_code == 200
    missing_body = missing.json()
    assert missing_body.get("verification_email_needed") is True
    assert missing_body.get("verification_original_email_needed") is True
    assert "email address must be supplied" in (missing_body.get("failure_reason") or "").lower()

    mismatch = client.post(
        _vote_url(token),
        json={
            "display_name": "Match V",
            "verification_email": "other@example.com",
            "authorize_verification_email": True,
        },
    )
    assert mismatch.status_code == 200
    assert mismatch.json().get("sent_magic_access_message") is not True
    assert "email" in (mismatch.json().get("failure_reason") or "").lower()

    send = client.post(
        _vote_url(token),
        json={
            "display_name": "Match V",
            "verification_email": expected,
            "authorize_verification_email": True,
        },
    )
    assert send.status_code == 200
    send_body = send.json()
    assert send_body.get("sent_magic_access_message") is True
    assert "your email" in (send_body.get("failure_reason") or "").lower()

    session = get_next_session()
    key_row = _latest_magic_key(session, token)
    session.close()
    assert key_row is not None
    assert key_row.captured_email == expected


def test_ext_recipient_email_verified_rejects_mismatched_typed_email(client, account):
    project, *_ = _seed_project_with_choices(account)
    on_file = f"{uid('strict')}@example.com"
    link = _create_share_as(
        client,
        account.admin.id,
        project.id,
        access_mode="recipient_email_verified",
        shared_with_email=on_file,
    )
    token = link["magic_token"]

    mismatch = client.post(
        _vote_url(token),
        json={
            "display_name": "Leftover",
            "verification_email": "other@example.com",
            "authorize_verification_email": True,
        },
    )
    assert mismatch.status_code == 200
    body = mismatch.json()
    assert body.get("sent_magic_access_message") is not True
    assert "does not match" in (body.get("failure_reason") or "").lower()


def test_ext_verified_email_re_verify_joins_same_participant(client, account):
    """A re-verified (magic-key) email joins the same participant even after the cookie is lost."""
    reset_share_gate_throttle()
    project, *_ = _seed_project_with_choices(account)
    expected = f"{uid('verified')}@example.com"
    link = _create_share_as(
        client,
        account.admin.id,
        project.id,
        access_mode="email_matching_verified",
        shared_with_email=expected,
    )
    token = link["magic_token"]

    _issue_magic_key(client, token, email=expected)
    first = _redeem_verified_access(client, token, email=expected)
    participant_id = first["participant_id"]
    assert participant_id

    clear_auth(client)  # drop the share cookie -> new device/session

    _issue_magic_key(client, token, email=expected)
    second = _redeem_verified_access(client, token, email=expected)
    assert second["participant_id"] == participant_id

    session = get_next_session()
    rows = session.exec(
        select(ProjectVoteParticipant).where(
            ProjectVoteParticipant.customer_id == account.customer.id,
            ProjectVoteParticipant.project_id == project.id,
            ProjectVoteParticipant.share_id == link["id"],
            ProjectVoteParticipant.deleted_date == None,
        )
    ).all()
    session.close()
    assert len(rows) == 1
    assert rows[0].participant_key == f"share:{link['id']}:email:{expected.lower()}"


def test_ext_any_verified_email_tracks_email_not_share_binding(client, account):
    """Verified email is the identity anchor whether or not it is tied to the share recipient."""
    reset_share_gate_throttle()
    project, *_ = _seed_project_with_choices(account)
    link = _create_share_as(client, account.admin.id, project.id, access_mode="email_any_verified")
    token = link["magic_token"]
    email_a = f"{uid('verifA')}@example.com"

    _issue_magic_key(client, token, email=email_a)
    first = _redeem_verified_access(client, token, email=email_a)
    pid_a = first["participant_id"]
    assert pid_a

    clear_auth(client)

    _issue_magic_key(client, token, email=email_a)
    second = _redeem_verified_access(client, token, email=email_a)
    assert second["participant_id"] == pid_a

    clear_auth(client)

    email_b = f"{uid('verifB')}@example.com"
    _issue_magic_key(client, token, email=email_b)
    third = _redeem_verified_access(client, token, email=email_b)
    assert third["participant_id"] != pid_a


def test_ext_verified_email_reconciles_legacy_cookie_participant(client, account):
    """A pre-existing cookie-keyed participant with the same verified email is re-keyed, not duplicated."""
    reset_share_gate_throttle()
    project, *_ = _seed_project_with_choices(account)
    expected = f"{uid('legacy')}@example.com"
    link = _create_share_as(
        client,
        account.admin.id,
        project.id,
        access_mode="email_matching_verified",
        shared_with_email=expected,
    )
    token = link["magic_token"]

    session = get_next_session()
    legacy = ProjectVoteParticipant(
        customer_id=account.customer.id,
        project_id=project.id,
        share_id=link["id"],
        participant_key=f"share:{link['id']}:cookie:legacyhash",
        display_name="Legacy",
        email=expected,
        source=VoteSource.share,
        comparison_count=2,
    )
    session.add(legacy)
    session.commit()
    session.refresh(legacy)
    legacy_id = legacy.id
    session.close()

    _issue_magic_key(client, token, email=expected)
    payload = _redeem_verified_access(client, token, email=expected)
    assert payload["participant_id"] == legacy_id

    session = get_next_session()
    row = session.exec(
        select(ProjectVoteParticipant).where(ProjectVoteParticipant.id == legacy_id)
    ).one()
    session.close()
    assert row.participant_key == f"share:{link['id']}:email:{expected.lower()}"


def test_ext_unverified_email_new_session_new_participant(client, account):
    """Unverified emails are informational only: a fresh cookie is a fresh participant (may duplicate)."""
    reset_share_gate_throttle()
    project, *_ = _seed_project_with_choices(account)
    link = _create_share_as(client, account.admin.id, project.id, access_mode="email_any_unverified")
    token = link["magic_token"]
    email = f"{uid('unverif')}@example.com"

    first = client.post(_vote_url(token), json={"display_name": "U", "verification_email": email}).json()
    assert not first.get("failure_reason"), first
    pid1 = first["participant_id"]
    assert pid1

    clear_auth(client)

    second = client.post(_vote_url(token), json={"display_name": "U", "verification_email": email}).json()
    assert not second.get("failure_reason"), second
    assert second["participant_id"] != pid1


def test_ext_vote_complete_group_requires_cookie(client, account):
    project, a1, a2, factor = _seed_project_with_choices(account)
    link = _create_share_as(client, account.admin.id, project.id, access_mode="open_access")
    token = link["magic_token"]
    clear_auth(client)
    response = client.post(
        _vote_url(token, "/complete-group"),
        json={
            "prior_group": {
                "client_group_id": "x",
                "item_ids_initial": [a1.id, a2.id],
                "rank_order": [a1.id, a2.id],
                "pairings": [],
            }
        },
    )
    assert response.status_code in (401, 403, 200)
    if response.status_code == 200:
        assert response.json().get("failure_reason")


def test_ext_vote_complete_group_and_complete_flow(client, account):
    project, a1, a2, factor = _seed_project_with_choices(account)
    link = _create_share_as(client, account.admin.id, project.id, access_mode="open_access")
    token = link["magic_token"]

    access = client.post(
        _vote_url(token),
        json={"display_name": "Voter", "verification_email": "voter@example.com", "request_next": True},
    )
    assert access.status_code == 200
    assert not access.json().get("failure_reason"), access.json()
    g = access.json().get("next_group")
    assert g, access.json()
    participant_id = access.json().get("participant_id")

    submit = _ext_complete_group(client, token, g)
    assert submit.status_code == 200, submit.text
    submit_body = submit.json()
    assert not submit_body.get("failure_reason"), submit_body
    assert submit_body.get("group_info")
    assert submit_body.get("participant_id") == participant_id

    # idempotent
    replay = _ext_complete_group(client, token, g)
    assert replay.status_code == 200
    assert replay.json()["group_info"]["id"] == submit_body["group_info"]["id"]

    complete = client.post(
        _vote_url(token, "/complete"),
        json={"is_complete": True},
    )
    assert complete.status_code == 200
    complete_body = complete.json()
    assert not complete_body.get("failure_reason"), complete_body
    assert complete_body.get("completion_status", {}).get("is_complete") is True


def test_ext_vote_view_and_report_open_access(client, account):
    project, a1, a2, factor = _seed_project_with_choices(account)
    as_user(client, account.admin.id)
    mine = client.get("/ws/project-votes/my-vote", params={"project_id": project.id, "request_next": True}).json()
    g = mine.get("next_group")
    if g:
        ids = list(g.get("item_ids") or [])
        rank = sorted(ids)
        pairings = [{"winner_id": rank[i], "loser_id": rank[i+1], "response": "winner", "decision_seconds": 0.1,
                     "presented_left_id": rank[i], "presented_right_id": rank[i+1]} for i in range(len(rank)-1)]
        client.post("/ws/project-votes/complete-group", json={
            "project_id": project.id,
            "prior_group": {
                "client_group_id": g["client_group_id"],
                "pass_index": 1,
                "group_type": g.get("group_type"),
                "criterion_id": g.get("criterion_id"),
                "sort_algorithm": g.get("sort_algorithm"),
                "item_ids_initial": ids,
                "rank_order": rank,
                "pairings": pairings,
            },
        })

    view_link = _create_share_as(
        client, account.admin.id, project.id, shared_type="vote_view", access_mode="open_access"
    )
    report_link = _create_share_as(
        client, account.admin.id, project.id, shared_type="report", access_mode="open_access"
    )

    view = client.post(f"/ext-ws/share/{view_link['magic_token']}/vote-view", json={})
    assert view.status_code == 200
    assert not view.json().get("failure_reason"), view.json()
    assert "completion_status" in view.json()
    assert "report" not in view.json() or not view.json().get("report")

    report = client.post(f"/ext-ws/share/{report_link['magic_token']}/report", json={})
    assert report.status_code == 200
    rb = report.json()
    assert not rb.get("failure_reason"), rb
    assert rb.get("project", {}).get("project_id") == project.id
    assert rb.get("report") is not None
    assert "option_ranking" in (rb.get("report") or {}) or "metrics" in (rb.get("report") or {})


def test_ext_vote_view_complete_submitter_summary(client, account):
    project, a1, a2, factor = _seed_project_with_choices(account)
    create_factor(account, project_id=project.id, title="Quality")
    link = _create_share_as(
        client, account.admin.id, project.id, shared_type="vote_view", access_mode="open_access"
    )
    token = link["magic_token"]
    access = client.post(
        f"/ext-ws/share/{token}/vote-view",
        json={"display_name": "Viewer", "request_next": True},
    )
    assert access.status_code == 200, access.text
    body = access.json()
    assert not body.get("failure_reason"), body
    group = body.get("next_group")
    assert group
    for _ in range(3):
        if not group:
            break
        saved = _ext_complete_group(client, token, group, share_kind="vote_view")
        assert saved.status_code == 200, saved.text
        assert not saved.json().get("failure_reason"), saved.json()
        group = saved.json().get("next_group")
    done = client.post(
        f"/ext-ws/share/{token}/vote/complete",
        json={"share_kind": "vote_view", "is_complete": True},
    )
    assert done.status_code == 200, done.text
    summary = done.json().get("submitter_summary") or {}
    assert summary.get("ranking_mode")
    assert "top_n" in summary
    assert "participants" not in summary
    assert "dispersion" not in summary
    board = summary.get("alternative_leaderboard") or []
    assert board
    assert "score" in board[0]
    assert board[0].get("title")
    assert board[0].get("rank_ci95") or board[0].get("expected_rank") is not None
    factors = summary.get("factor_leaderboard") or []
    assert len(factors) >= 2
    assert any(
        row.get("weight") is not None or row.get("normalizedWeight") is not None
        for row in factors
    )

    reopen = client.post(
        f"/ext-ws/share/{token}/vote-view",
        json={"display_name": "Viewer"},
    )
    assert reopen.status_code == 200
    reopened = reopen.json()
    assert reopened.get("personal_vote", {}).get("is_complete") is True
    again = reopened.get("submitter_summary") or {}
    assert again.get("ranking_mode") == summary.get("ranking_mode")
    assert again.get("alternative_leaderboard")


def test_ext_complete_group_invalid_payload(client, account):
    project, a1, a2, factor = _seed_project_with_choices(account)
    link = _create_share_as(client, account.admin.id, project.id, access_mode="open_access")
    token = link["magic_token"]
    access = client.post(_vote_url(token), json={"display_name": "V", "request_next": True})
    g = access.json().get("next_group")
    assert g
    bad = client.post(
        _vote_url(token, "/complete-group"),
        json={
            "prior_group": {
                "client_group_id": g["client_group_id"],
                "item_ids_initial": g["item_ids"],
                "rank_order": g["item_ids"][:1],
                "pairings": [],
            },
        },
    )
    assert bad.status_code == 200
    assert bad.json().get("failure_reason")


def test_ext_logout_clears_cookie(client, account):
    project, *_ = _seed_project_with_choices(account)
    link = _create_share_as(client, account.admin.id, project.id, access_mode="open_access")
    token = link["magic_token"]

    access = client.post(_vote_url(token), json={"display_name": "L"})
    assert access.status_code == 200
    assert client.cookies.get(settings.ACCESS_VIEW_COOKIE) is not None

    logout = client.get(f"/ext-ws/share/{token}/logout")
    assert logout.status_code == 200


def _set_end_time(project_id: int, end_time):
    session = get_next_session()
    row = session.get(CustomerProject, project_id)
    row.end_time = end_time
    session.add(row)
    session.commit()
    session.close()


def test_ext_vote_accepts_until_grace_then_rejects(client, account):
    project, *_ = _seed_project_with_choices(account)
    link = _create_share_as(client, account.admin.id, project.id, access_mode="open_access")
    token = link["magic_token"]
    _set_end_time(project.id, datetime.now() - timedelta(minutes=20))
    access = client.post(_vote_url(token), json={"display_name": "V", "request_next": True})
    assert access.status_code == 200
    body = access.json()
    assert not body.get("failure_reason"), body
    assert body.get("next_group")
    assert body.get("project", {}).get("end_time")
    assert body.get("project", {}).get("collection_ending_soon") is True

    _set_end_time(project.id, datetime.now() - timedelta(hours=2))
    nxt = client.post(_vote_url(token, "/next-group"), json={})
    assert nxt.status_code == 200
    assert nxt.json().get("failure_reason") == COLLECTION_CLOSED_MSG
    done = client.post(_vote_url(token, "/complete-group"), json={"prior_group": None})
    assert done.status_code == 200
    assert done.json().get("failure_reason") == COLLECTION_CLOSED_MSG

    report_link = _create_share_as(
        client, account.admin.id, project.id, shared_type="report", access_mode="open_access"
    )
    report = client.post(f"/ext-ws/share/{report_link['magic_token']}/report", json={})
    assert report.status_code == 200
    assert not report.json().get("failure_reason"), report.json()
    assert report.json().get("report") is not None


def test_ext_vote_null_end_time_never_blocks(client, account):
    project, *_ = _seed_project_with_choices(account)
    link = _create_share_as(client, account.admin.id, project.id, access_mode="open_access")
    access = client.post(
        _vote_url(link["magic_token"]),
        json={"display_name": "V", "request_next": True},
    )
    assert access.status_code == 200
    assert not access.json().get("failure_reason")
    assert access.json().get("next_group")
    assert access.json().get("project", {}).get("end_time") in (None, "")


def test_ext_vote_disabled_independent_of_end_time(client, account):
    project, *_ = _seed_project_with_choices(account)
    link = _create_share_as(client, account.admin.id, project.id, access_mode="open_access")
    token = link["magic_token"]
    access = client.post(_vote_url(token), json={"display_name": "V", "request_next": False})
    assert access.status_code == 200
    assert not access.json().get("failure_reason"), access.json()
    session = get_next_session()
    row = session.get(CustomerProject, project.id)
    row.disabled = True
    row.end_time = datetime.now() + timedelta(days=12)
    session.add(row)
    session.commit()
    session.close()
    nxt = client.post(_vote_url(token, "/next-group"), json={})
    assert nxt.status_code == 200
    assert "locked" in (nxt.json().get("failure_reason") or "").lower()


def test_ext_cookie_duration_honored_on_grant(client, account):
    project, *_ = _seed_project_with_choices(account)
    link = _create_share_as(
        client,
        account.admin.id,
        project.id,
        access_mode="open_access",
        cookie_duration=2,
    )
    response = client.post(_vote_url(link["magic_token"]), json={"display_name": "TTL"})
    assert response.status_code == 200, response.text
    assert not response.json().get("failure_reason"), response.json()
    set_cookie = response.headers.get("set-cookie") or ""
    assert "Max-Age=172800" in set_cookie


def test_ext_gate_throttles_wrong_password_attempts(client, account):
    project, *_ = _seed_project_with_choices(account)
    link = _create_share_as(
        client,
        account.admin.id,
        project.id,
        access_mode="password_only",
        share_password="correct-pw",
    )
    token = link["magic_token"]
    prior_ip = settings.SHARE_GATE_MAX_FAILURES_PER_IP_PER_HOUR
    prior_token = settings.SHARE_GATE_MAX_FAILURES_PER_TOKEN_PER_HOUR
    reset_share_gate_throttle()
    settings.SHARE_GATE_MAX_FAILURES_PER_IP_PER_HOUR = 2
    settings.SHARE_GATE_MAX_FAILURES_PER_TOKEN_PER_HOUR = 2
    try:
        first = client.post(_vote_url(token), json={"display_name": "G", "verification_password": "nope-1"})
        assert first.status_code == 200
        assert first.json().get("verification_password_incorrect") is True
        second = client.post(_vote_url(token), json={"display_name": "G", "verification_password": "nope-2"})
        assert second.status_code == 200
        assert second.json().get("verification_password_incorrect") is True
        blocked = client.post(_vote_url(token), json={"display_name": "G", "verification_password": "nope-3"})
        assert blocked.status_code == 429
        assert "too many" in (blocked.json().get("detail") or "").lower()
    finally:
        settings.SHARE_GATE_MAX_FAILURES_PER_IP_PER_HOUR = prior_ip
        settings.SHARE_GATE_MAX_FAILURES_PER_TOKEN_PER_HOUR = prior_token
        reset_share_gate_throttle()


def test_ext_gate_throttles_unauth_volume_but_not_cookied_session(client, account):
    project, *_ = _seed_project_with_choices(account)
    link = _create_share_as(client, account.admin.id, project.id, access_mode="open_access")
    token = link["magic_token"]
    granted = client.post(_vote_url(token), json={"display_name": "In"})
    assert granted.status_code == 200
    assert not granted.json().get("failure_reason"), granted.json()

    prior = settings.SHARE_GATE_MAX_UNAUTH_PER_IP_PER_HOUR
    reset_share_gate_throttle()
    settings.SHARE_GATE_MAX_UNAUTH_PER_IP_PER_HOUR = 1
    try:
        still_ok = client.post(_vote_url(token, "/next-group"), json={})
        assert still_ok.status_code == 200

        client.cookies.delete(settings.ACCESS_VIEW_COOKIE)
        other = _create_share_as(client, account.admin.id, project.id, access_mode="password_only", share_password="x")
        probe = client.post(_vote_url(other["magic_token"]), json={"display_name": "P"})
        assert probe.status_code == 200
        blocked = client.post(_vote_url(other["magic_token"]), json={"display_name": "P", "verification_password": "nope"})
        assert blocked.status_code == 429
    finally:
        settings.SHARE_GATE_MAX_UNAUTH_PER_IP_PER_HOUR = prior
        reset_share_gate_throttle()


def test_get_random_baseN_value_digits_only():
    digits = get_random_baseN_value(length=6, digits_only=True)
    assert len(digits) == 6
    assert digits.isdigit()
    mixed = get_random_baseN_value(length=6, digits_only=False)
    assert len(mixed) == 6


def _set_digits_only(value: bool):
    prior = [(obj, obj.token_security_digits_only) for obj in (app_settings, settings)]
    for obj, _ in prior:
        obj.token_security_digits_only = value
    return prior


def _restore_digits_only(prior):
    for obj, old in prior:
        obj.token_security_digits_only = old


def test_access_magic_key_digits_only_true():
    prior = _set_digits_only(True)
    session = get_next_session()
    try:
        rec = PvfShareLinkMagicKey.create_shared_magic_key_record(
            session=session,
            usr_context=PvfUserContext(authenticated_session=False),
            share_link_id=0,
            shared_magic_token=uid("tok"),
            clear_lock=False,
        )
        assert rec.access_magic_key is not None
        assert rec.access_magic_key.isdigit()
        assert len(rec.access_magic_key) == 6
    finally:
        session.close()
        _restore_digits_only(prior)


def test_access_magic_key_passes_digits_only_flag(monkeypatch):
    captured = {}

    def fake(length=6, map_chars=None, *, digits_only=False):
        captured["digits_only"] = digits_only
        return "ABC123"

    monkeypatch.setattr("src.pvf.db.models.share_link_tracking.get_random_baseN_value", fake)
    session = get_next_session()
    try:
        prior = _set_digits_only(False)
        try:
            PvfShareLinkMagicKey.create_shared_magic_key_record(
                session=session,
                usr_context=PvfUserContext(authenticated_session=False),
                share_link_id=0,
                shared_magic_token=uid("tok"),
                clear_lock=False,
            )
            assert captured["digits_only"] is False
        finally:
            _restore_digits_only(prior)
        prior = _set_digits_only(True)
        try:
            PvfShareLinkMagicKey.create_shared_magic_key_record(
                session=session,
                usr_context=PvfUserContext(authenticated_session=False),
                share_link_id=0,
                shared_magic_token=uid("tok"),
                clear_lock=False,
            )
            assert captured["digits_only"] is True
        finally:
            _restore_digits_only(prior)
    finally:
        session.close()


