def test_webhook_verification(client, monkeypatch):
    monkeypatch.setenv("VERIFY_TOKEN", "secret")
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "secret",
            "hub.challenge": "42",
        },
    )
    assert response.status_code == 200
    assert response.json() == 42


def test_duplicate_message_is_acknowledged_once(client, monkeypatch):
    calls = []

    def record_enqueue(background_tasks, message, services):
        calls.append(message.external_id)

    monkeypatch.setattr(
        "src.api.routes_webhook.enqueue_message",
        record_enqueue,
    )
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.same",
                                    "from": "5511999999999",
                                    "type": "text",
                                    "text": {"body": "oi"},
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }

    assert client.post("/webhook", json=payload).status_code == 200
    assert client.post("/webhook", json=payload).status_code == 200
    assert calls == ["wamid.same"]


def test_non_text_messages_are_ignored(client):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.image",
                                    "from": "5511999999999",
                                    "type": "image",
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }
    response = client.post("/webhook", json=payload)
    assert response.status_code == 200
    assert response.json()["accepted"] == 0
