"""Integration test for the LangGraph agent pipeline.

Runs the drafter -> critic -> splitter -> sender graph with mocked LLM and
WhatsApp calls so no real API key is needed. (CRM extraction now runs off the
graph, fire-and-forget, so it is not part of this pipeline test.)
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
    repetition: int = 9
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

    # Drafter calls make_llm(...).invoke(); critic calls
    # make_llm(...).with_structured_output(...).invoke(). One mock serves both,
    # patched at the single factory source (src.bot.llm.ChatOpenAI).
    fake_llm = MagicMock()
    fake_llm.invoke = MagicMock(return_value=_FakeDraft())
    fake_llm.with_structured_output = MagicMock(
        return_value=MagicMock(invoke=MagicMock(return_value=_FakeEval()))
    )

    with (
        patch("src.bot.whatsapp.send_whatsapp_message", new=_mock_send),
        patch("src.bot.llm.ChatOpenAI", return_value=fake_llm),
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
