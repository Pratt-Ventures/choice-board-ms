from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from sqlmodel import select

from src.config.config_settings import settings
from src.pvf.config.pvf_config_settings import pvf_settings
from src.pvf.db.models.application_event_log import PvfApplicationLogEvent
from src.pvf.db.models.customer_user import PvfCustomer, PvfUser
from src.pvf.db.models.user_passwords import PvfUserPasswords
from src.pvf.depends.api_session_dependencies import get_next_session
from src.pvf.utils.login_2fa import (
    issue_login_2fa_code,
    login_2fa_customer_controllable,
    login_2fa_optional,
    login_2fa_required,
    normalize_login_2fa_mode,
)
from src.pvf.utils.pvf_base_internal_resources import get_random_baseN_value
from src.tests.helpers.auth_client import as_user, clear_auth, login
from src.tests.helpers.factories import uid


@contextmanager
def _mode(mode: str):
    prior = [(obj, obj.LOGIN_2FA_MODE) for obj in (settings, pvf_settings)]
    for obj, _ in prior:
        obj.LOGIN_2FA_MODE = mode
    try:
        yield
    finally:
        for obj, value in prior:
            obj.LOGIN_2FA_MODE = value


@contextmanager
def _digits_only(value: bool):
    prior = [(obj, obj.token_security_digits_only) for obj in (settings, pvf_settings)]
    for obj, _ in prior:
        obj.token_security_digits_only = value
    try:
        yield
    finally:
        for obj, old in prior:
            obj.token_security_digits_only = old


def _set_user_use_2fa(user_id: int, value: bool) -> None:
    session = get_next_session()
    user = PvfUser.get_user_by_id_system(session=session, id=user_id, clear_lock=False)
    user.use_2fa = value
    session.add(user)
    session.commit()
    session.close()


def _set_customer_use_2fa(customer_id: int, value: bool) -> None:
    session = get_next_session()
    customer = PvfCustomer.get_customer_by_id_system(session=session, id=customer_id, clear_lock=False)
    customer.use_2fa = value
    customer.update_customer_system(session=session, clear_lock=True)


def _password_row(user_id: int) -> PvfUserPasswords:
    session = get_next_session()
    row = session.exec(
        select(PvfUserPasswords).where(PvfUserPasswords.user_id == user_id).order_by(PvfUserPasswords.id.desc())
    ).first()
    session.close()
    return row


def _backdate_2fa(user_id: int, *, minutes: int) -> None:
    session = get_next_session()
    row = session.exec(
        select(PvfUserPasswords).where(PvfUserPasswords.user_id == user_id).order_by(PvfUserPasswords.id.desc())
    ).first()
    row.last_2fa_issued_at = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    session.add(row)
    session.commit()
    session.close()


def test_normalize_login_2fa_mode():
    assert normalize_login_2fa_mode("Admins+OptIn") == "admins+optin"
    assert normalize_login_2fa_mode("all") == "all"
    assert normalize_login_2fa_mode("nope") == "disabled"
    assert normalize_login_2fa_mode("") == "disabled"


def test_login_2fa_required_matrix():
    class U:
        def __init__(self, admin=False, sys=0, use=False):
            self.customer_admin = admin
            self.system_user_mode = sys
            self.use_2fa = use

    class C:
        def __init__(self, use=False):
            self.use_2fa = use

    member, admin, sysadmin = U(), U(admin=True), U(sys=2)
    with _mode("disabled"):
        assert not login_2fa_required(sysadmin, C())
    with _mode("sysadmins"):
        assert login_2fa_required(sysadmin, C())
        assert not login_2fa_required(admin, C())
        assert not login_2fa_required(member, C())
    with _mode("admins"):
        assert login_2fa_required(admin, C())
        assert login_2fa_required(sysadmin, C())
        assert not login_2fa_required(member, C())
    with _mode("admins+optin"):
        assert login_2fa_required(admin, C())
        assert not login_2fa_required(member, C())
        assert login_2fa_required(member, C(use=True))
        assert login_2fa_required(U(use=True), C())
        assert login_2fa_optional(member, C())
        assert not login_2fa_optional(member, C(use=True))
        assert login_2fa_customer_controllable(admin)
        assert not login_2fa_customer_controllable(member)
    with _mode("all"):
        assert login_2fa_required(member, C())
        assert not login_2fa_optional(member, C())


