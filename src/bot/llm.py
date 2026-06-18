"""Central factory for OpenAI chat models.

Resolves the API key from the runtime settings (set via the admin panel) first,
falling back to the OPENAI_API_KEY environment variable. This lets the user paste
their GPT key in the panel and have it take effect without editing the server .env.
"""
from __future__ import annotations

import os
from typing import Any

from langchain_openai import ChatOpenAI


def resolve_openai_key(settings: dict[str, Any] | None = None) -> str:
    """Return the OpenAI key, preferring the DB-stored settings over the env var."""
    if settings:
        key = (settings.get("openai_api_key") or "").strip()
        if key:
            return key
    return os.getenv("OPENAI_API_KEY", "").strip()


def make_llm(settings: dict[str, Any] | None = None, **kwargs: Any) -> ChatOpenAI:
    """Build a ChatOpenAI client using the resolved key, model and optional base URL."""
    settings = settings or {}
    params: dict[str, Any] = {
        "model": kwargs.pop("model", None) or settings.get("model", "gpt-4o-mini"),
    }
    key = resolve_openai_key(settings)
    if key:
        params["api_key"] = key
    base_url = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")
    if base_url:
        params["base_url"] = base_url
    params.update(kwargs)
    return ChatOpenAI(**params)
