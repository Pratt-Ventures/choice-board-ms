def test_ui_status(client):
    from src.config.config_settings import settings

    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "API Available"
    assert "PowerChoice" in body.get("service", "")
    assert body.get("version") == settings.VERSION


def test_api_status(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body.get("status") == "API Available"


def test_alive(client):
    response = client.get("/alive")
    assert response.status_code == 200
