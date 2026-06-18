from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.bot.prompts import build_critic_prompt
from src.bot.state import AgentState


class CriticEvaluation(BaseModel):
    approved: bool
    naturalness: int = Field(ge=0, le=10)
    relevance: int = Field(ge=0, le=10)
    concision: int = Field(ge=0, le=10)
    coherence: int = Field(ge=0, le=10)
    repetition: int = Field(ge=0, le=10)
    issues: list[str] = Field(default_factory=list)
    revision_instruction: str = ""


def critic_node(state: AgentState):
    settings = state.get("settings", {})
    llm = ChatOpenAI(
        model=settings.get("model", "gpt-4o-mini"),
        temperature=0,
    ).with_structured_output(CriticEvaluation)
    history = state.get("messages", [])
    last_user_message = history[-1].content if history else ""
    evaluation = llm.invoke(
        [
            SystemMessage(content=build_critic_prompt(settings)),
            HumanMessage(
                content=(
                    f"Última mensagem do contato:\n{last_user_message}\n\n"
                    f"Resposta proposta:\n{state.get('current_draft', '')}"
                )
            ),
        ]
    )
    data = evaluation.model_dump()
    data["approved"] = bool(
        data["approved"]
        and data["relevance"] >= 8
        and data["coherence"] >= 8
        and data["naturalness"] >= 7
        and not data["issues"]
    )
    return {"evaluation": data}
