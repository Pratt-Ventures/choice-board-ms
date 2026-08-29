from src.tests.helpers.auth_client import as_user, clear_auth
from src.tests.helpers.factories import create_api_key, create_project


def test_create_api_key_as_admin(client, account):
    create_project(account)
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/api-keys/create-api-access-configuration",
        json={
            "application_tag": account.project_tag,
            "description": "pytest",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)
    info = body.get("api_configuration_info") or {}
    if info.get("authentication_key_id"):
        account.tracked_api_key_ids.append(info["authentication_key_id"])


def test_create_api_key_non_admin_fails(client, account):
    create_project(account)
    as_user(client, account.member.id)
    response = client.post(
        "/ws/api-keys/create-api-access-configuration",
        json={
            "application_tag": account.project_tag,
            "description": "pytest",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason")


def test_get_api_access_configurations(client, account):
    create_project(account)
    create_api_key(account)
    as_user(client, account.admin.id)
    response = client.post("/ws/api-keys/get-api-access-configurations", json={})
    assert response.status_code == 200
    body = response.json()
    assert body.get("api_configuration_list") is not None


def test_get_api_keys_unauthenticated(client):
    clear_auth(client)
    response = client.post("/ws/api-keys/get-api-access-configurations", json={})
    assert response.status_code in (401, 403)


def test_modify_api_key_as_admin(client, account):
    create_project(account)
    key_id, _, _ = create_api_key(account)
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/api-keys/modify-api-access-configuration",
        json={
            "authentication_key_id": key_id,
            "description": "modified",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)


def test_modify_api_key_non_admin_fails(client, account):
    create_project(account)
    key_id, _, _ = create_api_key(account)
    as_user(client, account.member.id)
    response = client.post(
        "/ws/api-keys/modify-api-access-configuration",
        json={"authentication_key_id": key_id, "description": "nope"},
    )
    assert response.status_code == 200
    assert response.json().get("failure_reason")


def test_modify_foreign_api_key_fails(client, account, other_account):
    create_project(other_account)
    key_id, _, _ = create_api_key(other_account)
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/api-keys/modify-api-access-configuration",
        json={"authentication_key_id": key_id, "description": "steal"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason")


def test_remove_api_key_as_admin(client, account):
    create_project(account)
    key_id, _, _ = create_api_key(account)
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/api-keys/remove-api-access-configuration",
        json={"authentication_key_id": key_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)
    if key_id in account.tracked_api_key_ids:
        account.tracked_api_key_ids.remove(key_id)


def test_remove_api_key_non_admin_fails(client, account):
    create_project(account)
    key_id, _, _ = create_api_key(account)
    as_user(client, account.member.id)
    response = client.post(
        "/ws/api-keys/remove-api-access-configuration",
        json={"authentication_key_id": key_id},
    )
    assert response.status_code == 200
    assert response.json().get("failure_reason")
