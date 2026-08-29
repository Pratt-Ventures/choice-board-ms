from src.config.config_settings import settings
from src.pvf.config.pvf_config_settings import parse_csv_name_list
from src.pvf.db.models.customer_user import PvfCustomer
from src.pvf.depends.api_session_dependencies import get_next_session
from src.tests.helpers.auth_client import as_user, clear_auth

_STRIPE_SETTINGS_BLOB = '{"livemode": false, "secret": "billing-internal"}'


def _persist_customer_stripe_settings(customer_id: int, blob: str) -> None:
    session = get_next_session()
    customer = PvfCustomer.get_customer_by_id_system(session=session, id=customer_id, clear_lock=False)
    customer.stripe_settings = blob
    customer.update_customer_system(session=session, clear_lock=True)


def _read_customer_stripe_settings(customer_id: int) -> str | None:
    session = get_next_session()
    customer = PvfCustomer.get_customer_by_id_system(session=session, id=customer_id, clear_lock=True)
    return customer.stripe_settings


def test_parse_csv_name_list_variants():
    assert parse_csv_name_list("stripe_settings, client_settings") == ["stripe_settings", "client_settings"]
    assert parse_csv_name_list("") == []
    assert parse_csv_name_list(None) == []
    assert parse_csv_name_list("   ") == []
    assert parse_csv_name_list("  a, , b ,") == ["a", "b"]
    assert parse_csv_name_list([" stripe_settings ", "", "x"]) == ["stripe_settings", "x"]


def test_context_masked_fields_validator_default_and_empty():
    assert settings.parse_context_masked_fields(None) == ["stripe_settings"]
    assert settings.parse_context_masked_fields("") == []
    assert settings.parse_context_masked_fields("stripe_settings, client_settings") == [
        "stripe_settings",
        "client_settings",
    ]
    assert isinstance(settings.CONTEXT_MASKED_FIELDS, list)


def test_get_user_customer_context(client, account):
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/core/get-user-customer-context",
        json={"include_account_status": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("email") == account.admin_email
    assert body.get("customer_id") == account.customer.id


def test_get_user_customer_context_unauthenticated(client):
    clear_auth(client)
    response = client.post(
        "/ws/core/get-user-customer-context",
        json={"include_account_status": True},
    )
    assert response.status_code in (401, 403)


def test_user_all_account_users(client, account):
    as_user(client, account.admin.id)
    response = client.get("/ws/user-all-account-users")
    assert response.status_code == 200
    body = response.json()
    emails = [u.get("email") for u in (body.get("user_info_list") or [])]
    assert account.admin_email in emails
    if account.member_email:
        assert account.member_email in emails


def test_user_all_account_users_unauthenticated(client):
    clear_auth(client)
    response = client.get("/ws/user-all-account-users")
    assert response.status_code in (401, 403)


def test_user_all_account_admins(client, account):
    as_user(client, account.member.id)
    response = client.get("/ws/user-all-account-admins")
    assert response.status_code == 200
    body = response.json()
    emails = [u.get("email") for u in (body.get("user_info_list") or [])]
    assert account.admin_email in emails
    if account.member_email:
        assert account.member_email not in emails


def test_user_all_account_admins_unauthenticated(client):
    clear_auth(client)
    response = client.get("/ws/user-all-account-admins")
    assert response.status_code in (401, 403)


def test_context_openapi_settings_uses_app_client_settings_schema(client):
    spec = client.get("/session/docs.json").json()
    view = spec["components"]["schemas"]["UserCustomerContextView"]
    settings_schema = view["properties"]["settings"]
    refs = [settings_schema.get("$ref")]
    refs.extend(item.get("$ref") for item in settings_schema.get("anyOf", []))
    assert "#/components/schemas/ClientSettings" in refs
    client_settings = spec["components"]["schemas"]["ClientSettings"]
    assert "coherence_method" in client_settings["properties"]
    assert "enable_share_open_access" in client_settings["properties"]
    vote = spec["components"]["schemas"]["CustomerVoteSettingsResult"]
    vote_refs = [vote["properties"]["settings"].get("$ref")]
    vote_refs.extend(item.get("$ref") for item in vote["properties"]["settings"].get("anyOf", []))
    assert "#/components/schemas/ClientSettings" in vote_refs


def test_context_includes_vote_settings_defaults(client, account):
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/core/get-user-customer-context",
        json={"include_account_status": False},
    )
    assert response.status_code == 200
    settings = response.json().get("settings") or {}
    assert settings.get("coherence_method") == "spearman"
    assert "question_group_size" not in settings or settings.get("question_group_size") is None


