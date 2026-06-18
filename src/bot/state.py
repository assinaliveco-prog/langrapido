import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], operator.add]
    conversation_id: int
    contact_id: int
    user_phone: str
    settings: dict[str, Any]
    memories: list[dict[str, Any]]
    style: dict[str, Any]
    current_draft: str
    candidates: list[str]
    evaluation: dict[str, Any]
    messages_to_send: list[str]
    revision_count: int
    crm: dict[str, Any]
