"""Ambient email_params injected by send_outbound_mail."""
import asyncio
from datetime import datetime, timezone

from sqlmodel import select

from src.pvf.db.models.customer_user import PvfUserContext
from src.pvf.db.models.email_activity_log import PvfEmailActivityLog
from src.pvf.depends.api_session_dependencies import get_next_session
from src.tests.helpers.factories import uid
from src.pvf.utils.pvf_base_internal_resources import PvfAuthRelatedOutboundEmailType as OutboundEmailType
from src.pvf.utils.outbound_mail_queue import send_outbound_mail

from src.config.config_settings import settings

def _expected_app_base_url() -> str:
    return settings.APPLICATION_BASE_URL.rstrip("/")


def _expected_app_login_url() -> str:
    return f"{_expected_app_base_url()}/{settings.APP_LOGIN_PATH.lstrip('/')}"


def _latest_params(dest: str) -> dict:
    session = get_next_session()
    row = session.exec(
        select(PvfEmailActivityLog)
        .where(PvfEmailActivityLog.email_address == dest.lower())
        .order_by(PvfEmailActivityLog.id.desc())
    ).first()
    session.close()
    assert row is not None
    return row.email_params_json or {}


def _send(usr_context: PvfUserContext, dest: str, email_params: dict) -> None:
    session = get_next_session()
    # send_outbound_mail is now sync (with internal async handling); handle both sync and async for compat
    result = send_outbound_mail(
        session=session,
        usr_context=usr_context,
        email_type=OutboundEmailType.new_user_welcome,
        destination_email=dest,
        email_params=email_params,
    )
    # If it returned a coroutine (old async version), run it
    if hasattr(result, "__await__") or hasattr(result, "send"):
        try:
            import asyncio as _asyncio
            _asyncio.run(result)  # type: ignore
        except Exception:
            pass


def test_ambient_theme_and_session_fields_authenticated(account):
    dest = f"{uid('amb')}@mailinator.com"
    usr_context = account.user_context()
    usr_context.remote_ip = "203.0.113.10"
    _send(usr_context, dest, {})
    params = _latest_params(dest)
    assert params["brand_name"] == settings.EMAIL_BRAND_NAME
    assert params["support_email"] == settings.EMAIL_SUPPORT_EMAIL
    assert params["year"] == datetime.now(timezone.utc).year
    assert params["app_base_url"] == _expected_app_base_url()
    assert params["app_login_url"] == _expected_app_login_url()
    assert params["user_name"] == account.admin.name
    assert params["user_email"] == account.admin.email
    assert params["user_phone"] == account.admin.phone
    assert params["customer_name"] == account.customer.customer_name
    assert params["customer_email"] == account.customer.customer_email
    assert params["customer_phone"] == account.customer.customer_phone


def test_ambient_theme_keys_without_session_user():
    dest = f"{uid('amb')}@mailinator.com"
    usr_context = PvfUserContext(remote_ip="203.0.113.11")
    _send(usr_context, dest, {})
    params = _latest_params(dest)
    assert params["user_name"] == ""
    assert params["user_email"] == ""
    assert params["user_phone"] == ""
    assert params["customer_name"] == ""
    assert params["customer_email"] == ""
    assert params["customer_phone"] == ""
    assert params["brand_name"] == settings.EMAIL_BRAND_NAME
    assert params["support_email"] == settings.EMAIL_SUPPORT_EMAIL
    assert params["year"] == datetime.now(timezone.utc).year
    assert params["app_base_url"] == _expected_app_base_url()
    assert params["app_login_url"] == _expected_app_login_url()


def test_caller_supplied_theme_keys_not_overwritten(account):
    dest = f"{uid('amb')}@mailinator.com"
    usr_context = account.user_context()
    _send(
        usr_context,
        dest,
        {
            "brand_name": "Caller Brand",
            "app_login_url": "https://example.test/signin",
            "user_email": "preset@example.com",
        },
    )
    params = _latest_params(dest)
    assert params["brand_name"] == "Caller Brand"
    assert params["app_login_url"] == "https://example.test/signin"
    assert params["user_email"] == "preset@example.com"
    assert params["year"] == datetime.now(timezone.utc).year
    assert params["app_base_url"] == _expected_app_base_url()
    assert params["support_email"] == settings.EMAIL_SUPPORT_EMAIL
