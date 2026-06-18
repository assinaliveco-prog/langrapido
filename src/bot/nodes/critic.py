import difflib

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.bot.llm import make_llm
from src.bot.prompts import build_critic_prompt
from src.bot.state import AgentState


def _too_similar(a: str, b: str, threshold: float = 0.82) -> bool:
    if not a or not b:
        return False
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold


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
    llm = make_llm(settings, temperature=0).with_structured_output(CriticEvaluation)
    history = state.get("messages", [])
    last_user_message = history[-1].content if history else ""
    # Recent bot replies so the critic can actually catch repetition.
    prior_replies = [m.content for m in history if isinstance(m, AIMessage)][-3:]
    prior_block = "\n".join(f"- {reply}" for reply in prior_replies) or "(nenhuma ainda)"
    evaluation = llm.invoke(
        [
            SystemMessage(content=build_critic_prompt(settings)),
            HumanMessage(
                content=(
                    f"Suas respostas anteriores neste chat (a proposta NÃO pode "
                    f"repetir nem parafrasear estas):\n{prior_block}\n\n"
                    f"Última mensagem do contato:\n{last_user_message}\n\n"
                    f"Resposta proposta:\n{state.get('current_draft', '')}"
                )
            ),
        ]
    )
    data = evaluation.model_dump()

    # Deterministic repetition guard — does not depend on the LLM's judgement.
    draft = state.get("current_draft", "")
    duplicate = next((r for r in prior_replies if _too_similar(draft, r)), None)
    if duplicate:
        data["repetition"] = min(data.get("repetition", 0), 2)
        data.setdefault("issues", []).append("resposta quase idêntica a uma anterior")
        if not data.get("revision_instruction"):
            data["revision_instruction"] = (
                f"Sua resposta está quase idêntica a esta que você já enviou: "
                f"\"{duplicate[:80]}\". Reformule completamente, com outra abordagem e "
                f"outras palavras, e avance a conversa para um novo passo."
            )

    data["approved"] = bool(
        data["approved"]
        and data["relevance"] >= 8
        and data["coherence"] >= 8
        and data["naturalness"] >= 7
        and data["repetition"] >= 7
        and not data["issues"]
    )
    return {"evaluation": data}
