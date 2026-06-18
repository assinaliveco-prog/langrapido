from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.api.db import get_personality, update_personality
from src.api.repository import Repository, get_repository
from src.api.routes_admin import router as admin_router
from src.api.routes_webhook import router as webhook_router
from src.api.schemas import HealthResponse
from src.services.conversation import ConversationEngine
from src.services.whatsapp import WhatsAppClient, get_whatsapp_client


load_dotenv()

# Fallback environment variables for VPS deployment (from Easypanel LLM keys)
if not os.getenv("OPENAI_API_KEY") and os.getenv("LLM_API_KEY"):
    os.environ["OPENAI_API_KEY"] = os.environ.get("LLM_API_KEY", "")
if not os.getenv("OPENAI_API_BASE") and os.getenv("LLM_API_BASE"):
    os.environ["OPENAI_API_BASE"] = os.environ.get("LLM_API_BASE", "")
    os.environ["OPENAI_BASE_URL"] = os.environ.get("LLM_API_BASE", "")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"



@dataclass
class AppServices:
    repository: Repository
    engine: ConversationEngine
    whatsapp: WhatsAppClient


def create_app() -> FastAPI:
    application = FastAPI(title="LangRápido", version="2.0.0")
    repository = get_repository()
    application.state.services = AppServices(
        repository=repository,
        engine=ConversationEngine(repository),
        whatsapp=get_whatsapp_client(repository),
    )
    application.include_router(admin_router)
    application.include_router(webhook_router)
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.get("/painel", response_class=HTMLResponse)
    async def admin_panel():
        return (BASE_DIR / "templates" / "panel.html").read_text(encoding="utf-8")

    @application.get("/api/health", response_model=HealthResponse)
    async def health():
        ai_configured = bool(os.getenv("OPENAI_API_KEY"))
        whatsapp = application.state.services.whatsapp
        whatsapp_configured = whatsapp.configured
        whatsapp_details = None
        if whatsapp_configured:
            whatsapp_details = await whatsapp.get_phone_number_details()
        return {
            "status": (
                "ready" if ai_configured and whatsapp_configured else "degraded"
            ),
            "database": repository.path.exists(),
            "ai_configured": ai_configured,
            "whatsapp_configured": whatsapp_configured,
            "whatsapp_details": whatsapp_details,
        }


    @application.get("/api/personality")
    async def get_personality_api():
        return get_personality() or {}

    @application.post("/api/personality")
    async def set_personality_api(data: dict):
        return update_personality(
            data.get("system_prompt", ""),
            data.get("slang_level", "media"),
            bool(data.get("use_emojis", True)),
        )

    return application


app = create_app()