def test_context_settings_include_all_share_mode_flags(client, account):
    """The settings payload carries an enable flag per PvfShareAccessCheckMode (UI visibility contract)."""
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/core/get-user-customer-context",
        json={"include_account_status": False},
    )
    assert response.status_code == 200
    settings = response.json().get("settings") or {}
    for flag in (
        "enable_share_open_access",
        "enable_share_email_any_unverified",
        "enable_share_email_any_verified",
        "enable_share_email_matching",
        "enable_share_email_matching_verified",
        "enable_share_recipient_email_verified",
        "enable_share_password_only",
        "enable_share_password_with_email_any_unverified",
        "enable_share_password_with_email_any_verified",
        "enable_share_password_with_email_matching",
        "enable_share_password_with_email_matching_verified",
        "enable_share_password_with_recipient_email_verified",
        "enable_user_communication",
        "ai_features_enabled",
        "ai_providers_configured",
    ):
        assert flag in settings, flag
        assert isinstance(settings[flag], bool), flag


def test_update_customer_vote_settings_admin(client, account):
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/core/update-customer-vote-settings",
        json={"coherence_method": "kendall"},
    )
    assert response.status_code == 200
    body = response.json()
    assert not body.get("failure_reason"), body
    settings = body.get("settings") or {}
    assert settings.get("coherence_method") == "kendall"

    bad_coh = client.post(
        "/ws/core/update-customer-vote-settings",
        json={"coherence_method": "not-a-method"},
    )
    assert bad_coh.status_code == 200
    assert bad_coh.json()["settings"]["coherence_method"] == "spearman"


def test_update_customer_vote_settings_non_admin_denied(client, account):
    as_user(client, account.member.id)
    response = client.post(
        "/ws/core/update-customer-vote-settings",
        json={"coherence_method": "kendall"},
    )
    assert response.status_code == 200
    assert response.json().get("failure_reason")


def test_context_masks_stripe_settings_and_leaves_db_intact(client, account):
    _persist_customer_stripe_settings(account.customer.id, _STRIPE_SETTINGS_BLOB)
    original = settings.CONTEXT_MASKED_FIELDS
    try:
        settings.CONTEXT_MASKED_FIELDS = ["stripe_settings"]
        as_user(client, account.admin.id)
        response = client.post(
            "/ws/core/get-user-customer-context",
            json={"include_account_status": True},
        )
    finally:
        settings.CONTEXT_MASKED_FIELDS = original
    assert response.status_code == 200
    body = response.json()
    customer_record = body.get("customer_record") or {}
    user_record = body.get("user_record") or {}
    assert "stripe_settings" not in customer_record
    assert "stripe_settings" not in user_record
    assert "stripe_customer_id" in body
    assert _read_customer_stripe_settings(account.customer.id) == _STRIPE_SETTINGS_BLOB


def test_context_includes_stripe_settings_when_mask_empty(client, account):
    _persist_customer_stripe_settings(account.customer.id, _STRIPE_SETTINGS_BLOB)
    original = settings.CONTEXT_MASKED_FIELDS
    try:
        settings.CONTEXT_MASKED_FIELDS = []
        as_user(client, account.admin.id)
        response = client.post(
            "/ws/core/get-user-customer-context",
            json={"include_account_status": True},
        )
    finally:
        settings.CONTEXT_MASKED_FIELDS = original
    assert response.status_code == 200
    customer_record = response.json().get("customer_record") or {}
    assert customer_record.get("stripe_settings") == _STRIPE_SETTINGS_BLOB


def test_version_sync_client_server_static():
    """Guard against stale `client X → server Y` banners that survive reload.

    The SPA's baked appVersion (static_client/index.html) must match
    src/config/config_settings.py VERSION and client/package.json version.
    See fix for client 0.7.88 → server 0.7.89 mismatch that survived Reload.
    """
    import json
    import re
    from pathlib import Path

    ws_root = Path(__file__).resolve().parents[2]
    # server version
    cfg_text = (ws_root / "src/config/config_settings.py").read_text()
    m = re.search(r'VERSION\s*:\s*str\s*=\s*"([^"]+)"', cfg_text)
    assert m, "could not parse VERSION from src/config/config_settings.py"
    server_version = m.group(1).strip()

    # client package.json version
    pkg = json.loads((ws_root / "client/package.json").read_text())
    client_version = str(pkg.get("version") or "").strip()
    assert client_version, "client/package.json version missing"
    assert client_version == server_version, (
        f"version drift: client/package.json {client_version} != server {server_version} — "
        "bump both together and regenerate static_client via ./scripts/nuxt/update_static_client.sh"
    )

    # nuxt fallback must match (otherwise a missing NUXT_PUBLIC_APP_VERSION would bake stale version)
    nuxt_text = (ws_root / "client/nuxt.config.ts").read_text()
    m2 = re.search(r"let _pkgVersion\s*=\s*'([^']+)'", nuxt_text)
    if m2:
        fallback = m2.group(1).strip()
        assert fallback == client_version, (
            f"nuxt fallback {fallback} != client/package.json {client_version} — keep _pkgVersion in sync"
        )

    # baked static_client version (what the browser actually loads)
    idx = ws_root / "static_client/index.html"
    if idx.is_file():
        html = idx.read_text()
        m3 = re.search(r'appVersion:"([^"]+)"', html)
        if m3:
            baked = m3.group(1).strip()
            assert baked == server_version, (
                f"baked static_client appVersion {baked} != server {server_version} — "
                "run ./scripts/nuxt/update_static_client.sh to rebuild"
            )
