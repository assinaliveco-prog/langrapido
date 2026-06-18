from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Iterator

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request


router = APIRouter(tags=["webhook"])


@dataclass(frozen=True)
class IncomingWhatsAppMessage:
    external_id: str
    phone: str
    text: str


def iter_text_messages(payload: dict) -> Iterator[IncomingWhatsAppMessage]:
    if payload.get("object") != "whatsapp_business_account":
        return
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                if message.get("type") != "text":
                    continue
                external_id = message.get("id")
                phone = message.get("from")
                text = message.get("text", {}).get("body", "").strip()
                if external_id and phone and text:
                    yield IncomingWhatsAppMessage(external_id, phone, text)


def iter_evolution_messages(payload: dict) -> Iterator[IncomingWhatsAppMessage]:
    event = payload.get("event")
    if event != "messages.upsert":
        return
    data = payload.get("data", {})
    key = data.get("key", {})
    from_me = key.get("fromMe", False)
    if from_me:
        return
    remote_jid = key.get("remoteJid", "")
    phone = remote_jid.split("@")[0] if "@" in remote_jid else remote_jid
    text = data.get("messageContent", "")
    if not text:
        message = data.get("message", {})
        text = message.get("conversation", "") or message.get("extendedTextMessage", {}).get("text", "")
    text = text.strip()
    external_id = key.get("id")
    if external_id and phone and text:
        yield IncomingWhatsAppMessage(external_id, phone, text)



import re


def parse_media_message(text: str) -> tuple[str, str, str | None] | None:
    match = re.match(
        r"^\[(Imagem|Documento|Vídeo|Áudio|Image|Document|Video|Audio)\]\s*(https?://[^\s|]+|/[^\s|]+)(?:\s*\|\s*(.*))?$",
        text,
        re.IGNORECASE,
    )
    if match:
        media_type = match.group(1).capitalize()
        if media_type in ("Video", "Vídeo"):
            media_type = "Vídeo"
        elif media_type in ("Audio", "Áudio"):
            media_type = "Áudio"
        elif media_type in ("Image", "Imagem"):
            media_type = "Imagem"
        elif media_type in ("Document", "Documento"):
            media_type = "Documento"

        url = match.group(2).strip()
        caption = match.group(3)
        if caption:
            caption = caption.strip()
        return media_type, url, caption
    return None


async def process_message(message: IncomingWhatsAppMessage, services) -> None:
    try:
        if services.whatsapp.configured:
            await services.whatsapp.mark_read(message.external_id)
        result = await services.engine.handle_whatsapp_message(
            message.phone,
            message.text,
            external_id=message.external_id,
        )
        if services.whatsapp.configured:
            for text, timing in zip(result.messages, result.timings):
                await asyncio.sleep(timing["thinking_seconds"])
                await asyncio.sleep(timing["typing_seconds"])
                parsed = parse_media_message(text)
                if parsed:
                    media_type, url, caption = parsed
                    if media_type == "Imagem":
                        await services.whatsapp.send_image(message.phone, url, caption)
                    elif media_type == "Documento":
                        await services.whatsapp.send_document(message.phone, url, caption)
                    elif media_type == "Vídeo":
                        await services.whatsapp.send_video(message.phone, url, caption)
                    elif media_type == "Áudio":
                        await services.whatsapp.send_audio(message.phone, url)
                else:
                    await services.whatsapp.send_text(message.phone, text)
    except Exception as error:
        services.repository.add_event(
            "webhook",
            "error",
            "Falha ao processar mensagem do WhatsApp",
            {
                "external_id": message.external_id,
                "type": type(error).__name__,
            },
        )


def enqueue_message(
    background_tasks: BackgroundTasks,
    message: IncomingWhatsAppMessage,
    services,
) -> None:
    background_tasks.add_task(process_message, message, services)


@router.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    expected_token = os.getenv("VERIFY_TOKEN")

    if mode == "subscribe" and expected_token and token == expected_token:
        try:
            return int(challenge or "")
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail="Challenge inválido",
            ) from error
    if mode and token:
        raise HTTPException(status_code=403, detail="Token de verificação inválido")
    raise HTTPException(
        status_code=400,
        detail="Parâmetros de verificação ausentes",
    )


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    payload = await request.json()
    services = request.app.state.services
    accepted = 0
    
    # Official Meta Cloud API
    for message in iter_text_messages(payload):
        if not services.repository.claim_webhook(message.external_id):
            continue
        enqueue_message(background_tasks, message, services)
        accepted += 1
        
    # Evolution API
    for message in iter_evolution_messages(payload):
        if not services.repository.claim_webhook(message.external_id):
            continue
        enqueue_message(background_tasks, message, services)
        accepted += 1
        
    return {"status": "accepted", "accepted": accepted}
