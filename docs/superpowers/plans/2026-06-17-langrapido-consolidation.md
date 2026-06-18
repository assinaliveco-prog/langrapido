# LangRápido Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidar o LangRápido em uma única aplicação FastAPI/LangGraph com persistência SQLite, painel operacional responsivo, laboratório seguro e respostas contextualmente humanizadas.

**Architecture:** FastAPI servirá APIs e arquivos estáticos; uma camada de repositório SQLite será a fonte de verdade; `ConversationEngine` será compartilhado pelo webhook e laboratório; o grafo LangGraph ficará restrito à elaboração, crítica, revisão e divisão da resposta. O frontend será HTML/CSS/JavaScript sem etapa de build para manter a implantação simples.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite, LangGraph, LangChain OpenAI, HTTPX, HTML5, CSS3, JavaScript, pytest.

---

## Estrutura de arquivos

Arquivos novos:

- `src/api/schemas.py`: contratos Pydantic da API.
- `src/api/repository.py`: migrações e operações SQLite.
- `src/api/routes_admin.py`: endpoints administrativos.
- `src/api/routes_webhook.py`: endpoints exclusivos da Meta.
- `src/services/conversation.py`: motor compartilhado por webhook e laboratório.
- `src/services/humanization.py`: perfil de estilo, divisão e cálculo de ritmo.
- `src/services/whatsapp.py`: cliente isolado da Meta.
- `src/bot/prompts.py`: composição dos prompts.
- `src/api/static/panel.css`: sistema visual.
- `src/api/static/panel.js`: navegação e integração com API.
- `tests/conftest.py`: banco e app isolados.
- `tests/test_repository.py`: persistência e migrações.
- `tests/test_humanization.py`: regras determinísticas.
- `tests/test_conversation.py`: orquestração sem chamada externa.
- `tests/test_api.py`: contratos administrativos.
- `tests/test_webhook.py`: validação e idempotência.

Arquivos modificados:

- `src/api/server.py`: composição da aplicação.
- `src/api/templates/panel.html`: nova interface.
- `src/bot/agent.py`: grafo com contratos claros.
- `src/bot/state.py`: estado estruturado.
- `src/bot/nodes/drafter.py`: geração adaptativa.
- `src/bot/nodes/critic.py`: avaliação estruturada.
- `src/bot/nodes/splitter.py`: divisão semântica determinística.
- `requirements.txt`: dependências de runtime e testes.
- `.env.example`: configuração documentada.
- `main.py`: entrada estável.

Arquivos legados preservados até a equivalência:

- `server.js`
- `agents.js`
- `humanizer.js`
- `public/`

Eles não serão removidos antes dos testes de equivalência.

### Task 1: Base de testes e configuração

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Create: `tests/conftest.py`
- Create: `tests/test_app_boot.py`

- [ ] **Step 1: Declarar dependências reproduzíveis**

Substituir `requirements.txt` por:

```text
fastapi>=0.115,<1
uvicorn[standard]>=0.30,<1
langgraph>=0.2,<1
langgraph-checkpoint>=2,<3
langchain-openai>=0.2,<1
langchain-core>=0.3,<1
httpx>=0.27,<1
pydantic>=2.8,<3
python-dotenv>=1,<2
pytest>=8,<9
pytest-asyncio>=0.24,<1
```

- [ ] **Step 2: Documentar variáveis operacionais sem segredos**

Usar em `.env.example`:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
VERIFY_TOKEN=
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_API_VERSION=v22.0
DATABASE_PATH=src/api/database.db
ADMIN_HOST=127.0.0.1
ADMIN_PORT=8000
```

- [ ] **Step 3: Escrever teste de inicialização**

```python
# tests/test_app_boot.py
from fastapi.testclient import TestClient


def test_panel_and_health_are_available(client: TestClient):
    panel = client.get("/painel")
    health = client.get("/api/health")

    assert panel.status_code == 200
    assert "LangRápido" in panel.text
    assert health.status_code == 200
    assert health.json()["status"] in {"ready", "degraded"}
