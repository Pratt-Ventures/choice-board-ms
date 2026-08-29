from unittest.mock import AsyncMock

import os
import pytest
from fastapi.testclient import TestClient

# The ENABLE_SHARE_* flags only control which access modes the share dialog offers in
# the UI (via context settings); they never gate API or security behavior. Force every
# one on BEFORE config_settings/client_settings are imported so all share modes are
# exercisable (and context settings uniform) under pytest, regardless of the env.
_ENABLE_SHARE_ENV_VARS = (
    "ENABLE_SHARE_OPEN_ACCESS",
    "ENABLE_SHARE_EMAIL_ANY_UNVERIFIED",
    "ENABLE_SHARE_EMAIL_ANY_VERIFIED",
    "ENABLE_SHARE_EMAIL_MATCHING",
    "ENABLE_SHARE_EMAIL_MATCHING_VERIFIED",
    "ENABLE_SHARE_RECIPIENT_EMAIL_VERIFIED",
    "ENABLE_SHARE_PASSWORD_ONLY",
    "ENABLE_SHARE_PASSWORD_WITH_EMAIL_ANY_UNVERIFIED",
    "ENABLE_SHARE_PASSWORD_WITH_EMAIL_ANY_VERIFIED",
    "ENABLE_SHARE_PASSWORD_WITH_EMAIL_MATCHING",
    "ENABLE_SHARE_PASSWORD_WITH_EMAIL_MATCHING_VERIFIED",
    "ENABLE_SHARE_PASSWORD_WITH_RECIPIENT_EMAIL_VERIFIED",
)
for _var in _ENABLE_SHARE_ENV_VARS:
    os.environ[_var] = "1"

from src.config.config_settings import settings  # noqa: E402
from src.pvf.config.pvf_config_settings import pvf_settings  # noqa: E402

# pvf internals read pvf_settings; the application settings instance mirrors pvf fields.
# Set both so overrides are visible everywhere.
for _settings_obj in (settings, pvf_settings):
    _settings_obj.PYTEST_ACTIVE = True
    _settings_obj.SG_KEY = ""
    _settings_obj.SG_API_ENDPOINT = ""
    _settings_obj.MAX_EMAILS_PER_DEST_PER_HOUR = 1000
    _settings_obj.MAX_EMAILS_PER_DEST_PER_24_HOURS = 1000
    _settings_obj.MAX_EMAILS_PER_REMOTE_IP_PER_HOUR_VERIFIED = 1000
    _settings_obj.MAX_EMAILS_PER_REMOTE_IP_PER_HOUR = 1000
    _settings_obj.SHARE_GATE_MAX_UNAUTH_PER_IP_PER_HOUR = 10000
    _settings_obj.SHARE_GATE_MAX_FAILURES_PER_IP_PER_HOUR = 10000
    _settings_obj.SHARE_GATE_MAX_FAILURES_PER_TOKEN_PER_HOUR = 10000

from src.pvf.pvf_app_runner import app  # noqa: E402
from src.tests.helpers.cleanup import cleanup_account  # noqa: E402
from src.tests.helpers.factories import (  # noqa: E402
    create_account,
    create_api_key,
    create_project,
)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def account():
    ctx = create_account(system_user_mode=0, with_member=True)
    yield ctx
    cleanup_account(ctx)


@pytest.fixture
def sysadmin_account():
    ctx = create_account(system_user_mode=2, power_user_mode=2, with_member=True)
    yield ctx
    cleanup_account(ctx)


@pytest.fixture
def other_account():
    ctx = create_account(system_user_mode=0, with_member=False)
    yield ctx
    cleanup_account(ctx)


@pytest.fixture
def full_account():
    """PvfCustomer + admin + member + project + API key."""
    ctx = create_account(system_user_mode=2, power_user_mode=2, with_member=True)
    create_project(ctx)
    create_api_key(ctx)
    yield ctx
    cleanup_account(ctx)


@pytest.fixture(autouse=True)
def sendgrid_mock(mocker):
    return mocker.patch(
        "src.pvf.utils.outbound_mail_queue.request_sendgrid_delivery",
        new_callable=AsyncMock,
        return_value="",
    )
