from src.api.repository import Repository


def test_migrations_are_idempotent(tmp_path):
    path = tmp_path / "app.db"
    Repository(path).migrate()
    Repository(path).migrate()

    tables = Repository(path).table_names()
    assert {
        "settings",
        "contacts",
        "conversations",
        "messages",
        "memories",
        "evaluations",
        "events",
        "processed_webhooks",
        "lab_sessions",
    }.issubset(tables)


def test_message_round_trip_preserves_relationships(tmp_path):
    repo = Repository(tmp_path / "app.db")
    repo.migrate()
    contact = repo.upsert_contact("5511999999999", "Mariana")
    conversation = repo.get_or_create_conversation(contact["id"], "whatsapp")
    repo.add_message(
        conversation["id"],
        "user",
        "qual o valor?",
        external_id="wamid.1",
    )

    messages = repo.list_messages(conversation["id"])
    assert messages[0]["text"] == "qual o valor?"
    assert messages[0]["external_id"] == "wamid.1"
    assert messages[0]["role"] == "user"


def test_settings_round_trip_uses_defaults(tmp_path):
    repo = Repository(tmp_path / "app.db")
    repo.migrate()

    original = repo.get_settings()
    assert original["agent_name"] == "Rafa"
    assert original["typo_probability"] == 0

    saved = repo.update_settings({"agent_name": "Nina", "max_questions": 2})
    assert saved["agent_name"] == "Nina"
    assert repo.get_settings()["max_questions"] == 2


def test_webhook_claim_is_atomic_and_idempotent(tmp_path):
    repo = Repository(tmp_path / "app.db")
    repo.migrate()

    assert repo.claim_webhook("wamid.same") is True
    assert repo.claim_webhook("wamid.same") is False


def test_memory_can_be_upserted_and_found(tmp_path):
    repo = Repository(tmp_path / "app.db")
    repo.migrate()
    contact = repo.upsert_contact("lab:session-1", "Teste")

    repo.upsert_memory(contact["id"], "budget", "5 mil", confidence=1.0)
    repo.upsert_memory(contact["id"], "budget", "6 mil", confidence=1.0)

    memory = repo.find_memory(contact["id"], "budget")
    assert memory["value"] == "6 mil"
    assert len(repo.list_memories(contact["id"])) == 1