```

- [ ] **Step 4: Criar fixture de banco isolado**

```python
# tests/conftest.py
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from src.api.server import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
```

- [ ] **Step 5: Executar o teste e confirmar a falha inicial**

Run: `python -m pytest tests/test_app_boot.py -v`  
Expected: FAIL porque `create_app` e `/api/health` ainda não existem.

- [ ] **Step 6: Registrar checkpoint**

Não há repositório Git em `C:\Users\jvcom\langrapido`. Não inicializar Git automaticamente. Se o usuário inicializar o repositório, usar:

```powershell
git add requirements.txt .env.example tests
git commit -m "test: establish FastAPI test harness"
```

### Task 2: Repositório SQLite e migrações idempotentes

**Files:**
- Create: `src/api/repository.py`
- Create: `src/api/schemas.py`
- Modify: `src/api/db.py`
- Create: `tests/test_repository.py`

- [ ] **Step 1: Escrever testes da persistência**

```python
# tests/test_repository.py
from src.api.repository import Repository


def test_migrations_are_idempotent(tmp_path):
    path = tmp_path / "app.db"
    Repository(path).migrate()
    Repository(path).migrate()

    tables = Repository(path).table_names()
    assert {
        "settings", "contacts", "conversations", "messages",
        "memories", "evaluations", "events", "processed_webhooks"
    }.issubset(tables)


def test_message_round_trip_preserves_relationships(tmp_path):
    repo = Repository(tmp_path / "app.db")
    repo.migrate()
    contact = repo.upsert_contact("5511999999999", "Mariana")
    conversation = repo.get_or_create_conversation(contact["id"], "whatsapp")
    repo.add_message(conversation["id"], "user", "qual o valor?", external_id="wamid.1")

    messages = repo.list_messages(conversation["id"])
    assert messages[0]["text"] == "qual o valor?"
    assert messages[0]["external_id"] == "wamid.1"
```

- [ ] **Step 2: Executar os testes**

Run: `python -m pytest tests/test_repository.py -v`  
Expected: FAIL com `ModuleNotFoundError: src.api.repository`.

- [ ] **Step 3: Criar contratos centrais**

```python
# src/api/schemas.py
from typing import Literal
from pydantic import BaseModel, Field


class AgentSettings(BaseModel):
    agent_name: str = "Rafa"
    role: str = "consultor comercial"
    objective: str = "entender a necessidade e orientar o próximo passo"
    voice: str = "natural, direto e acolhedor"
    formality: Literal["baixa", "media", "alta"] = "media"
    concision: Literal["curta", "equilibrada", "detalhada"] = "equilibrada"
    emoji_mode: Literal["nunca", "espelhar", "leve"] = "espelhar"
    commercial_initiative: int = Field(default=50, ge=0, le=100)
    max_questions: int = Field(default=1, ge=0, le=3)
    split_messages: bool = True
    typo_probability: float = Field(default=0, ge=0, le=0.05)
    preferred_terms: list[str] = []
    forbidden_terms: list[str] = []
    business_rules: str = ""
    model: str = "gpt-4o-mini"


class LabMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class HealthResponse(BaseModel):
    status: Literal["ready", "degraded"]
    database: bool
    ai_configured: bool
    whatsapp_configured: bool
```

- [ ] **Step 4: Implementar migrações e operações mínimas**

`Repository` deve:

```python
class Repository:
    def __init__(self, path: str | Path): ...
    def migrate(self) -> None: ...
    def table_names(self) -> set[str]: ...
    def get_settings(self) -> dict: ...
    def update_settings(self, values: dict) -> dict: ...
    def upsert_contact(self, phone: str, name: str | None = None) -> dict: ...
    def get_or_create_conversation(self, contact_id: int, channel: str) -> dict: ...
    def add_message(
        self,
        conversation_id: int,
        role: str,
        text: str,
        *,
        external_id: str | None = None,
        status: str = "stored",
        metadata: dict | None = None,
    ) -> dict: ...
    def list_messages(self, conversation_id: int, limit: int = 100) -> list[dict]: ...
    def claim_webhook(self, external_id: str) -> bool: ...
    def add_event(self, category: str, level: str, message: str, details: dict | None = None) -> None: ...
