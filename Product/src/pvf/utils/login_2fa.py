from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from passlib.context import CryptContext
from pydantic import BaseModel
from sqlmodel import Session, desc, select

from ..config.pvf_config_settings import pvf_settings
from ..db.models.customer_user import PvfUserContext
from ..db.models.user_passwords import PvfUserPasswords
from .outbound_mail_queue import send_outbound_mail
from .pvf_base_internal_resources import PvfAuthRelatedOutboundEmailType, get_random_baseN_value

LOGIN_2FA_MODES = frozenset({"disabled", "sysadmins", "admins", "admins+optin", "all"})
LOGIN_2FA_CHALLENGE_MESSAGE = "A supplemental login code has been sent to your email"
LOGIN_2FA_ALREADY_SENT_MESSAGE = "A supplemental login code has already been sent to your email"

_PWD_CONTEXT = CryptContext(schemes=["pbkdf2_sha512"], deprecated="auto")

def normalize_login_2fa_mode(raw: str | None = None) -> str:
    value = (raw if raw is not None else pvf_settings.LOGIN_2FA_MODE) or ""
    value = str(value).strip().lower()
    return value if value in LOGIN_2FA_MODES else "disabled"


def _is_sysadmin(user: Any) -> bool:
    return (getattr(user, "system_user_mode", 0) or 0) >= 2


def _is_admin(user: Any) -> bool:
    return _is_sysadmin(user) or bool(getattr(user, "customer_admin", False))


def login_2fa_required(user: Any, customer: Any) -> bool:
    mode = normalize_login_2fa_mode()
    if mode == "disabled":
        return False
    if mode == "all":
        return True
    is_sys = _is_sysadmin(user)
    is_adm = _is_admin(user)
    if mode == "sysadmins":
        return is_sys
    if mode == "admins":
        return is_adm
    if mode == "admins+optin":
        return is_adm or bool(getattr(customer, "use_2fa", False)) or bool(getattr(user, "use_2fa", False))
    return False


def login_2fa_optional(user: Any, customer: Any) -> bool:
    if normalize_login_2fa_mode() != "admins+optin":
        return False
    return not bool(getattr(customer, "use_2fa", False))


def login_2fa_customer_controllable(user: Any) -> bool:
    if normalize_login_2fa_mode() != "admins+optin":
        return False
    return _is_admin(user)


def apply_2fa_client_settings(settings_obj: Any, user: Any, customer: Any) -> None:
    settings_obj.TWO_FACTOR_AUTH_ENABLED = login_2fa_required(user, customer)
    settings_obj.TWO_FACTOR_AUTH_OPTIONAL = login_2fa_optional(user, customer)
    settings_obj.TWO_FACTOR_AUTH_CUSTOMER_CONTROLLABLE = login_2fa_customer_controllable(user)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _latest_password_row(session: Session, user_id: int) -> PvfUserPasswords:
    return session.exec(
        select(PvfUserPasswords).where(PvfUserPasswords.user_id == user_id).order_by(desc(PvfUserPasswords.id)).limit(1)
    ).one()


def login_2fa_code_is_fresh(session: Session, user: Any) -> bool:
    row = _latest_password_row(session, user.id)
    if not row.last_2fa_hash or not row.last_2fa_issued_at:
        return False
    issued = _as_utc(row.last_2fa_issued_at)
    limit = timedelta(seconds=max(int(pvf_settings.LOGIN_2FA_RESEND_LIMIT_SECONDS), 0))
    return datetime.now(timezone.utc) - issued < limit


def issue_login_2fa_code(session: Session, user: Any) -> str:
    code = get_random_baseN_value(length=6, digits_only=pvf_settings.token_security_digits_only)
    row = _latest_password_row(session, user.id)
    row.last_2fa_hash = _PWD_CONTEXT.hash(code)
    row.last_2fa_issued_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    return code


def verify_login_2fa_code(session: Session, user: Any, code: str | None) -> bool:
    if not code:
        return False
    row = _latest_password_row(session, user.id)
    if not row.last_2fa_hash or not row.last_2fa_issued_at:
        return False
    issued = _as_utc(row.last_2fa_issued_at)
    minutes = max(int(pvf_settings.LOGIN_2FA_VALIDITY_MINUTES), 0)
    if issued + timedelta(minutes=minutes) < datetime.now(timezone.utc):
        return False
    if not _PWD_CONTEXT.verify(code, row.last_2fa_hash):
        return False
    clear_login_2fa_code(session, user, password_row=row)
    return True


def clear_login_2fa_code(session: Session, user: Any, *, password_row: PvfUserPasswords | None = None) -> None:
    row = password_row if password_row is not None else _latest_password_row(session, user.id)
    row.last_2fa_hash = None
    row.last_2fa_issued_at = None
    session.add(row)
    session.commit()


def send_login_2fa_email(session: Session, *, user: Any, remote_ip: str | None, url_path: str | None, code: str) -> str:
    proxy_user = user.model_copy()
    mail_context = PvfUserContext(
        limited_proxy=True,
        remote_ip=remote_ip,
        url_path=(url_path or "")[:150],
        sess_user=proxy_user,
    )
    mail_context.sess_user.customer_admin = False
    mail_context.sess_user.power_user_mode = 0
    mail_context.sess_user.system_user_mode = 0
    return send_outbound_mail(
        session=session,
        usr_context=mail_context,
        destination_email=user.email,
        email_type=PvfAuthRelatedOutboundEmailType.login_2fa,
        email_params=dict(
            login_2fa_code=code,
            valid_duration=pvf_settings.LOGIN_2FA_VALIDITY_MESSAGE,
        ),
    )
