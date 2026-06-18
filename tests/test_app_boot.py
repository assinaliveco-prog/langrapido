from fastapi.testclient import TestClient


def test_panel_and_health_are_available(client: TestClient):
    panel = client.get("/painel")
    health = client.get("/api/health")

    assert panel.status_code == 200
    assert "LangRápido" in panel.text
    assert health.status_code == 200
    assert health.json()["status"] in {"ready", "degraded"}


def test_panel_assets_are_served(client: TestClient):
    css = client.get("/static/panel.css")
    javascript = client.get("/static/panel.js")

    assert css.status_code == 200
    assert "--canvas" in css.text
    assert javascript.status_code == 200
    assert "const api" in javascript.text
