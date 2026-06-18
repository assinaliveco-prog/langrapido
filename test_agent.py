"""Integration test for the LangGraph agent pipeline.

Runs the full drafter -> critic -> splitter -> sender -> crm_extractor graph
with mocked LLM and WhatsApp calls so no real API key is needed.
"""
from __future__ import annotations

import asyncio
import pytest

from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeDraft(MagicMock):
    content = "Ola! Posso te ajudar com isso. Qual e o seu orcamento?"


class _FakeEval(BaseModel):
    approved: bool = True
    naturalness: int = 9
    relevance: int = 9
    concision: int = 9
    coherence: int = 9
    repetition: int = 0
    issues: list[str] = []
    revision_instruction: str = ""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_humanization():
    """Full pipeline smoke test: graph runs end-to-end without errors."""
    from src.bot.agent import graph

    sent: list[str] = []

    async def _mock_send(to, text):
        sent.append(text)

    with (
        patch("src.bot.whatsapp.send_whatsapp_message", new=_mock_send),
        patch(
            "src.bot.nodes.drafter.ChatOpenAI",
            return_value=MagicMock(invoke=MagicMock(return_value=_FakeDraft())),
        ),
        patch(
            "src.bot.nodes.critic.ChatOpenAI",
            return_value=MagicMock(
                with_structured_output=MagicMock(
                    return_value=MagicMock(invoke=MagicMock(return_value=_FakeEval()))
                )
            ),
        ),
        patch(
            "src.bot.nodes.crm_extractor.ChatOpenAI",
            return_value=MagicMock(
                with_structured_output=MagicMock(
                    return_value=MagicMock(
                        invoke=MagicMock(
                            return_value=MagicMock(
                                model_dump=MagicMock(
                                    return_value={
                                        "name": "",
                                        "email": "",
                                        "interest": "",
                                        "budget": "",
                                        "next_action": "",
                                        "urgency": "",
                                    }
                                )
                            )
                        )
                    )
                )
            ),
        ),
    ):
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content="Quero comprar, qual o preco?")],
                "user_phone": None,
                "settings": {},
                "memories": [],
                "style": {},
                "revision_count": 0,
                "candidates": [],
            },
            config={"configurable": {"thread_id": "test-pipeline-openai-001"}},
        )

    draft = result.get("current_draft", "")
    assert isinstance(draft, str), "current_draft deve ser string"
    assert len(draft) > 0, "current_draft nao deve estar vazio"

    evaluation = result.get("evaluation", {})
    assert "approved" in evaluation, "evaluation deve ter campo 'approved'"

    print(f"\n OK Pipeline completo com OpenAI - draft: {draft!r}")
    print(f"   evaluation: approved={evaluation.get('approved')}")


if __name__ == "__main__":
    asyncio.run(test_humanization())
