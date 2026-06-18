"""CRM extractor node – infers structured lead fields from conversation history.

Uses Gemini with structured output to detect name, email, phone, interest, and
budget from the last exchange, then persists any new/updated values as memories.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.api.repository import get_repository
from src.bot.llm import make_llm
from src.bot.state import AgentState


class CRMFields(BaseModel):
    """Fields extracted from the conversation to enrich the CRM contact."""

    name: str = Field(default="", description="Nome do lead, se mencionado")
    email: str = Field(default="", description="E-mail, se mencionado")
    interest: str = Field(default="", description="Produto/serviço de interesse, se identificado")
    budget: str = Field(default="", description="Orçamento ou faixa de preço, se mencionado")
    next_action: str = Field(
        default="",
        description="Próximo passo sugerido para o vendedor: ex. 'enviar proposta', 'agendar ligação'",
    )
    urgency: str = Field(
        default="",
        description="Grau de urgência: 'baixa', 'media' ou 'alta'",
    )


_EXTRACTION_SYSTEM = """
Você é um analisador de CRM. Extraia informações do lead a partir do histórico de conversa.
Retorne apenas os campos que foram MENCIONADOS EXPLICITAMENTE — deixe os outros em branco.
Não invente dados.
""".strip()


def crm_extractor_node(state: AgentState) -> dict[str, Any]:
    """Extract CRM fields from conversation and persist as memories."""
    settings = state.get("settings", {})
    messages = state.get("messages", [])
    if not messages:
        return {}

    # Build a brief conversation excerpt (last 6 messages max)
    excerpt_messages = messages[-6:]
    conversation_text = "\n".join(
        f"{'Contato' if getattr(m, 'type', None) == 'human' else 'Bot'}: {m.content}"
        for m in excerpt_messages
    )

    llm = make_llm(settings, temperature=0).with_structured_output(CRMFields)

    try:
        result: CRMFields = llm.invoke(
            [
                SystemMessage(content=_EXTRACTION_SYSTEM),
                HumanMessage(content=f"Conversa:\n{conversation_text}"),
            ]
        )
    except Exception:
        # Non-critical — skip silently so main flow continues
        return {}

    # Persist non-empty fields as memories
    contact_id = state.get("contact_id")
    if contact_id:
        repository = get_repository()
        field_map = result.model_dump()
        for key, value in field_map.items():
            if value:
                repository.upsert_memory(
                    contact_id,
                    key,
                    str(value),
                    confidence=0.85,
                )

    crm = result.model_dump()
    return {"crm": crm}
