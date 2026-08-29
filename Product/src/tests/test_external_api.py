import json

from src.tests.helpers.auth_client import clear_auth, signed_api_headers


def _post_signed(client, path: str, body: dict, rq_key: str, secret: str):
    payload = json.dumps(body)
    headers = signed_api_headers(payload, rq_key, secret)
    return client.post(path, content=payload.encode("utf-8"), headers=headers)


def test_api_status(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    assert response.json().get("status") == "API Available"


def test_api_check_valid_signature(client, full_account):
    body = {"ping": "pong"}
    response = _post_signed(
        client,
        "/api/api-check",
        body,
        full_account.api_rq_key,
        full_account.api_shared_secret,
    )
    assert response.status_code == 200
    assert response.json() is True


def test_api_check_missing_headers(client):
    response = client.post("/api/api-check", json={"ping": "pong"})
    assert response.status_code == 401


def test_api_check_bad_signature(client, full_account):
    body = {"ping": "pong"}
    payload = json.dumps(body)
    headers = signed_api_headers(payload, full_account.api_rq_key, "wrong-secret")
    response = client.post("/api/api-check", content=payload.encode(), headers=headers)
    assert response.status_code == 401


def test_get_defined_project_records(client, full_account):
    body = {"page_index": 0, "page_size": 100}
    response = _post_signed(
        client,
        "/api/get-defined-project-records",
        body,
        full_account.api_rq_key,
        full_account.api_shared_secret,
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("failure_reason", "") in ("", None)
    assert data.get("customer_project_info_list")


def test_get_defined_project_records_with_tag_filter(client, full_account):
    body = {"project_tag": full_account.project_tag, "page_index": 0, "page_size": 100}
    response = _post_signed(
        client,
        "/api/get-defined-project-records",
        body,
        full_account.api_rq_key,
        full_account.api_shared_secret,
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("failure_reason", "") in ("", None)


def test_external_api_unauthenticated(client):
    clear_auth(client)
    response = client.post(
        "/api/get-defined-project-records",
        json={"page_index": 0, "page_size": 10},
    )
    assert response.status_code == 401