```

Usar `sqlite3.Row`, `PRAGMA foreign_keys = ON`, `BEGIN IMMEDIATE` para `claim_webhook`, timestamps UTC e JSON somente para metadados flexíveis.

- [ ] **Step 5: Manter compatibilidade de personalidade**

Modificar `src/api/db.py` para delegar ao novo repositório:

```python
from src.api.repository import get_repository


def get_personality():
    settings = get_repository().get_settings()
    return {
        "system_prompt": settings["business_rules"],
        "slang_level": settings["formality"],
        "use_emojis": settings["emoji_mode"] != "nunca",
    }
```

- [ ] **Step 6: Executar testes**

Run: `python -m pytest tests/test_repository.py -v`  
Expected: 2 passed.

### Task 3: Humanização determinística e segura

**Files:**
- Create: `src/services/__init__.py`
- Create: `src/services/humanization.py`
- Create: `tests/test_humanization.py`

- [ ] **Step 1: Escrever testes das regras**

```python
# tests/test_humanization.py
from src.services.humanization import (
    infer_style,
    split_semantically,
    safe_typo,
    timing_for,
)


def test_short_urgent_message_produces_short_direct_style():
    style = infer_style("preço? preciso disso hj")
    assert style.target_chars <= 180
    assert style.urgency == "high"
    assert style.max_questions == 1


def test_short_message_is_not_split():
    assert split_semantically("sim, consigo te enviar ainda hoje") == [
        "sim, consigo te enviar ainda hoje"
    ]


def test_sensitive_tokens_never_receive_typo():
    text = "Ana, o valor é R$ 2.490 e meu número é 11999998888"
    for seed in range(30):
        changed = safe_typo(text, probability=0.05, seed=seed)
        assert "Ana" in changed
        assert "R$ 2.490" in changed
        assert "11999998888" in changed


def test_timing_is_bounded():
    timing = timing_for("consigo te mostrar duas opções")
    assert 0.4 <= timing.thinking_seconds <= 2.5
    assert 0.8 <= timing.typing_seconds <= 8
```

- [ ] **Step 2: Executar e confirmar falha**

Run: `python -m pytest tests/test_humanization.py -v`  
Expected: FAIL porque o módulo ainda não existe.

- [ ] **Step 3: Implementar tipos e funções puras**

```python
@dataclass(frozen=True)
class ConversationStyle:
    urgency: Literal["low", "normal", "high"]
    target_chars: int
    formality: Literal["low", "medium", "high"]
    mirror_emojis: bool
    max_questions: int


@dataclass(frozen=True)
class MessageTiming:
    thinking_seconds: float
    typing_seconds: float


def infer_style(text: str) -> ConversationStyle: ...
def split_semantically(text: str, max_chunks: int = 3) -> list[str]: ...
def safe_typo(text: str, probability: float, seed: int | None = None) -> str: ...
def timing_for(text: str) -> MessageTiming: ...
```

Regras:

- mensagens com até 40 caracteres ou marcadores `hj`, `agora`, `rápido`, `urgente` recebem alvo de 180 caracteres;
- nunca dividir texto com até 180 caracteres;
- dividir primeiro por parágrafos e depois por fronteiras de frase;
- nunca produzir mais de três blocos;
- proteger URLs, e-mails, números, valores monetários, palavras capitalizadas e tokens com pontuação interna;
- limitar erros a 5%, desabilitados por padrão;
- usar cálculo determinístico quando `seed` for fornecido.

- [ ] **Step 4: Executar testes**

Run: `python -m pytest tests/test_humanization.py -v`  
Expected: 4 passed.

### Task 4: Prompts, estado e grafo revisável

**Files:**
- Create: `src/bot/prompts.py`
- Modify: `src/bot/state.py`
- Modify: `src/bot/nodes/drafter.py`
- Modify: `src/bot/nodes/critic.py`
- Modify: `src/bot/nodes/splitter.py`
- Modify: `src/bot/agent.py`
- Create: `tests/test_agent_graph.py`

- [ ] **Step 1: Testar o roteamento sem LLM**

```python
# tests/test_agent_graph.py
from src.bot.agent import critic_router


def test_approved_draft_routes_to_splitter():
    assert critic_router({"evaluation": {"approved": True}, "revision_count": 1}) == "splitter"


