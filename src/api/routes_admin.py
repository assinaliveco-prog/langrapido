from __future__ import annotations

import os
import shutil
import uuid
import httpx

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from src.api.schemas import (
    AgentSettings,
    FlowCreate,
    FlowResponse,
    LabMessageRequest,
    LabSessionRequest,
)


router = APIRouter(prefix="/api", tags=["admin"])

# Sentinel char used to mask secrets in API responses. update_settings treats any
# incoming value containing it (or empty) as "unchanged" so the masked value the
# browser holds is never written back over the real secret.
MASK_CHAR = "…"
_SECRET_FIELDS = ("openai_api_key", "evolution_key")


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return "••••"
    return f"{value[:3]}{MASK_CHAR}{value[-4:]}"


def _mask_settings(settings: dict) -> dict:
    return {**settings, **{f: _mask_secret(settings.get(f, "")) for f in _SECRET_FIELDS}}


@router.get("/dashboard")
async def dashboard(request: Request):
    from src.bot.llm import resolve_openai_key

    services = request.app.state.services
    stats = services.repository.dashboard_stats()
    settings = services.repository.get_settings()
    return {
        **stats,
        "model": settings["model"],
        "ai_configured": bool(resolve_openai_key(settings)),
        "whatsapp_configured": services.whatsapp.configured,
    }


@router.get("/settings", response_model=AgentSettings)
async def get_settings(request: Request):
    return _mask_settings(request.app.state.services.repository.get_settings())


@router.put("/settings", response_model=AgentSettings)
async def put_settings(settings: AgentSettings, request: Request):
    saved = request.app.state.services.repository.update_settings(
        settings.model_dump()
    )
    return _mask_settings(saved)


@router.get("/contacts")
async def list_contacts(request: Request):
    return request.app.state.services.repository.list_contacts()


@router.get("/contacts/{contact_id}")
async def get_contact(contact_id: int, request: Request):
    repository = request.app.state.services.repository
    contact = repository.get_contact(contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contato não encontrado")
    return {
        **contact,
        "memories": repository.list_memories(contact_id),
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: int, request: Request):
    return request.app.state.services.repository.list_messages(conversation_id)


@router.post(
    "/lab/sessions",
    status_code=status.HTTP_201_CREATED,
)
async def create_lab_session(payload: LabSessionRequest, request: Request):
    session = request.app.state.services.repository.create_lab_session(payload.name)
    return {**session, "channel": "lab"}


@router.post("/lab/sessions/{session_id}/messages")
async def send_lab_message(
    session_id: str,
    payload: LabMessageRequest,
    request: Request,
):
    services = request.app.state.services
    try:
        return await services.engine.handle_lab_message(session_id, payload.text)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "O provedor de IA não está disponível. "
                "A mensagem foi preservada para nova tentativa."
            ),
        ) from error


@router.delete(
    "/lab/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_lab_session(session_id: str, request: Request):
    deleted = request.app.state.services.repository.delete_lab_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Sessão de laboratório não encontrada",
        )


@router.get("/events")
async def list_events(request: Request, limit: int = 100):
    safe_limit = max(1, min(limit, 500))
    return request.app.state.services.repository.list_events(safe_limit)


@router.get("/flows", response_model=list[FlowResponse])
async def list_flows(request: Request):
    return request.app.state.services.repository.list_flows()


@router.get("/flows/{flow_id}", response_model=FlowResponse)
async def get_flow(flow_id: int, request: Request):
    flow = request.app.state.services.repository.get_flow(flow_id)
    if flow is None:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    return flow


