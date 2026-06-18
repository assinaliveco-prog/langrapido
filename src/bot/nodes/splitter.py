from src.bot.state import AgentState
from src.services.humanization import safe_typo, split_semantically


def splitter_node(state: AgentState):
    draft = state.get("current_draft", "").strip()
    settings = state.get("settings", {})
    style = state.get("style", {})
    if not draft:
        messages: list[str] = []
    elif settings.get("split_messages", True):
        messages = split_semantically(
            draft,
            max_chunks=3,
            target_chars=style.get("target_chars", 180),
        )
    else:
        messages = [draft]

    typo_probability = settings.get("typo_probability", 0)
    if typo_probability:
        messages = [
            safe_typo(message, probability=typo_probability) for message in messages
        ]
    return {"messages_to_send": messages}
