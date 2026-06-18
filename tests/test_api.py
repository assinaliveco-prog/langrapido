def test_settings_round_trip(client):
    original = client.get("/api/settings")
    assert original.status_code == 200
    payload = original.json()
    payload["agent_name"] = "Nina"

    saved = client.put("/api/settings", json=payload)

    assert saved.status_code == 200
    assert saved.json()["agent_name"] == "Nina"
    assert client.get("/api/settings").json()["agent_name"] == "Nina"


def test_health_never_returns_secrets(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "super-secret")
    monkeypatch.setenv("WHATSAPP_TOKEN", "also-secret")

    payload = client.get("/api/health").text

    assert "super-secret" not in payload
    assert "also-secret" not in payload


def test_lab_session_does_not_require_whatsapp(client):
    created = client.post("/api/lab/sessions", json={"name": "Teste"})

    assert created.status_code == 201
    assert created.json()["name"] == "Teste"
    assert created.json()["channel"] == "lab"


def test_lab_message_without_ai_returns_503_and_keeps_input(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    session = client.post("/api/lab/sessions", json={"name": "Sem IA"}).json()

    response = client.post(
        f"/api/lab/sessions/{session['id']}/messages",
        json={"text": "qual o valor?"},
    )

    assert response.status_code == 503
    messages = client.get(
        f"/api/conversations/{session['conversation_id']}/messages"
    ).json()
    assert messages[-1]["text"] == "qual o valor?"


def test_dashboard_uses_real_counts(client):
    client.post("/api/lab/sessions", json={"name": "Contato real"})

    dashboard = client.get("/api/dashboard")

    assert dashboard.status_code == 200
    assert dashboard.json()["contacts"] == 1
    assert dashboard.json()["open_conversations"] == 1


def test_events_endpoint_returns_recorded_failures(client):
    services = client.app.state.services
    services.repository.add_event("test", "warning", "evento de teste")

    response = client.get("/api/events")

    assert response.status_code == 200
    assert response.json()[0]["message"] == "evento de teste"
