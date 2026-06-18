import pytest

from src.api.repository import Repository
from src.services.conversation import ConversationEngine


class FakeGenerator:
    async def respond(self, context):
        assert context["messages"][-1]["text"] == "meu orçamento é 5 mil"
        assert context["style"]["max_questions"] == 1
        return {
            "draft": "entendi, com 5 mil dá pra trabalhar algumas opções",
            "evaluation": {"approved": True, "issues": []},
            "messages": ["entendi, com 5 mil dá pra trabalhar algumas opções"],
        }


class FailingGenerator:
    async def respond(self, context):
        raise RuntimeError("provider unavailable")


@pytest.mark.asyncio
async def test_engine_persists_input_output_and_memory(tmp_path):
    repo = Repository(tmp_path / "app.db")
    repo.migrate()
    session = repo.create_lab_session("Sessão 1")
    engine = ConversationEngine(repo, FakeGenerator())

    result = await engine.handle_lab_message(
        session["id"],
        "meu orçamento é 5 mil",
    )

    assert result.messages[0].startswith("entendi")
    memory = repo.find_memory(session["contact_id"], "budget")
    assert memory["value"] == "5 mil"
    assert len(repo.list_messages(session["conversation_id"])) == 2


@pytest.mark.asyncio
async def test_engine_keeps_input_when_generation_fails(tmp_path):
    repo = Repository(tmp_path / "app.db")
    repo.migrate()
    session = repo.create_lab_session("Sessão com falha")
    engine = ConversationEngine(repo, FailingGenerator())

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await engine.handle_lab_message(session["id"], "oi")

    messages = repo.list_messages(session["conversation_id"])
    assert [message["text"] for message in messages] == ["oi"]
    assert repo.list_events()[0]["category"] == "generation"