def test_login_disabled_unchanged(client, account):
    with _mode("disabled"):
        response = login(client, account.admin_email, account.admin_password)
    assert response.status_code == 200
    assert response.cookies.get("access_token")
    assert not response.json().get("two_factor_required")


def test_all_mode_challenges_member(client, account, monkeypatch):
    monkeypatch.setattr("src.pvf.utils.login_2fa.get_random_baseN_value", lambda length=6, map_chars=None, *, digits_only=False: "ABC123")
    with _mode("all"):
        response = login(client, account.member_email, account.member_password)
    assert response.status_code == 200
    body = response.json()
    assert body.get("two_factor_required") is True
    assert response.cookies.get("access_token")
    row = _password_row(account.member.id)
    assert row.last_2fa_hash
    assert "ABC123" not in (row.last_2fa_hash or "")
    assert row.last_2fa_issued_at is not None


def test_challenge_then_code_completes_login(client, account, monkeypatch):
    monkeypatch.setattr("src.pvf.utils.login_2fa.get_random_baseN_value", lambda length=6, map_chars=None, *, digits_only=False: "XYZ789")
    with _mode("admins"):
        challenge = login(client, account.admin_email, account.admin_password)
        assert challenge.status_code == 200
        assert challenge.json().get("two_factor_required") is True
        clear_auth(client)
        denied = client.post(
            "/auth-ws/login",
            json={"email": account.admin_email, "password": account.admin_password, "two_factor_code": "nope"},
        )
        assert denied.status_code == 403
        assert denied.json().get("detail", "").startswith("PvfLogin failed")
        clear_auth(client)
        ok = client.post(
            "/auth-ws/login",
            json={"email": account.admin_email, "password": account.admin_password, "two_factor_code": "XYZ789"},
        )
    assert ok.status_code == 200
    assert ok.json().get("user_id") == account.admin.id
    assert ok.cookies.get("access_token")
    row = _password_row(account.admin.id)
    assert row.last_2fa_hash is None
    clear_auth(client)
    with _mode("admins"):
        reused = client.post(
            "/auth-ws/login",
            json={"email": account.admin_email, "password": account.admin_password, "two_factor_code": "XYZ789"},
        )
    assert reused.status_code == 403


def test_login_and_get_context_challenge(client, account, monkeypatch):
    monkeypatch.setattr("src.pvf.utils.login_2fa.get_random_baseN_value", lambda length=6, map_chars=None, *, digits_only=False: "CTX001")
    clear_auth(client)
    with _mode("admins"):
        response = client.post(
            "/auth-ws/login-and-get-context",
            json={"email": account.admin_email, "password": account.admin_password},
        )
        assert response.status_code == 200
        assert response.json().get("two_factor_required") is True
        assert not response.json().get("user_id")
        done = client.post(
            "/auth-ws/login-and-get-context",
            json={"email": account.admin_email, "password": account.admin_password, "two_factor_code": "CTX001"},
        )
    assert done.status_code == 200
    assert done.json().get("email") == account.admin_email
    assert done.json().get("settings", {}).get("TWO_FACTOR_AUTH_ENABLED") is True


def test_resend_keeps_hash_within_window(client, account, monkeypatch):
    codes = iter(["FIRST1", "SECOND"])
    monkeypatch.setattr("src.pvf.utils.login_2fa.get_random_baseN_value", lambda length=6, map_chars=None, *, digits_only=False: next(codes))
    with _mode("all"):
        first = login(client, account.member_email, account.member_password)
        hash_one = _password_row(account.member.id).last_2fa_hash
        second = login(client, account.member_email, account.member_password)
    assert first.json().get("two_factor_required")
    assert second.json().get("two_factor_required")
    assert _password_row(account.member.id).last_2fa_hash == hash_one


def test_expired_code_rejected(client, account, monkeypatch):
    monkeypatch.setattr("src.pvf.utils.login_2fa.get_random_baseN_value", lambda length=6, map_chars=None, *, digits_only=False: "OLDCOD")
    with _mode("all"):
        login(client, account.member_email, account.member_password)
        _backdate_2fa(account.member.id, minutes=30)
        clear_auth(client)
        response = client.post(
            "/auth-ws/login",
            json={"email": account.member_email, "password": account.member_password, "two_factor_code": "OLDCOD"},
        )
    assert response.status_code == 403


