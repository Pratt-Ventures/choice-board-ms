from src.tests.helpers.auth_client import as_user, clear_auth
from src.tests.helpers.factories import create_project


def test_get_dashboard_information(client, account):
    create_project(account)
    as_user(client, account.admin.id)
    response = client.post(
        "/ws/core/get-dashboard-information",
        json={
            "recent_limit": 10,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("failure_reason", "") in ("", None)
    assert "summary" in body
    assert "projects_summary" in body or "applications_summary" in body
    assert "api_keys_summary" in body
    assert "account_status" in body
    summary = body["summary"]
    assert summary.get("project_count", summary.get("application_count", 0)) >= 1
    assert "api_key_count" in summary
    assert "team_user_count" in summary


def test_get_dashboard_information_unauthenticated(client):
    clear_auth(client)
    response = client.post("/ws/core/get-dashboard-information", json={})
    assert response.status_code in (401, 403)