def test_rejected_draft_routes_to_drafter_before_limit():
    assert critic_router({"evaluation": {"approved": False}, "revision_count": 1}) == "drafter"


def test_rejected_draft_stops_revising_at_limit():
    assert critic_router({"evaluation": {"approved": False}, "revision_count": 2}) == "splitter"
```

- [ ] **Step 2: Confirmar falha**

Run: `python -m pytest tests/test_agent_graph.py -v`  
Expected: FAIL porque o roteador atual depende de texto em `critic_feedback`.

- [ ] **Step 3: Definir estado explícito**

```python
class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], operator.add]
    conversation_id: int
    user_phone: str
    settings: dict
    memories: list[dict]
    style: dict
    current_draft: str
    candidates: list[str]
    evaluation: dict
    messages_to_send: list[str]
    revision_count: int
```

- [ ] **Step 4: Centralizar prompts**

`src/bot/prompts.py` deve fornecer:

```python
def build_drafter_prompt(settings: dict, style: dict, memories: list[dict]) -> str: ...
def build_critic_prompt(settings: dict) -> str: ...
```

O prompt do elaborador deve incluir:

- responder primeiro ao conteúdo explícito;
- no máximo `max_questions`;
- não repetir dados presentes em memória;
- respeitar `forbidden_terms`;
- não alegar ser humano nem mentir sobre identidade quando perguntado;
- não usar clichês listados;
- retornar somente a mensagem destinada ao contato.

- [ ] **Step 5: Tornar a crítica estruturada**

```python
class CriticEvaluation(BaseModel):
    approved: bool
    naturalness: int = Field(ge=0, le=10)
    relevance: int = Field(ge=0, le=10)
    concision: int = Field(ge=0, le=10)
    coherence: int = Field(ge=0, le=10)
    repetition: int = Field(ge=0, le=10)
    issues: list[str]
    revision_instruction: str
```

Aprovar somente se relevância e coerência forem pelo menos 8, naturalidade pelo menos 7 e não houver problema crítico.

- [ ] **Step 6: Remover LLM do splitter**

`splitter_node` deve chamar `split_semantically(current_draft)` diretamente. Isso elimina custo, latência e variação em uma tarefa determinística.

- [ ] **Step 7: Corrigir roteamento**

```python
MAX_REVISIONS = 2


def critic_router(state: AgentState) -> str:
    evaluation = state.get("evaluation", {})
    if evaluation.get("approved") or state.get("revision_count", 0) >= MAX_REVISIONS:
        return "splitter"
    return "drafter"
```

- [ ] **Step 8: Executar testes**

Run: `python -m pytest tests/test_agent_graph.py tests/test_humanization.py -v`  
Expected: todos passam.

### Task 5: Motor compartilhado, memória e laboratório

**Files:**
- Create: `src/services/conversation.py`
- Create: `tests/test_conversation.py`

- [ ] **Step 1: Escrever teste com gerador falso**

```python
# tests/test_conversation.py
import pytest

from src.api.repository import Repository
from src.services.conversation import ConversationEngine


class FakeGenerator:
    async def respond(self, context):
        assert context["messages"][-1]["text"] == "meu orçamento é 5 mil"
        return {
            "draft": "entendi, com 5 mil dá pra trabalhar algumas opções",
            "evaluation": {"approved": True, "issues": []},
            "messages": ["entendi, com 5 mil dá pra trabalhar algumas opções"],
        }


@pytest.mark.asyncio
async def test_engine_persists_input_output_and_memory(tmp_path):
    repo = Repository(tmp_path / "app.db")
    repo.migrate()
    engine = ConversationEngine(repo, FakeGenerator())

    result = await engine.handle_lab_message("session-1", "meu orçamento é 5 mil")

    assert result.messages[0].startswith("entendi")
    assert repo.find_memory("session-1", "budget")["value"] == "5 mil"
    assert len(repo.list_session_messages("session-1")) == 2
```

- [ ] **Step 2: Confirmar falha**

Run: `python -m pytest tests/test_conversation.py -v`  
Expected: FAIL porque o motor não existe.

- [ ] **Step 3: Implementar interface do gerador e resultado**

```python
class ResponseGenerator(Protocol):
    async def respond(self, context: dict) -> dict: ...


