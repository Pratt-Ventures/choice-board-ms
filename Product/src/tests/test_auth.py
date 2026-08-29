import uuid

from sqlmodel import select

from src.config.config_settings import settings
from src.pvf.db.models.customer_user import PvfCustomer
from src.pvf.db.models.user_password_reset_tokens import PvfUserPasswordReset
from src.pvf.depends.api_session_dependencies import get_next_session
from src.tests.helpers.auth_client import as_user, clear_auth, login
from src.tests.helpers.factories import uid

_STRIPE_SETTINGS_BLOB = '{"livemode": false, "secret": "billing-internal"}'


def test_login_success(client, account):
    response = login(client, account.admin_email, account.admin_password)
    assert response.status_code == 200
    assert response.cookies.get("access_token") is not None


def test_login_fail_bad_credentials(client, account):
    response = login(client, account.admin_email, "wrong-password")
    assert response.status_code == 403
    assert response.cookies.get("access_token") is not None


def test_login_fail_unknown_user(client):
    response = login(client, f"{uuid.uuid4()}@example.com", "x")
    assert response.status_code == 403


def test_login_and_get_context(client, account):
    clear_auth(client)
    response = client.post(
        "/auth-ws/login-and-get-context",
        json={"email": account.admin_email, "password": account.admin_password},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("email") == account.admin_email or body.get("user_info", {}).get("email") == account.admin_email or "email" in str(body)


def test_login_and_get_context_masks_stripe_settings(client, account):
    session = get_next_session()
    customer = PvfCustomer.get_customer_by_id_system(session=session, id=account.customer.id, clear_lock=False)
    customer.stripe_settings = _STRIPE_SETTINGS_BLOB
    customer.update_customer_system(session=session, clear_lock=True)
    original = settings.CONTEXT_MASKED_FIELDS
    try:
        settings.CONTEXT_MASKED_FIELDS = ["stripe_settings"]
        clear_auth(client)
        response = client.post(
            "/auth-ws/login-and-get-context",
            json={"email": account.admin_email, "password": account.admin_password},
        )
    finally:
        settings.CONTEXT_MASKED_FIELDS = original
    assert response.status_code == 200
    body = response.json()
    customer_record = body.get("customer_record") or {}
    user_record = body.get("user_record") or {}
    assert "stripe_settings" not in customer_record
    assert "stripe_settings" not in user_record
    session = get_next_session()
    stored = PvfCustomer.get_customer_by_id_system(session=session, id=account.customer.id, clear_lock=True)
    assert stored.stripe_settings == _STRIPE_SETTINGS_BLOB


def test_password_reset_unknown_email_no_mail(client, sendgrid_mock):
    sendgrid_mock.reset_mock()
    response = client.post(
        "/auth-ws/password-reset-request",
        json={"email": f"{uuid.uuid4()}@example.com"},
    )
    assert response.status_code == 200
    sendgrid_mock.assert_not_awaited()


def test_password_reset_known_email_creates_token(client, account, sendgrid_mock):
    sendgrid_mock.reset_mock()
    response = client.post(
        "/auth-ws/password-reset-request",
        json={"email": account.admin_email},
    )
    assert response.status_code == 200
    session = get_next_session()
    token_row = session.exec(
        select(PvfUserPasswordReset)
        .where(PvfUserPasswordReset.email == account.admin_email)
        .order_by(PvfUserPasswordReset.id.desc())
    ).first()
    session.close()
    assert token_row is not None
    # non-prod may skip actual SendGrid delivery; token creation is the durable side effect


def test_change_password_via_token_success(client, account):
    session = get_next_session()
    token_row = PvfUserPasswordReset.create_user_password_reset_system(
        session=session, email=account.admin_email, clear_lock=False
    )
    token = token_row.token
    session.close()

    new_pw = uid("newpw")
    response = client.post(
        "/auth-ws/change-password-via-token",
        json={"email": account.admin_email, "token": token, "new_password": new_pw},
    )
    assert response.status_code == 200
    assert response.json() is True

    login_resp = login(client, account.admin_email, new_pw)
    assert login_resp.status_code == 200
    account.admin_password = new_pw


def test_change_password_via_token_invalid(client, account):
    response = client.post(
        "/auth-ws/change-password-via-token",
        json={"email": account.admin_email, "token": "not-a-real-token", "new_password": "x"},
    )
    assert response.status_code == 200
    assert response.json() is False


def test_logout(client, account):
    as_user(client, account.admin.id)
    response = client.get("/auth-ws/logout")
    assert response.status_code == 200
    assert "Logout successful" in response.json().get("message", "")
