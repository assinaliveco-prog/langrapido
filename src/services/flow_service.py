import json
import logging
import os
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger("flow_service")


async def classify_message_for_flow(
    text: str,
    flows: list[dict[str, Any]],
    settings: dict[str, Any],
) -> int | None:
    """
    Classifies a user message against a list of custom flows to see if one triggers.
    Returns the flow ID if there's a match, or None.
    """
    if not flows:
        return None

    # Format the flows description for the prompt
    flows_list_str = ""
    for f in flows:
        flows_list_str += (
            f"ID: {f['id']} - Nome: {f['name']} - "
            f"Quando usar (Intenção/Gatilho): {f['trigger_intent']}\n"
        )

    system_prompt = f"""Você é o classificador de intenções da central de atendimento inteligente.
Sua única tarefa é analisar a última mensagem enviada pelo usuário e determinar se ela ativa algum dos fluxos pré-configurados listados abaixo.

Fluxos disponíveis:
{flows_list_str}

Regras:
1. Responda APENAS com o ID numérico do fluxo ativado (ex: 3) se a intenção do usuário corresponder de forma clara a um dos fluxos disponíveis.
2. Se a mensagem do usuário NÃO corresponder a nenhum dos fluxos, ou se for apenas saudações genéricas (ex: "oi", "bom dia") ou dúvidas que o atendente de IA geral deve responder, responda apenas 'NONE'.
3. Não invente IDs. Não responda com nenhuma outra palavra senão o ID ou 'NONE'.
"""

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment. Skipping flow matching.")
            return None

        # Build the messages
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Mensagem do Usuário: '{text}'"),
        ]

        llm = ChatOpenAI(
            model=settings.get("model", "gpt-4o-mini"),
            temperature=0.0,  # 0.0 for deterministic classification
            max_tokens=10,
        )
        response = await llm.ainvoke(messages)
        result = response.content.strip().upper()

        if "NONE" in result or not result:
            return None

        # Try to parse the result as an integer ID
        digits = "".join(c for c in result if c.isdigit())
        if digits:
            flow_id = int(digits)
            # Verify the flow ID exists in the active flows list
            if any(f["id"] == flow_id for f in flows):
                return flow_id

        return None
    except Exception as e:
        logger.error(f"Error in flow classification: {e}")
        return None