@router.post(
    "/flows",
    response_model=FlowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_flow(flow: FlowCreate, request: Request):
    return request.app.state.services.repository.add_flow(
        flow.name,
        flow.trigger_intent,
        [step.model_dump() for step in flow.steps],
    )


@router.put("/flows/{flow_id}", response_model=FlowResponse)
async def update_flow(flow_id: int, flow: FlowCreate, request: Request):
    updated = request.app.state.services.repository.update_flow(
        flow_id,
        flow.name,
        flow.trigger_intent,
        [step.model_dump() for step in flow.steps],
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")
    return updated


@router.delete("/flows/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(flow_id: int, request: Request):
    deleted = request.app.state.services.repository.delete_flow(flow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Fluxo não encontrado")


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    uploads_dir = os.path.join(os.path.dirname(__file__), "static", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(uploads_dir, unique_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    url_path = f"/static/uploads/{unique_filename}"
    return {"url": url_path, "filename": file.filename}


@router.get("/instances/nettest")
async def nettest(request: Request):
    """Probe which internal hostname reaches the Evolution service (for webhook URL)."""
    # self-reach probes: which internal hostname:port reaches THIS app (langrapido)
    candidates = [
        "http://langrapido:8000/api/health",
        "http://jota_langrapido:8000/api/health",
        "http://jota-langrapido:8000/api/health",
        "http://langrapido:80/api/health",
        "http://langrapido:3000/api/health",
    ]
    results = {}
    for host in candidates:
        try:
            async with httpx.AsyncClient(timeout=6) as c:
                r = await c.get(host)
            results[host] = r.status_code
        except Exception as e:
            results[host] = type(e).__name__ + ": " + str(e)[:40]
    return results


@router.get("/instances/debug")
async def debug_instance(request: Request):
    """Raw Evolution diagnostics — connection state + instance details."""
    services = request.app.state.services
    cfg = services.whatsapp.get_config()
    if cfg["provider"] != "evolution":
        return {"error": "provider is not evolution", "provider": cfg["provider"]}
    base = cfg["evolution_url"].rstrip("/")
    inst = cfg["evolution_instance"]
    headers = {"apikey": cfg["evolution_key"]}
    out = {"url": base, "instance": inst}
    async with httpx.AsyncClient(timeout=15) as c:
        try:
            r = await c.get(f"{base}/instance/connectionState/{inst}", headers=headers)
            out["connectionState"] = {"http": r.status_code, "body": r.text[:300]}
        except Exception as e:
            out["connectionState"] = {"error": str(e)[:150]}
        try:
            r3 = await c.post(
                f"{base}/chat/findMessages/{inst}",
                headers={**headers, "Content-Type": "application/json"},
                json={"where": {}, "limit": 5},
            )
            data = r3.json()
            msgs = data.get("messages", data) if isinstance(data, dict) else data
            records = msgs.get("records", msgs) if isinstance(msgs, dict) else msgs
            count = len(records) if isinstance(records, list) else "?"
            out["messagesInEvolution"] = {"http": r3.status_code, "count": count}
        except Exception as e:
            out["messagesInEvolution"] = {"error": str(e)[:150]}
        try:
            r4 = await c.get(f"{base}/webhook/find/{inst}", headers=headers)
            out["webhookConfig"] = {"http": r4.status_code, "body": r4.text[:200]}
        except Exception as e:
            out["webhookConfig"] = {"error": str(e)[:150]}
    return out


@router.get("/instances/status")
async def get_instance_status(request: Request):
    services = request.app.state.services
    cfg = services.whatsapp.get_config()

    if cfg["provider"] == "official":
        details = await services.whatsapp.get_phone_number_details()
        if details:
            return {
                "provider": "official",
                "status": "connected",
                "display_name": details.get("verified_name", "WhatsApp Cloud API"),
                "phone": details.get("display_phone_number", ""),
                "id": details.get("id", ""),
            }
        else:
            return {
                "provider": "official",
                "status": "disconnected" if services.whatsapp.configured else "unconfigured",
            }
    else:
        if not services.whatsapp.configured:
            return {
                "provider": "evolution",
                "status": "unconfigured",
            }
        # Evolution API connectionState
        url = f"{cfg['evolution_url']}/instance/connectionState/{cfg['evolution_instance']}"
        headers = {"apikey": cfg["evolution_key"]}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.get(url, headers=headers)
            
            # If instance doesn't exist on Evolution, try creating it
            if res.status_code == 404 or (res.status_code == 200 and res.json().get("status") == 404) or (res.status_code == 200 and "not found" in res.json().get("message", "").lower()):
                create_url = f"{cfg['evolution_url']}/instance/create"
                create_payload = {
                    "instanceName": cfg["evolution_instance"],
                    "qrcode": True,
                    "integration": "WHATSAPP-BAILEYS",
                }
                async with httpx.AsyncClient(timeout=20) as client:
                    create_res = await client.post(create_url, headers=headers, json=create_payload)
                if create_res.status_code == 201 or create_res.status_code == 200:
                    qr_data = create_res.json()
                    qrcode = qr_data.get("qrcode", {}).get("base64") or qr_data.get("base64")
                    return {
                        "provider": "evolution",
                        "status": "disconnected",
                        "qrcode": qrcode,
                    }
                else:
                    return {
                        "provider": "evolution",
                        "status": "error",
                        "detail": f"Erro ao criar instância no Evolution (Status: {create_res.status_code})",
                    }

            if res.status_code == 200:
                data = res.json()
                # If instance is open/connected
                state = data.get("instance", {}).get("state")
                if state == "open":
                    return {
                        "provider": "evolution",
                        "status": "connected",
                        "display_name": f"Evolution API ({cfg['evolution_instance']})",
                        "phone": cfg["evolution_instance"],
                        "id": cfg["evolution_instance"],
                    }
                elif state == "connecting":
                    # Already pairing — do NOT call /instance/connect again, it
                    # restarts the Baileys socket and prevents the pair from
                    # completing. Just report waiting; the QR was already issued.
                    return {
                        "provider": "evolution",
                        "status": "disconnected",
                        "connecting": True,
                    }
                else:
                    # Truly closed — (re)start the connection to fetch a QR.
                    connect_url = f"{cfg['evolution_url']}/instance/connect/{cfg['evolution_instance']}"
                    async with httpx.AsyncClient(timeout=10) as client:
                        connect_res = await client.get(connect_url, headers=headers)
                    qrcode = None
                    if connect_res.status_code == 200:
                        qr_data = connect_res.json()
                        qrcode = qr_data.get("base64") or qr_data.get("code")
                    return {
                        "provider": "evolution",
                        "status": "disconnected",
                        "qrcode": qrcode,
                    }
            else:
                return {
                    "provider": "evolution",
                    "status": "error",
                    "detail": f"Evolution API retornou status {res.status_code}",
                }
        except Exception as e:
            return {
                "provider": "evolution",
                "status": "error",
                "detail": f"Erro de conexão com Evolution API: {str(e)}",
            }


@router.post("/instances/connect")
async def connect_instance(request: Request):
    """Force an Evolution instance to (re)connect and return a fresh QR code."""
    services = request.app.state.services
    cfg = services.whatsapp.get_config()
    if cfg["provider"] == "official":
        raise HTTPException(
            status_code=400,
            detail="Conexão por QR Code disponível apenas para Evolution API",
        )
    if not services.whatsapp.configured:
        raise HTTPException(
            status_code=400,
            detail="Configure a URL, a chave e o nome da instância antes de conectar",
        )

    base = cfg["evolution_url"].rstrip("/")
    instance = cfg["evolution_instance"]
    headers = {"apikey": cfg["evolution_key"]}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(
                f"{base}/instance/connect/{instance}", headers=headers
            )
            # Instance not created yet → create it (qrcode=True returns the QR)
            if res.status_code == 404:
                create_res = await client.post(
                    f"{base}/instance/create",
                    headers=headers,
                    json={
                        "instanceName": instance,
                        "qrcode": True,
                        "integration": "WHATSAPP-BAILEYS",
                    },
                )
                if create_res.status_code not in (200, 201):
                    raise HTTPException(
                        status_code=502,
                        detail=f"Erro ao criar instância (status {create_res.status_code})",
                    )
                data = create_res.json()
                qrcode = data.get("qrcode", {}).get("base64") or data.get("base64")
                return {"status": "disconnected", "qrcode": qrcode}

        if res.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Evolution API retornou status {res.status_code}",
            )
        data = res.json()
        # Already connected
        if data.get("instance", {}).get("state") == "open":
            return {"status": "connected"}
        qrcode = (
            data.get("base64")
            or data.get("code")
            or data.get("qrcode", {}).get("base64")
        )
        return {"status": "disconnected", "qrcode": qrcode}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro de conexão com Evolution API: {error}",
        ) from error


@router.post("/instances/setup-webhook")
async def setup_webhook(payload: dict | None = None, request: Request = None):
    """Point the Evolution instance's webhook at this app so inbound messages arrive.

    Defaults to the internal Docker hostname (avoids public-URL loopback from the
    same VPS). Pass {"url": "..."} to override.
    """
    services = request.app.state.services
    cfg = services.whatsapp.get_config()
    if cfg["provider"] != "evolution":
        raise HTTPException(status_code=400, detail="Disponível apenas para Evolution API")
    base = cfg["evolution_url"].rstrip("/")
    instance = cfg["evolution_instance"]
    headers = {"apikey": cfg["evolution_key"]}
    override = (payload or {}).get("url") if payload else None
    if override:
        webhook_url = override.rstrip("/")
    else:
        internal = os.getenv("INTERNAL_WEBHOOK_URL", "http://langrapido:8000/webhook")
        webhook_url = internal
    # Evolution v2 webhook/set payload (nested under "webhook")
    body = {
        "webhook": {
            "enabled": True,
            "url": webhook_url,
            "events": ["MESSAGES_UPSERT"],
            "webhookByEvents": False,
            "base64": False,
        }
    }
    results = {}
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            r = await client.post(f"{base}/webhook/set/{instance}", headers=headers, json=body)
            results["nested"] = {"http": r.status_code, "body": r.text[:200]}
            if r.status_code not in (200, 201):
                # fallback to flat payload (older shape)
                flat = {"enabled": True, "url": webhook_url, "events": ["MESSAGES_UPSERT"], "webhookByEvents": False}
                r2 = await client.post(f"{base}/webhook/set/{instance}", headers=headers, json=flat)
                results["flat"] = {"http": r2.status_code, "body": r2.text[:200]}
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error
    return {"webhook_url": webhook_url, "results": results}


@router.post("/instances/pair")
async def pair_instance(payload: dict, request: Request):
    """Get a WhatsApp pairing code (8 digits) for the number — no QR scan needed."""
    services = request.app.state.services
    cfg = services.whatsapp.get_config()
    if cfg["provider"] != "evolution":
        raise HTTPException(status_code=400, detail="Disponível apenas para Evolution API")
    number = "".join(ch for ch in str(payload.get("number", "")) if ch.isdigit())
    if not number:
        raise HTTPException(status_code=400, detail="Informe o número com DDI e DDD (ex: 5511999998888)")
    base = cfg["evolution_url"].rstrip("/")
    instance = cfg["evolution_instance"]
    headers = {"apikey": cfg["evolution_key"]}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # ensure instance exists
            state = await client.get(
                f"{base}/instance/connectionState/{instance}", headers=headers
            )
            if state.status_code == 404:
                await client.post(
                    f"{base}/instance/create",
                    headers=headers,
                    json={
                        "instanceName": instance,
                        "qrcode": True,
                        "integration": "WHATSAPP-BAILEYS",
                    },
                )
            # request pairing code for the number
            res = await client.get(
                f"{base}/instance/connect/{instance}",
                headers=headers,
                params={"number": number},
            )
        data = res.json() if res.status_code == 200 else {}
        code = data.get("pairingCode") or data.get("code")
        if code:
            return {"status": "ok", "pairingCode": code}
        return {
            "status": "error",
            "detail": f"Evolution não retornou código (status {res.status_code})",
            "raw": str(data)[:200],
        }
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.post("/instances/logout")
async def logout_instance(request: Request):
    services = request.app.state.services
    cfg = services.whatsapp.get_config()
    if cfg["provider"] == "official":
        raise HTTPException(status_code=400, detail="Operação não disponível para canal Oficial")

    url = f"{cfg['evolution_url']}/instance/logout/{cfg['evolution_instance']}"
    headers = {"apikey": cfg["evolution_key"]}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(url, headers=headers)
        if res.status_code == 200:
            return {"status": "ok", "message": "Instância deslogada com sucesso"}
        else:
            # Try delete
            del_url = f"{cfg['evolution_url']}/instance/delete/{cfg['evolution_instance']}"
            async with httpx.AsyncClient(timeout=10) as client:
                del_res = await client.delete(del_url, headers=headers)
            if del_res.status_code == 200:
                return {"status": "ok", "message": "Instância excluída com sucesso"}
            raise HTTPException(status_code=res.status_code, detail="Não foi possível deslogar a instância")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



