from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.api.repository import get_repository
from src.bot.prompts import build_drafter_prompt
from src.bot.state import AgentState


def drafter_node(state: AgentState):
    settings = state.get("settings") or get_repository().get_settings()
    prompt = build_drafter_prompt(
        settings,
        state.get("style", {}),
        state.get("memories", []),
    )
    messages = [SystemMessage(content=prompt), *state.get("messages", [])]
    evaluation = state.get("evaluation", {})
    instruction = evaluation.get("revision_instruction")
    if instruction:
        messages.append(
            HumanMessage(
                content=(
                    "Reescreva a resposta anterior corrigindo apenas isto: "
                    f"{instruction}"
                )
            )
        )

    llm = ChatOpenAI(
        model=settings.get("model", "gpt-4o-mini"),
        temperature=0.65,
    )
    response = llm.invoke(messages)
    draft = response.content.strip()
    return {
        "current_draft": draft,
        "candidates": [*state.get("candidates", []), draft],
        "revision_count": state.get("revision_count", 0) + 1,
        "settings": settings,
    }