class ConversationResult(BaseModel):
    messages: list[str]
    draft: str
    evaluation: dict
    timings: list[dict]
```

- [ ] **Step 4: Implementar fluxo transacional**

`ConversationEngine` deverá:

- persistir entrada antes de chamar o gerador;
- montar contexto com mensagens recentes, settings e memórias;
- persistir cada saída;
- extrair memórias explícitas por regras seguras para nome, orçamento, e-mail e telefone;
- registrar evento de erro e manter a entrada em caso de falha;
- expor métodos separados `handle_lab_message` e `handle_whatsapp_message` sobre um `_handle` comum.

- [ ] **Step 5: Executar teste**

Run: `python -m pytest tests/test_conversation.py -v`  
Expected: 1 passed.

### Task 6: Cliente WhatsApp e webhook idempotente

**Files:**
- Create: `src/services/whatsapp.py`
- Create: `src/api/routes_webhook.py`
- Modify: `src/bot/whatsapp.py`
- Create: `tests/test_webhook.py`

- [ ] **Step 1: Escrever testes de verificação e duplicidade**

```python
# tests/test_webhook.py
def test_webhook_verification(client, monkeypatch):
    monkeypatch.setenv("VERIFY_TOKEN", "secret")
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "secret",
            "hub.challenge": "42",
        },
    )
    assert response.status_code == 200
    assert response.json() == 42


def test_duplicate_message_is_acknowledged_once(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "src.api.routes_webhook.enqueue_message",
        lambda *args, **kwargs: calls.append(args),
    )
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [{
            "id": "wamid.same",
            "from": "5511999999999",
            "type": "text",
            "text": {"body": "oi"},
        }]}}]}],
    }
    assert client.post("/webhook", json=payload).status_code == 200
    assert client.post("/webhook", json=payload).status_code == 200
    assert len(calls) == 1
```

- [ ] **Step 2: Confirmar falha**

Run: `python -m pytest tests/test_webhook.py -v`  
Expected: FAIL porque o roteador novo ainda não existe.

- [ ] **Step 3: Implementar cliente com injeção de HTTP**

```python
class WhatsAppClient:
    def __init__(self, token: str, phone_number_id: str, api_version: str, http: httpx.AsyncClient): ...
    @property
    def configured(self) -> bool: ...
    async def mark_read(self, message_id: str) -> dict: ...
    async def send_text(self, to: str, text: str) -> dict: ...
```

Usar timeout de 15 segundos, `raise_for_status` e mensagens de erro sem incluir token.

- [ ] **Step 4: Implementar extração tolerante do webhook**

Separar:

```python
def iter_text_messages(payload: dict) -> Iterator[IncomingWhatsAppMessage]: ...
def enqueue_message(background_tasks, message, services) -> None: ...
```

Reivindicar `message.id` por `Repository.claim_webhook` antes de enfileirar.

- [ ] **Step 5: Manter adaptadores antigos**

`src/bot/whatsapp.py` deve delegar ao cliente novo para não quebrar importações durante a migração.

- [ ] **Step 6: Executar testes**

Run: `python -m pytest tests/test_webhook.py -v`  
Expected: 2 passed.

### Task 7: API administrativa e composição da aplicação

**Files:**
- Create: `src/api/routes_admin.py`
- Modify: `src/api/server.py`
- Modify: `main.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Testar contratos e proteção de segredos**

```python
# tests/test_api.py
def test_settings_round_trip(client):
    original = client.get("/api/settings").json()
    original["agent_name"] = "Nina"
    saved = client.put("/api/settings", json=original)
    assert saved.status_code == 200
    assert client.get("/api/settings").json()["agent_name"] == "Nina"


def test_health_never_returns_secrets(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "super-secret")
    monkeypatch.setenv("WHATSAPP_TOKEN", "also-secret")
    payload = client.get("/api/health").text
    assert "super-secret" not in payload
    assert "also-secret" not in payload


def test_lab_session_does_not_require_whatsapp(client):
    created = client.post("/api/lab/sessions", json={"name": "Teste"})
    assert created.status_code == 201
```

- [ ] **Step 2: Confirmar falha**

