from __future__ import annotations

import os
from typing import Any

import httpx


class WhatsAppClient:
    def __init__(
        self,
        repository: Any = None,
        token: str = "",
        phone_number_id: str = "",
        api_version: str = "v22.0",
        http: httpx.AsyncClient | None = None,
    ):
        self.repository = repository
        self.token = token
        self.phone_number_id = phone_number_id
        self.api_version = api_version
        self.http = http

    def get_config(self) -> dict[str, Any]:
        config = {
            "provider": "official",
            "token": self.token or os.getenv("WHATSAPP_TOKEN", ""),
            "phone_number_id": self.phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
            "api_version": self.api_version or os.getenv("WHATSAPP_API_VERSION", "v22.0"),
            "evolution_url": os.getenv("EVOLUTION_API_URL", ""),
            "evolution_key": os.getenv("EVOLUTION_API_KEY", ""),
            "evolution_instance": os.getenv("EVOLUTION_INSTANCE_NAME", ""),
        }
        if self.repository is not None:
            try:
                settings = self.repository.get_settings()
                provider = settings.get("whatsapp_provider", "official")
                config["provider"] = provider
                if provider == "evolution":
                    config["evolution_url"] = settings.get("evolution_url") or config["evolution_url"]
                    config["evolution_key"] = settings.get("evolution_key") or config["evolution_key"]
                    config["evolution_instance"] = settings.get("evolution_instance") or config["evolution_instance"]
            except Exception:
                pass
        return config

    @property
    def configured(self) -> bool:
        cfg = self.get_config()
        if cfg["provider"] == "official":
            return bool(cfg["token"] and cfg["phone_number_id"])
        else:
            return bool(cfg["evolution_url"] and cfg["evolution_key"] and cfg["evolution_instance"])

    def _to_absolute_url(self, url: str) -> str:
        if url.startswith("/"):
            public_url = os.getenv("PUBLIC_URL") or "http://localhost:8000"
            return f"{public_url.rstrip('/')}{url}"
        return url

    async def _post_api(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("Integração do WhatsApp não configurada")
        if self.http is not None:
            response = await self.http.post(
                url,
                headers=headers,
                json=payload,
                timeout=15,
            )
        else:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                )
        response.raise_for_status()
        return response.json()

    async def mark_read(self, message_id: str) -> dict[str, Any]:
        cfg = self.get_config()
        if cfg["provider"] == "official":
            url = f"https://graph.facebook.com/{cfg['api_version']}/{cfg['phone_number_id']}/messages"
            headers = {
                "Authorization": f"Bearer {cfg['token']}",
                "Content-Type": "application/json",
            }
            payload = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id,
            }
            return await self._post_api(url, headers, payload)
        return {"status": "ok"}

    async def send_text(self, to: str, text: str) -> dict[str, Any]:
        cfg = self.get_config()
        if cfg["provider"] == "official":
            url = f"https://graph.facebook.com/{cfg['api_version']}/{cfg['phone_number_id']}/messages"
            headers = {
                "Authorization": f"Bearer {cfg['token']}",
                "Content-Type": "application/json",
            }
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"preview_url": False, "body": text},
            }
            return await self._post_api(url, headers, payload)
        else:
            url = f"{cfg['evolution_url']}/message/sendText/{cfg['evolution_instance']}"
            headers = {
                "apikey": cfg["evolution_key"],
                "Content-Type": "application/json",
            }
            payload = {
                "number": to,
                "text": text,
            }
            return await self._post_api(url, headers, payload)

    async def send_image(
        self, to: str, url: str, caption: str | None = None
    ) -> dict[str, Any]:
        url = self._to_absolute_url(url)
        cfg = self.get_config()
        if cfg["provider"] == "official":
            official_url = f"https://graph.facebook.com/{cfg['api_version']}/{cfg['phone_number_id']}/messages"
            headers = {
                "Authorization": f"Bearer {cfg['token']}",
                "Content-Type": "application/json",
            }
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "image",
                "image": {"link": url},
            }
            if caption:
                payload["image"]["caption"] = caption
            return await self._post_api(official_url, headers, payload)
        else:
            evolution_url = f"{cfg['evolution_url']}/message/sendMedia/{cfg['evolution_instance']}"
            headers = {
                "apikey": cfg["evolution_key"],
                "Content-Type": "application/json",
            }
            payload = {
                "number": to,
                "mediatype": "image",
                "media": url,
                "caption": caption or "",
            }
            return await self._post_api(evolution_url, headers, payload)

    async def send_document(
        self,
        to: str,
        url: str,
        caption: str | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        url = self._to_absolute_url(url)
        cfg = self.get_config()
        if cfg["provider"] == "official":
            official_url = f"https://graph.facebook.com/{cfg['api_version']}/{cfg['phone_number_id']}/messages"
            headers = {
                "Authorization": f"Bearer {cfg['token']}",
                "Content-Type": "application/json",
            }
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "document",
                "document": {"link": url},
            }
            if caption:
                payload["document"]["caption"] = caption
            if filename:
                payload["document"]["filename"] = filename
            return await self._post_api(official_url, headers, payload)
        else:
            evolution_url = f"{cfg['evolution_url']}/message/sendMedia/{cfg['evolution_instance']}"
            headers = {
                "apikey": cfg["evolution_key"],
                "Content-Type": "application/json",
            }
            payload = {
                "number": to,
                "mediatype": "document",
                "media": url,
                "caption": caption or "",
            }
            if filename:
                payload["fileName"] = filename
            return await self._post_api(evolution_url, headers, payload)

    async def send_video(
        self, to: str, url: str, caption: str | None = None
    ) -> dict[str, Any]:
        url = self._to_absolute_url(url)
        cfg = self.get_config()
        if cfg["provider"] == "official":
            official_url = f"https://graph.facebook.com/{cfg['api_version']}/{cfg['phone_number_id']}/messages"
            headers = {
                "Authorization": f"Bearer {cfg['token']}",
                "Content-Type": "application/json",
            }
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "video",
                "video": {"link": url},
            }
            if caption:
                payload["video"]["caption"] = caption
            return await self._post_api(official_url, headers, payload)
        else:
            evolution_url = f"{cfg['evolution_url']}/message/sendMedia/{cfg['evolution_instance']}"
            headers = {
                "apikey": cfg["evolution_key"],
                "Content-Type": "application/json",
            }
            payload = {
                "number": to,
                "mediatype": "video",
                "media": url,
                "caption": caption or "",
            }
            return await self._post_api(evolution_url, headers, payload)

    async def send_audio(self, to: str, url: str) -> dict[str, Any]:
        url = self._to_absolute_url(url)
        cfg = self.get_config()
        if cfg["provider"] == "official":
            official_url = f"https://graph.facebook.com/{cfg['api_version']}/{cfg['phone_number_id']}/messages"
            headers = {
                "Authorization": f"Bearer {cfg['token']}",
                "Content-Type": "application/json",
            }
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "audio",
                "audio": {"link": url},
            }
            return await self._post_api(official_url, headers, payload)
        else:
            evolution_url = f"{cfg['evolution_url']}/message/sendMedia/{cfg['evolution_instance']}"
            headers = {
                "apikey": cfg["evolution_key"],
                "Content-Type": "application/json",
            }
            payload = {
                "number": to,
                "mediatype": "audio",
                "media": url,
            }
            return await self._post_api(evolution_url, headers, payload)

    async def get_phone_number_details(self) -> dict[str, Any] | None:
        if not self.configured:
            return None
        cfg = self.get_config()
        if cfg["provider"] == "official":
            url = f"https://graph.facebook.com/{cfg['api_version']}/{cfg['phone_number_id']}"
            headers = {"Authorization": f"Bearer {cfg['token']}"}
            try:
                if self.http is not None:
                    response = await self.http.get(url, headers=headers, timeout=10)
                else:
                    async with httpx.AsyncClient(timeout=10) as client:
                        response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    return response.json()
            except Exception:
                pass
        else:
            url = f"{cfg['evolution_url']}/instance/connectionState/{cfg['evolution_instance']}"
            headers = {"apikey": cfg["evolution_key"]}
            try:
                if self.http is not None:
                    response = await self.http.get(url, headers=headers, timeout=10)
                else:
                    async with httpx.AsyncClient(timeout=10) as client:
                        response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    instance_data = data.get("instance", {})
                    state = instance_data.get("state")
                    if state == "open":
                        return {
                            "display_phone_number": cfg["evolution_instance"],
                            "verified_name": f"Evolution API ({cfg['evolution_instance']})",
                            "id": cfg["evolution_instance"],
                            "status": "connected"
                        }
            except Exception:
                pass
        return None


def get_whatsapp_client(repository: Any = None) -> WhatsAppClient:
    return WhatsAppClient(
        repository=repository,
        token=os.getenv("WHATSAPP_TOKEN", ""),
        phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
        api_version=os.getenv("WHATSAPP_API_VERSION", "v22.0"),
    )
