from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Protocol

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from src.api.repository import Repository
from src.services.humanization import infer_style, timing_for
from src.services.flow_service import classify_message_for_flow



class ResponseGenerator(Protocol):
    async def respond(self, context: dict[str, Any]) -> dict[str, Any]: ...


class ConversationResult(BaseModel):
    messages: list[str]
    draft: str
    evaluation: dict[str, Any]
    timings: list[dict[str, float]]


class LangGraphGenerator:
    async def respond(self, context: dict[str, Any]) -> dict[str, Any]:
        from src.bot.agent import graph

        history = [
            (
                HumanMessage(content=message["text"])
                if message["role"] == "user"
                else AIMessage(content=message["text"])
            )
            for message in context["messages"]
        ]
        result = await graph.ainvoke(
            {
                "messages": history,
                "conversation_id": context["conversation_id"],
                "contact_id": context.get("contact_id"),
                "settings": context["settings"],
                "memories": context["memories"],
                "style": context["style"],
                "revision_count": 0,
                "candidates": [],
            },
            config={
                "configurable": {
                    "thread_id": (
                        f"generation:{context['conversation_id']}:"
                        f"{len(context['messages'])}"
                    )
                }
            },
        )
        return {
            "draft": result.get("current_draft", ""),
            "evaluation": result.get("evaluation", {}),
            "messages": result.get("messages_to_send", []),
        }


class ConversationEngine:
    def __init__(
        self,
        repository: Repository,
        generator: ResponseGenerator | None = None,
    ):
        self.repository = repository
        self.generator = generator or LangGraphGenerator()

    async def handle_lab_message(
        self,
        session_id: str,
        text: str,
    ) -> ConversationResult:
        session = self.repository.get_lab_session(session_id)
        if session is None:
            raise KeyError("Sessão de laboratório não encontrada")
        return await self._handle(
            conversation_id=session["conversation_id"],
            contact_id=session["contact_id"],
            text=text,
        )

    async def handle_whatsapp_message(
        self,
        phone: str,
        text: str,
        *,
        external_id: str,
    ) -> ConversationResult:
        contact = self.repository.upsert_contact(phone)
        conversation = self.repository.get_or_create_conversation(
            contact["id"],
            "whatsapp",
            external_thread_id=phone,
        )
        return await self._handle(
            conversation_id=conversation["id"],
            contact_id=contact["id"],
            text=text,
            external_id=external_id,
        )

    async def _handle(
        self,
        *,
        conversation_id: int,
        contact_id: int,
        text: str,
        external_id: str | None = None,
    ) -> ConversationResult:
        input_message = self.repository.add_message(
            conversation_id,
            "user",
            text.strip(),
            external_id=external_id,
        )
        self._extract_explicit_memories(contact_id, input_message["id"], text)
        style = infer_style(text)
        context = {
            "conversation_id": conversation_id,
            "contact_id": contact_id,
            "settings": self.repository.get_settings(),
            "messages": self.repository.list_messages(conversation_id),
            "memories": self.repository.list_memories(contact_id),
            "style": asdict(style),
        }

        matched_flow = await self._check_and_match_flow(
            text, contact_id, context["settings"]
        )
        if matched_flow:
            generated = self._build_flow_response(matched_flow, contact_id)
        else:
            try:
                generated = await self.generator.respond(context)
            except Exception as error:
                self.repository.add_event(
                    "generation",
                    "error",
                    "Falha ao gerar resposta",
                    {"type": type(error).__name__},
                )
                raise


        draft = str(generated.get("draft", "")).strip()
        evaluation = dict(generated.get("evaluation") or {})
        messages = [
            str(message).strip()
            for message in generated.get("messages", [])
            if str(message).strip()
        ]
        if draft:
            self.repository.add_evaluation(conversation_id, draft, evaluation)
        timings: list[dict[str, float]] = []
        for message in messages:
            timing = asdict(timing_for(message))
            timings.append(timing)
            self.repository.add_message(
                conversation_id,
                "assistant",
                message,
                status="generated",
                metadata={"timing": timing},
            )

        return ConversationResult(
            messages=messages,
            draft=draft,
            evaluation=evaluation,
            timings=timings,
        )

    def _extract_explicit_memories(
        self,
        contact_id: int,
        source_message_id: int,
        text: str,
    ) -> None:
        budget_match = re.search(
            r"(?:orçamento|orcamento)\s+(?:é|e|de|até|ate)?\s*"
            r"(R\$\s*)?([\d.,]+\s*(?:mil|k)?)",
            text,
            flags=re.IGNORECASE,
        )
        if budget_match:
            value = " ".join(
                part for part in budget_match.groups(default="") if part
            ).strip()
            self.repository.upsert_memory(
                contact_id,
                "budget",
                value,
                source_message_id=source_message_id,
            )

        email_match = re.search(
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
            text,
            flags=re.IGNORECASE,
        )
        if email_match:
            self.repository.upsert_memory(
                contact_id,
                "email",
                email_match.group(0),
                source_message_id=source_message_id,
            )

    async def _check_and_match_flow(
        self, text: str, contact_id: int, settings: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Queries all flows, filters out triggered ones, and attempts to match intent.
        Returns the matched flow dict or None.
        """
        try:
            all_flows = self.repository.list_flows()
            flows = [
                f for f in all_flows
                if not self.repository.find_memory(contact_id, f"flow_triggered:{f['id']}")
            ]
            if not flows:
                return None

            flow_id = await classify_message_for_flow(text, flows, settings)
            if flow_id:
                return self.repository.get_flow(flow_id)
        except Exception as flow_error:
            self.repository.add_event(
                "flow",
                "warning",
                f"Erro ao verificar fluxos: {flow_error}",
                {"error": str(flow_error)},
            )
        return None

    def _build_flow_response(self, flow: dict[str, Any], contact_id: int) -> dict[str, Any]:
        """
        Records trigger event and structures sequential flow messages.
        """
        self.repository.upsert_memory(
            contact_id,
            f"flow_triggered:{flow['id']}",
            "true",
        )

        self.repository.add_event(
            "flow",
            "info",
            f"Fluxo inteligente '{flow['name']}' ativado",
            {"contact_id": contact_id, "flow_name": flow["name"]},
        )

        flow_messages = []
        for step in flow.get("steps", []):
            step_type = step.get("type")
            step_text = (step.get("text") or "").strip()
            media_url = (step.get("media_url") or "").strip()

            if step_type == "text":
                if step_text:
                    flow_messages.append(step_text)
            else:
                prefix = {
                    "image": "Imagem",
                    "document": "Documento",
                    "video": "Vídeo",
                    "audio": "Áudio",
                }.get(step_type, "Imagem")

                if step_text:
                    flow_messages.append(f"[{prefix}] {media_url} | {step_text}")
                else:
                    flow_messages.append(f"[{prefix}] {media_url}")

        return {
            "draft": f"Fluxo inteligente ativado: {flow['name']}",
            "evaluation": {
                "approved": True,
                "naturalness": 10,
                "relevance": 10,
                "concision": 10,
                "coherence": 10,
                "repetition": 10,
            },
            "messages": flow_messages,
        }