Run: `python -m pytest tests/test_api.py -v`  
Expected: FAIL por ausência das rotas.

- [ ] **Step 3: Criar fábrica da aplicação**

```python
def create_app() -> FastAPI:
    app = FastAPI(title="LangRápido", version="2.0.0")
    app.state.repository = get_repository()
    app.state.repository.migrate()
    app.include_router(admin_router)
    app.include_router(webhook_router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
```

- [ ] **Step 4: Implementar endpoints administrativos**

Implementar os contratos da spec:

```text
GET    /api/health
GET    /api/dashboard
GET    /api/settings
PUT    /api/settings
GET    /api/contacts
GET    /api/contacts/{id}
GET    /api/conversations/{id}/messages
POST   /api/lab/sessions
POST   /api/lab/sessions/{id}/messages
DELETE /api/lab/sessions/{id}
GET    /api/events
```

`/api/lab/sessions/{id}/messages` deve retornar `503` com erro legível quando a chave de IA estiver ausente, preservando a mensagem recebida.

- [ ] **Step 5: Executar suíte de API**

Run: `python -m pytest tests/test_app_boot.py tests/test_api.py tests/test_webhook.py -v`  
Expected: todos passam.

### Task 8: Painel operacional

**Files:**
- Replace: `src/api/templates/panel.html`
- Create: `src/api/static/panel.css`
- Create: `src/api/static/panel.js`

- [ ] **Step 1: Construir a estrutura sem dependências CDN**

O HTML deve conter:

```html
<div class="app-shell">
  <aside class="sidebar" aria-label="Navegação principal">...</aside>
  <main class="workspace">
    <section data-view="overview">...</section>
    <section data-view="conversations" hidden>...</section>
    <section data-view="lab" hidden>...</section>
    <section data-view="personality" hidden>...</section>
    <section data-view="integrations" hidden>...</section>
    <section data-view="events" hidden>...</section>
  </main>
</div>
```

Usar SVG inline para ícones e preservar rótulos textuais.

- [ ] **Step 2: Implementar tokens visuais**

```css
:root {
  --canvas: #111310;
  --surface-1: #181b17;
  --surface-2: #20241f;
  --surface-3: #292e27;
  --line: #343a32;
  --text: #f2f1ea;
  --muted: #a6aa9f;
  --accent: #b8f36b;
  --accent-ink: #17200e;
  --warning: #e9b95f;
  --danger: #ef786f;
  --radius-sm: 8px;
  --radius-md: 14px;
  --radius-lg: 20px;
}
```

Diretrizes:

- largura da sidebar: 248px;
- cabeçalho da área: 72px;
- cartões sem transparência;
- foco com outline de 2px;
- transições limitadas a 180ms;
- `prefers-reduced-motion` desabilita movimento;
- em até 900px, sidebar vira barra inferior;
- em até 1180px, conversas passam de três para duas colunas e o contexto vira drawer.

- [ ] **Step 3: Implementar cliente de API**

```javascript
const api = {
  async request(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Não foi possível concluir a operação");
    return payload;
  },
};
```

O JavaScript deve:

- trocar views com histórico e estado de foco;
- carregar dashboard e health;
- listar contatos e mensagens;
- editar settings com feedback inline, sem `alert`;
- criar e limpar sessões do laboratório;
- mostrar rascunho, crítica e mensagens finais;
- filtrar eventos;
- renderizar estados loading, empty e error;
- escapar todo texto vindo da API usando `textContent`.

- [ ] **Step 4: Verificar sintaxe e carregamento**

Run: `python -m compileall src`  
Expected: exit 0.

Run: `python main.py`  
Expected: servidor em `http://127.0.0.1:8000`.

### Task 9: Equivalência, remoção de ambiguidade e testes completos

**Files:**
- Modify: `README.md` if present; otherwise create `README.md`
- Modify: `PLAN.md`
- Create: `legacy-node/README.md`
- Move after verification: `server.js`, `agents.js`, `humanizer.js`, `public/`, `package.json`, `package-lock.json`, `db.json`

- [ ] **Step 1: Criar matriz de equivalência**

Registrar em `legacy-node/README.md`:

