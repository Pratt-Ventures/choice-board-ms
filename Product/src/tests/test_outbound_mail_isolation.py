"""Outbound mail isolation: string template names, dict parse, discovery, undefined logs."""
import asyncio
from unittest.mock import patch

from sqlmodel import select

from src.pvf.db.models.customer_user import PvfUserContext
from src.pvf.db.models.email_activity_log import PvfEmailActivityLog
from src.pvf.depends.api_session_dependencies import get_next_session
from src.pvf.utils.pvf_base_internal_resources import PvfAuthRelatedOutboundEmailType as OutboundEmailType
from src.pvf.utils.outbound_mail_queue import normalize_email_type, send_outbound_mail
from src.pvf.utils.outbound_mail_sendgrid import (
    get_valid_sendgrid_template_names,
    request_sendgrid_delivery,
)
from src.pvf.utils.outbound_mail_smtp_jinja import (
    get_valid_jinja_template_names,
    request_smtp_jinja_delivery,
    send_template_email,
)

from src.config.config_settings import settings
from src.pvf.config.pvf_config_settings import parse_sendgrid_template_ids, pvf_settings

from src.tests.helpers.factories import uid

_EXPECTED_JINJA_NAMES = {
    "password_reset",
    "customer_activation_self",
    "customer_activation_admin",
    "customer_activation_admin_activated",
    "new_user_welcome",
    "share_project_vote",
    "share_project_vote_view",
    "share_project_report",
    "resending_invitation",
    "magic_access_key",
    "login_2fa",
}


def test_parse_sendgrid_template_ids_colon_comma():
    parsed = parse_sendgrid_template_ids(
        "password_reset:d-abc, share_project_vote:d-def, ,blank_id:, skipped"
    )
    assert parsed == {
        "password_reset": "d-abc",
        "share_project_vote": "d-def",
        "blank_id": "",
    }
    assert parse_sendgrid_template_ids(None) == {}
    assert parse_sendgrid_template_ids("   ") == {}
    assert parse_sendgrid_template_ids("code_only_no_colon") == {}


def test_normalize_email_type_accepts_enum_or_string():
    assert normalize_email_type(OutboundEmailType.new_user_welcome) == "new_user_welcome"
    assert normalize_email_type("share_project_vote") == "share_project_vote"


def test_jinja_valid_names_from_files_exclude_theme():
    names = get_valid_jinja_template_names()
    assert set(names) == _EXPECTED_JINJA_NAMES
    assert "email_visual_theme" not in names
    assert "not_set" not in names


def test_sendgrid_valid_names_from_dict():
    original = pvf_settings.SENDGRID_TEMPLATE_IDS
    try:
        pvf_settings.SENDGRID_TEMPLATE_IDS = {
            "password_reset": "d-abc",
            "share_project_vote": "d-def",
            "blank": "",
        }
        assert get_valid_sendgrid_template_names() == ["password_reset", "share_project_vote"]
    finally:
        pvf_settings.SENDGRID_TEMPLATE_IDS = original


def test_sendgrid_undefined_template_logs_and_does_not_send():
    usr_context = PvfUserContext(remote_ip="203.0.113.50")
    original = pvf_settings.SENDGRID_TEMPLATE_IDS
    try:
        pvf_settings.SENDGRID_TEMPLATE_IDS = {"password_reset": "d-abc"}
        with patch("src.pvf.utils.outbound_mail_sendgrid.log_event", return_value=99) as mock_log:
            with patch("src.pvf.utils.outbound_mail_sendgrid.httpx.AsyncClient") as mock_client:
                result = asyncio.run(
                    request_sendgrid_delivery(
                        session=None,
                        usr_context=usr_context,
                        destination_email="nobody@example.com",
                        email_type="not_a_real_template",
                        email_params={},
                    )
                )
        assert "Unsupported template requested not_a_real_template" in result
        assert mock_log.call_args.kwargs["severity"] >= 4
        mock_client.assert_not_called()
    finally:
        pvf_settings.SENDGRID_TEMPLATE_IDS = original


def test_jinja_undefined_template_logs_and_does_not_send():
    usr_context = PvfUserContext(remote_ip="203.0.113.51")
    with patch("src.pvf.utils.outbound_mail_smtp_jinja.log_event", return_value=77) as mock_log:
        with patch("src.pvf.utils.outbound_mail_smtp_jinja.send_template_email") as mock_send:
            result = asyncio.run(
                request_smtp_jinja_delivery(
                    session=None,
                    usr_context=usr_context,
                    destination_email="nobody@example.com",
                    email_type="not_a_real_template",
                    email_params={},
                )
            )
    assert "Unsupported template requested not_a_real_template" in result
    assert mock_log.call_args.kwargs["severity"] >= 4
    mock_send.assert_not_called()


def test_send_template_email_undefined_logs_without_raising():
    usr_context = PvfUserContext(remote_ip="203.0.113.52")
    with patch("src.pvf.utils.outbound_mail_smtp_jinja.log_event", return_value=55) as mock_log:
        with patch("src.pvf.utils.outbound_mail_smtp_jinja.emails.html") as mock_html:
            send_template_email(
                usr_context=usr_context,
                to="nobody@example.com",
                template_name="email_visual_theme",
                parameters={},
            )
    assert mock_log.call_args.kwargs["severity"] >= 4
    mock_html.assert_not_called()


def test_activity_log_stores_email_type_string(account):
    dest = f"{uid('iso')}@mailinator.com"
    usr_context = account.user_context()
    session = get_next_session()
    _res = send_outbound_mail(
        session=session,
        usr_context=usr_context,
        email_type=OutboundEmailType.new_user_welcome,
        destination_email=dest,
        email_params={},
    )
    if hasattr(_res, "__await__"):
        import asyncio as _asyncio
        _asyncio.run(_res)  # type: ignore
    session = get_next_session()
    row = session.exec(
        select(PvfEmailActivityLog)
        .where(PvfEmailActivityLog.email_address == dest.lower())
        .order_by(PvfEmailActivityLog.id.desc())
    ).first()
    session.close()
    assert row is not None
    assert isinstance(row.email_type, str)
    assert row.email_type == "new_user_welcome"


def test_send_outbound_mail_accepts_string_type(account):
    dest = f"{uid('iso')}@mailinator.com"
    usr_context = account.user_context()
    session = get_next_session()
    _res2 = send_outbound_mail(
        session=session,
        usr_context=usr_context,
        email_type="new_user_welcome",
        destination_email=dest,
        email_params={},
    )
    if hasattr(_res2, "__await__"):
        import asyncio as _asyncio
        _asyncio.run(_res2)  # type: ignore
    session = get_next_session()
    row = session.exec(
        select(PvfEmailActivityLog)
        .where(PvfEmailActivityLog.email_address == dest.lower())
        .order_by(PvfEmailActivityLog.id.desc())
    ).first()
    session.close()
    assert row is not None
    assert row.email_type == "new_user_welcome"