def test_sysadmins_mode_skips_member(client, account, sysadmin_account):
    with _mode("sysadmins"):
        member = login(client, account.member_email, account.member_password)
        admin = login(client, account.admin_email, account.admin_password)
        sysadmin = login(client, sysadmin_account.admin_email, sysadmin_account.admin_password)
    assert member.status_code == 200 and not member.json().get("two_factor_required")
    assert admin.status_code == 200 and not admin.json().get("two_factor_required")
    assert sysadmin.status_code == 200 and sysadmin.json().get("two_factor_required") is True


def test_admins_optin_member_flag(client, account, monkeypatch):
    monkeypatch.setattr("src.pvf.utils.login_2fa.get_random_baseN_value", lambda length=6, map_chars=None, *, digits_only=False: "OPTIN1")
    with _mode("admins+optin"):
        off = login(client, account.member_email, account.member_password)
        assert off.status_code == 200
        assert not off.json().get("two_factor_required")
        _set_user_use_2fa(account.member.id, True)
        on = login(client, account.member_email, account.member_password)
    assert on.status_code == 200
    assert on.json().get("two_factor_required") is True


def test_unknown_mode_is_disabled(client, account):
    with _mode("not-a-mode"):
        response = login(client, account.admin_email, account.admin_password)
    assert response.status_code == 200
    assert not response.json().get("two_factor_required")


def test_set_user_use_2fa_self_when_optional(client, account):
    with _mode("admins+optin"):
        as_user(client, account.member.id)
        on = client.post("/ws/user/set-use-2fa", json={"enabled": True})
        assert on.status_code == 200
        body = on.json()
        assert body.get("prior") is False
        assert body.get("new") is True
        assert body.get("use_2fa") is True
        off = client.post("/ws/user/set-use-2fa", json={"enabled": False})
        assert off.json().get("new") is False


def test_set_user_use_2fa_denied_when_not_optional(client, account):
    with _mode("admins"):
        as_user(client, account.member.id)
        response = client.post("/ws/user/set-use-2fa", json={"enabled": True})
    assert response.status_code == 200
    assert response.json().get("failure_reason")


def test_set_customer_use_2fa_admin_and_log(client, account):
    with _mode("admins+optin"):
        as_user(client, account.admin.id)
        response = client.post("/ws/customer/set-use-2fa", json={"enabled": True})
    assert response.status_code == 200
    body = response.json()
    assert not body.get("failure_reason")
    assert body.get("prior") is False
    assert body.get("new") is True
    session = get_next_session()
    row = session.exec(
        select(PvfApplicationLogEvent)
        .where(PvfApplicationLogEvent.customer_id == account.customer.id)
        .where(PvfApplicationLogEvent.log_message == "PvfCustomer 2FA setting changed")
        .order_by(PvfApplicationLogEvent.id.desc())
    ).first()
    session.close()
    assert row is not None
    assert row.details_json["prior"] is False
    assert row.details_json["new"] is True


def test_set_customer_use_2fa_non_admin_denied(client, account):
    with _mode("admins+optin"):
        as_user(client, account.member.id)
        response = client.post("/ws/customer/set-use-2fa", json={"enabled": True})
    assert response.status_code == 200
    assert response.json().get("failure_reason")


def test_set_use_2fa_unauthenticated(client):
    clear_auth(client)
    user_resp = client.post("/ws/user/set-use-2fa", json={"enabled": True})
    cust_resp = client.post("/ws/customer/set-use-2fa", json={"enabled": True})
    assert user_resp.status_code in (401, 403)
    assert cust_resp.status_code in (401, 403)


def test_user_update_cannot_write_use_2fa(client, account):
    as_user(client, account.member.id)
    client.post(
        "/ws/user-update",
        json={"id": account.member.id, "name": account.member.name, "email": account.member_email, "use_2fa": True},
    )
    session = get_next_session()
    user = PvfUser.get_user_by_id_system(session=session, id=account.member.id, clear_lock=True)
    assert user.use_2fa is False