```markdown
| Recurso Node | Destino Python | Evidência |
|---|---|---|
| Configuração do agente | `/api/settings` | `tests/test_api.py` |
| Simulador manual | `/api/lab/sessions/*` | `tests/test_conversation.py` |
| Divisão em mensagens | `services/humanization.py` | `tests/test_humanization.py` |
| CRM por lead | repository contacts/memories | `tests/test_repository.py` |
| Histórico | conversations/messages | `tests/test_repository.py` |
```

- [ ] **Step 2: Executar suíte completa**

Run: `python -m pytest -v`  
Expected: todos os testes passam sem rede e sem credenciais reais.

- [ ] **Step 3: Executar auditoria de codificação**

Run:

```powershell
rg "Ã.|ðŸ|â€|âœ|âš" src tests docs -g "*.py" -g "*.html" -g "*.css" -g "*.js" -g "*.md"
```

Expected: nenhuma ocorrência de mojibake em arquivos ativos.

- [ ] **Step 4: Mover legado somente após equivalência**

Criar `legacy-node/` e mover os arquivos Node preservando histórico e dados. Antes de qualquer movimento, resolver e conferir que todos os caminhos estão dentro de `C:\Users\jvcom\langrapido`.

- [ ] **Step 5: Atualizar documentação operacional**

O README deve explicar:

```text
1. python -m venv .venv
2. .venv\Scripts\Activate.ps1
3. pip install -r requirements.txt
4. copiar .env.example para .env
5. python main.py
6. abrir http://127.0.0.1:8000/painel
```

- [ ] **Step 6: Verificar que existe uma única entrada ativa**

Run:

```powershell
rg "listen\\(|express\\(|uvicorn.run|FastAPI\\(" -g "!legacy-node/**" -g "!node_modules/**"
```

Expected: apenas a aplicação FastAPI e sua entrada `main.py` aparecem como runtime ativo.

### Task 10: Validação visual e conversacional

**Files:**
- Create: `tests/fixtures/conversation_scenarios.json`
- Create: `tests/test_quality_scenarios.py`

- [ ] **Step 1: Definir cenários fixos**

O fixture deve conter oito cenários:

```json
[
  {"id":"price","message":"qual o valor?","must_address":["valor"],"max_chars":220},
  {"id":"urgent","message":"preciso disso hj, consegue?","must_address":["hoje"],"max_chars":180},
  {"id":"distrust","message":"isso parece bom demais, qual a pegadinha?","max_questions":1},
  {"id":"objection","message":"tá caro pra mim","must_acknowledge":true},
  {"id":"personal","message":"tô cuidando da minha mãe e sem muito tempo","must_acknowledge":true},
  {"id":"resume","history":["falamos do plano básico ontem"],"message":"podemos continuar?","must_not_ask":["qual plano"]},
  {"id":"known_info","history":["meu orçamento é 5 mil"],"message":"o que dá pra fazer?","must_not_ask":["orçamento"]},
  {"id":"out_of_scope","message":"você pode resolver meu imposto?","must_acknowledge":true}
]
```

- [ ] **Step 2: Criar validações determinísticas**

Os testes devem validar limites de tamanho, quantidade de `?`, termos proibidos e repetição de perguntas conhecidas usando um gerador fixture. Avaliações qualitativas dependentes de LLM devem ser marcadas `@pytest.mark.integration` e não bloquear a suíte offline.

- [ ] **Step 3: Validar navegador**

Com o servidor local ativo, verificar:

- `1440x900`: todas as seis views, conversa em três colunas e formulário;
- `1024x768`: ausência de sobreposição e contexto acessível;
- `390x844`: navegação inferior, conteúdo rolável e botões alcançáveis;
- teclado: navegação, foco e envio do laboratório;
- estados sem dados, erro 503 de IA e salvamento bem-sucedido;
- console sem erros.

- [ ] **Step 4: Auditoria final**

Executar:

```powershell
python -m pytest -v
python -m compileall src
```

Confirmar manualmente:

- painel usa apenas o FastAPI;
- laboratório e webhook usam `ConversationEngine`;
- dados persistem após reiniciar o servidor;
- nenhum segredo é exibido;
- legado Node está fora do runtime ativo;
- todos os critérios da spec possuem evidência.

