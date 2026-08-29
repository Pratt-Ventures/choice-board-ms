import pytest

from src.config.config_settings import settings
from src.pvf.db.models.user_password_reset_tokens import PvfUserPasswordReset
from src.pvf.depends.api_session_dependencies import get_next_session
from src.tests.helpers.cleanup import cleanup_account
from src.tests.helpers.factories import AccountContext, create_account, uid


@pytest.mark.skipif(settings.is_prod(), reason="test helpers disabled in production")
def test_openapi_marks_test_helpers_not_in_production(client):
    spec = client.get("/session/docs.json").json()
    tags = {t["name"]: t.get("description", "") for t in spec.get("tags", [])}
    assert "test-helpers" in tags
    tag_desc = tags["test-helpers"].lower()
    assert "testing" in tag_desc or "test" in tag_desc
    assert "not" in tag_desc and "production" in tag_desc

    helper_ops = [
        op
        for path, methods in spec.get("paths", {}).items()
        if path.startswith("/ws/test-helper/")
        for op in methods.values()
        if "test-helpers" in op.get("tags", [])
    ]
    assert helper_ops
    for op in helper_ops:
        text = f"{op.get('summary', '')} {op.get('description', '')}".lower()
        assert "testing" in text or "test" in text
        assert "not" in text and "production" in text


@pytest.mark.skipif(settings.is_prod(), reason="test helpers disabled in production")
def test_get_user_activation_token(client, account):
    response = client.post(
        "/ws/test-helper/get-user-activation-token",
        json={"user_email": account.admin_email},
    )
    assert response.status_code == 200
    assert response.json().get("activation_token")


@pytest.mark.skipif(settings.is_prod(), reason="test helpers disabled in production")
def test_get_forgot_password_token(client, account):
    session = get_next_session()
    PvfUserPasswordReset.create_user_password_reset_system(
        session=session, email=account.admin_email, clear_lock=False
    )
    session.close()
    response = client.post(
        "/ws/test-helper/get-forgot-password-token",
        json={"user_email": account.admin_email},
    )
    assert response.status_code == 200
    assert response.json().get("forgot_password_token")


@pytest.mark.skipif(settings.is_prod(), reason="test helpers disabled in production")
def test_get_latest_share_magic_key(client, account):
    from src.pvf.db.models.share_link_tracking import PvfShareLinkMagicKey
    from src.tests.helpers.auth_client import as_user, clear_auth
    from src.tests.helpers.factories import create_project, uid
    from src.pvf.depends.api_session_dependencies import get_next_session
    from src.pvf.db.models.customer_user import PvfUserContext

    project = create_project(account)
    as_user(client, account.admin.id)
    created = client.post(
        "/ws/create-share-link",
        json={
            "shared_type": "vote",
            "shared_entity_db_id": project.id,
            "access_mode": "email_any_verified",
            "link_auto_send": False,
            "share_link_name": f"th-magic-{uid()}",
            "shared_with_email": f"{uid('rcpt')}@example.com",
        },
    )
    assert created.status_code == 200, created.text
    token = created.json()["link_info"]["magic_token"]
    share_id = created.json()["link_info"]["id"]
    clear_auth(client)

    missing = client.post(
        "/ws/test-helper/get-latest-share-magic-key",
        json={"magic_token": token},
    )
    assert missing.status_code == 404

    session = get_next_session()
    PvfShareLinkMagicKey.create_shared_magic_key_record(
        session=session,
        usr_context=PvfUserContext(authenticated_session=False),
        share_link_id=share_id,
        shared_magic_token=token,
        captured_email="guest@example.com",
        captured_display_name="Guest",
        clear_lock=False,
    )
    session.close()

    found = client.post(
        "/ws/test-helper/get-latest-share-magic-key",
        json={"magic_token": token},
    )
    assert found.status_code == 200, found.text
    body = found.json()
    assert body.get("access_magic_key")
    assert body.get("share_id") == share_id


@pytest.mark.skipif(settings.is_prod(), reason="test helpers disabled in production")
def test_create_activated_user(client):
    """Helper posts to localhost:8000 via httpx; skip when live server is not available."""
    email = f"{uid('th')}@example.com"
    password = uid("pw")
    try:
        response = client.post(
            "/ws/test-helper/create-activated-user",
            json={
                "customer_name": "Helper Co",
                "admin_name": "Helper Admin",
                "admin_email": email,
                "admin_phone": "555-9000",
                "admin_password": password,
            },
        )
    except Exception as exc:
        pytest.skip(f"create-activated-user requires live server on localhost:8000: {exc}")
    if response.status_code >= 500:
        pytest.skip("create-activated-user requires live server on localhost:8000")
    assert response.status_code == 200
    body = response.json()
    assert body.get("customer_id")

    from src.pvf.db.models.customer_user import PvfCustomer, PvfUser

    session = get_next_session()
    cust = PvfCustomer.get_customer_by_id_system(session=session, id=body["customer_id"], clear_lock=False)
    user = PvfUser.get_user_by_email_system(session=session, email=email, clear_lock=False)
    assert cust.customer_activated is True
    ctx = AccountContext(
        customer=cust,
        admin=user,
        admin_email=email,
        admin_password=password,
        tracked_user_ids=[user.id] if user else [],
    )
    session.close()
    cleanup_account(ctx)
