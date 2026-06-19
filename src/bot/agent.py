import asyncio

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.bot.nodes.critic import critic_node
from src.bot.nodes.drafter import drafter_node
from src.bot.nodes.splitter import splitter_node
from src.bot.state import AgentState
from src.bot.whatsapp import send_whatsapp_message
from src.services.humanization import timing_for


MAX_REVISIONS = 2


async def sender_node(state: AgentState):
    messages_to_send = state.get("messages_to_send", [])
    user_phone = state.get("user_phone")
    sent: list[str] = []

    if user_phone:
        for message in messages_to_send:
            timing = timing_for(message)
            await asyncio.sleep(timing.thinking_seconds)
            await asyncio.sleep(timing.typing_seconds)
            await send_whatsapp_message(to=user_phone, text=message)
            sent.append(message)
    else:
        sent = list(messages_to_send)

    return {
        "messages": [AIMessage(content=" ".join(sent))] if sent else [],
        "messages_to_send": sent,
    }


def critic_router(state: AgentState) -> str:
    evaluation = state.get("evaluation", {})
    if evaluation.get("approved") or state.get("revision_count", 0) >= MAX_REVISIONS:
        return "splitter"
    return "drafter"


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("drafter", drafter_node)
    builder.add_node("critic", critic_node)
    builder.add_node("splitter", splitter_node)
    builder.add_node("sender", sender_node)
    builder.set_entry_point("drafter")
    builder.add_edge("drafter", "critic")
    builder.add_conditional_edges(
        "critic",
        critic_router,
        {"drafter": "drafter", "splitter": "splitter"},
    )
    builder.add_edge("splitter", "sender")
    # crm_extractor is intentionally OFF the graph's critical path: it makes an
    # extra LLM call that the user-facing reply does not depend on. It now runs
    # fire-and-forget from ConversationEngine._handle after the response is ready.
    builder.add_edge("sender", END)
    return builder.compile(checkpointer=MemorySaver())


graph = build_graph()