def test_context_2fa_flags_computed(client, account):
    with _mode("disabled"):
        as_user(client, account.admin.id)
        response = client.post("/ws/core/get-user-customer-context", json={"include_account_status": False})
    settings_body = response.json().get("settings") or {}
    assert settings_body.get("TWO_FACTOR_AUTH_ENABLED") is False
    assert settings_body.get("TWO_FACTOR_AUTH_OPTIONAL") is False
    assert settings_body.get("TWO_FACTOR_AUTH_CUSTOMER_CONTROLLABLE") is False
    with _mode("admins+optin"):
        as_user(client, account.admin.id)
        admin_ctx = client.post("/ws/core/get-user-customer-context", json={"include_account_status": False})
        as_user(client, account.member.id)
        member_ctx = client.post("/ws/core/get-user-customer-context", json={"include_account_status": False})
    admin_s = admin_ctx.json().get("settings") or {}
    member_s = member_ctx.json().get("settings") or {}
    assert admin_s.get("TWO_FACTOR_AUTH_ENABLED") is True
    assert admin_s.get("TWO_FACTOR_AUTH_OPTIONAL") is True
    assert admin_s.get("TWO_FACTOR_AUTH_CUSTOMER_CONTROLLABLE") is True
    assert member_s.get("TWO_FACTOR_AUTH_ENABLED") is False
    assert member_s.get("TWO_FACTOR_AUTH_OPTIONAL") is True
    assert member_s.get("TWO_FACTOR_AUTH_CUSTOMER_CONTROLLABLE") is False
    assert "use_2fa" in (admin_ctx.json().get("user_record") or {})
    assert "use_2fa" in (admin_ctx.json().get("customer_record") or {})


def test_context_ignores_stored_2fa_flag_override(client, account):
    session = get_next_session()
    customer = PvfCustomer.get_customer_by_id_system(session=session, id=account.customer.id, clear_lock=False)
    customer.client_settings = '{"TWO_FACTOR_AUTH_ENABLED": true, "TWO_FACTOR_AUTH_OPTIONAL": true}'
    customer.update_customer_system(session=session, clear_lock=True)
    with _mode("disabled"):
        as_user(client, account.member.id)
        response = client.post("/ws/core/get-user-customer-context", json={"include_account_status": False})
    flags = response.json().get("settings") or {}
    assert flags.get("TWO_FACTOR_AUTH_ENABLED") is False
    assert flags.get("TWO_FACTOR_AUTH_OPTIONAL") is False


def test_password_change_clears_2fa_hash(client, account, monkeypatch):
    from src.pvf.db.models.user_password_reset_tokens import PvfUserPasswordReset

    monkeypatch.setattr("src.pvf.utils.login_2fa.get_random_baseN_value", lambda length=6, map_chars=None, *, digits_only=False: "CLR001")
    with _mode("all"):
        login(client, account.admin_email, account.admin_password)
    assert _password_row(account.admin.id).last_2fa_hash
    session = get_next_session()
    token_row = PvfUserPasswordReset.create_user_password_reset_system(
        session=session, email=account.admin_email, clear_lock=False
    )
    token = token_row.token
    session.close()
    new_pw = uid("newpw")
    client.post(
        "/auth-ws/change-password-via-token",
        json={"email": account.admin_email, "token": token, "new_password": new_pw},
    )
    assert _password_row(account.admin.id).last_2fa_hash is None
    account.admin_password = new_pw


def test_get_random_baseN_value_digits_only():
    digits = get_random_baseN_value(length=6, digits_only=True)
    assert len(digits) == 6
    assert digits.isdigit()
    mixed = get_random_baseN_value(length=6, digits_only=False)
    assert len(mixed) == 6


def test_issue_login_2fa_code_digits_only_true(account):
    session = get_next_session()
    try:
        with _digits_only(True):
            code = issue_login_2fa_code(session, account.member)
        assert len(code) == 6
        assert code.isdigit()
    finally:
        session.close()


def test_issue_login_2fa_code_passes_digits_only_flag(account, monkeypatch):
    captured = {}

    def fake(length=6, map_chars=None, *, digits_only=False):
        captured["digits_only"] = digits_only
        return "ABC123"

    monkeypatch.setattr("src.pvf.utils.login_2fa.get_random_baseN_value", fake)
    session = get_next_session()
    try:
        with _digits_only(False):
            issue_login_2fa_code(session, account.member)
        assert captured["digits_only"] is False
        with _digits_only(True):
            issue_login_2fa_code(session, account.member)
        assert captured["digits_only"] is True
    finally:
        session.close()
