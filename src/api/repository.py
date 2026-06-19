from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from src.api.schemas import AgentSettings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            agent_name TEXT NOT NULL,
            role TEXT NOT NULL,
            objective TEXT NOT NULL,
            voice TEXT NOT NULL,
            formality TEXT NOT NULL,
            concision TEXT NOT NULL,
            emoji_mode TEXT NOT NULL,
            commercial_initiative INTEGER NOT NULL,
            max_questions INTEGER NOT NULL,
            split_messages INTEGER NOT NULL,
            typo_probability REAL NOT NULL,
            preferred_terms TEXT NOT NULL,
            forbidden_terms TEXT NOT NULL,
            business_rules TEXT NOT NULL,
            system_prompt TEXT NOT NULL DEFAULT '',
            whatsapp_provider TEXT NOT NULL DEFAULT 'official',
            evolution_url TEXT NOT NULL DEFAULT '',
            evolution_key TEXT NOT NULL DEFAULT '',
            evolution_instance TEXT NOT NULL DEFAULT '',
            openai_api_key TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL UNIQUE,
            name TEXT,
            email TEXT,
            interest TEXT NOT NULL DEFAULT 'indefinido',
            budget TEXT,
            summary TEXT,
            next_action TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            channel TEXT NOT NULL,
            external_thread_id TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_conversations_contact
            ON conversations(contact_id, updated_at DESC);

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            external_id TEXT UNIQUE,
            status TEXT NOT NULL DEFAULT 'stored',
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id, id);

        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 1,
            source_message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(contact_id, key)
        );

        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            draft TEXT NOT NULL,
            approved INTEGER NOT NULL,
            scores TEXT NOT NULL DEFAULT '{}',
            issues TEXT NOT NULL DEFAULT '[]',
            revision_instruction TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS processed_webhooks (
            external_id TEXT PRIMARY KEY,
            processed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS lab_sessions (
            id TEXT PRIMARY KEY,
            contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS flows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            trigger_intent TEXT NOT NULL,
            steps TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
        defaults = AgentSettings().model_dump()
        with self.connect() as connection:
            connection.executescript(schema)
            # Add columns to existing databases that may not have them
            migrations = [
                "ALTER TABLE settings ADD COLUMN system_prompt TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE settings ADD COLUMN whatsapp_provider TEXT NOT NULL DEFAULT 'official'",
                "ALTER TABLE settings ADD COLUMN evolution_url TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE settings ADD COLUMN evolution_key TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE settings ADD COLUMN evolution_instance TEXT NOT NULL DEFAULT ''",
                "ALTER TABLE settings ADD COLUMN openai_api_key TEXT NOT NULL DEFAULT ''",
            ]
            for statement in migrations:
                try:
                    connection.execute(statement)
                except Exception:
                    pass  # Column already exists
            connection.execute(
                """
                INSERT OR IGNORE INTO settings (
                    id, agent_name, role, objective, voice, formality, concision,
                    emoji_mode, commercial_initiative, max_questions,
                    split_messages, typo_probability, preferred_terms,
                    forbidden_terms, business_rules, system_prompt,
                    whatsapp_provider, evolution_url, evolution_key, evolution_instance,
                    openai_api_key, model, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    defaults["agent_name"],
                    defaults["role"],
                    defaults["objective"],
                    defaults["voice"],
                    defaults["formality"],
                    defaults["concision"],
                    defaults["emoji_mode"],
                    defaults["commercial_initiative"],
                    defaults["max_questions"],
                    int(defaults["split_messages"]),
                    defaults["typo_probability"],
                    json.dumps(defaults["preferred_terms"], ensure_ascii=False),
                    json.dumps(defaults["forbidden_terms"], ensure_ascii=False),
                    defaults["business_rules"],
                    defaults["system_prompt"],
                    defaults["whatsapp_provider"],
                    defaults["evolution_url"],
                    defaults["evolution_key"],
                    defaults["evolution_instance"],
                    defaults["openai_api_key"],
                    os.getenv("OPENAI_MODEL", defaults["model"]),
                    utc_now(),
                ),
            )

    def table_names(self) -> set[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        return {row["name"] for row in rows}

    @staticmethod
    def _settings_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data.pop("id", None)
        data.pop("updated_at", None)
        data["split_messages"] = bool(data["split_messages"])
        data["preferred_terms"] = json.loads(data["preferred_terms"] or "[]")
        data["forbidden_terms"] = json.loads(data["forbidden_terms"] or "[]")
        return data

    def get_settings(self) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        if row is None:
            self.migrate()
            return self.get_settings()
        return self._settings_dict(row)

    def update_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        current = self.get_settings()
        # Secrets are returned to the client masked (containing '…'/'•'). When the
        # client sends a masked or empty secret back, keep the stored real value
        # instead of overwriting it with the mask.
        values = dict(values)
        for secret in ("openai_api_key", "evolution_key"):
            incoming = values.get(secret)
            if incoming is None or incoming == "" or "…" in str(incoming) or "•" in str(incoming):
                values[secret] = current.get(secret, "")
        validated = AgentSettings.model_validate({**current, **values}).model_dump()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE settings SET
                    agent_name = ?, role = ?, objective = ?, voice = ?,
                    formality = ?, concision = ?, emoji_mode = ?,
                    commercial_initiative = ?, max_questions = ?,
                    split_messages = ?, typo_probability = ?,
                    preferred_terms = ?, forbidden_terms = ?,
                    business_rules = ?, system_prompt = ?,
                    whatsapp_provider = ?, evolution_url = ?,
                    evolution_key = ?, evolution_instance = ?,
                    openai_api_key = ?,
                    model = ?, updated_at = ?
                WHERE id = 1
                """,
                (
                    validated["agent_name"],
                    validated["role"],
                    validated["objective"],
                    validated["voice"],
                    validated["formality"],
                    validated["concision"],
                    validated["emoji_mode"],
                    validated["commercial_initiative"],
                    validated["max_questions"],
                    int(validated["split_messages"]),
                    validated["typo_probability"],
                    json.dumps(validated["preferred_terms"], ensure_ascii=False),
                    json.dumps(validated["forbidden_terms"], ensure_ascii=False),
                    validated["business_rules"],
                    validated["system_prompt"],
                    validated["whatsapp_provider"],
                    validated["evolution_url"],
                    validated["evolution_key"],
                    validated["evolution_instance"],
                    validated["openai_api_key"],
                    validated["model"],
                    utc_now(),
                ),
            )
        return self.get_settings()

    def upsert_contact(self, phone: str, name: str | None = None) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO contacts (phone, name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(phone) DO UPDATE SET
                    name = COALESCE(excluded.name, contacts.name),
                    updated_at = excluded.updated_at
                """,
                (phone, name, now, now),
            )
            row = connection.execute(
                "SELECT * FROM contacts WHERE phone = ?", (phone,)
            ).fetchone()
        return dict(row)

    def get_contact(self, contact_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM contacts WHERE id = ?", (contact_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_contacts(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT contacts.*, (
                    SELECT conversations.id FROM conversations
                    WHERE conversations.contact_id = contacts.id
                    ORDER BY conversations.updated_at DESC, conversations.id DESC
                    LIMIT 1
                ) AS conversation_id
                FROM contacts
                ORDER BY contacts.updated_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def dashboard_stats(self) -> dict[str, Any]:
        with self.connect() as connection:
            contacts = connection.execute(
                "SELECT COUNT(*) AS count FROM contacts"
            ).fetchone()["count"]
            open_conversations = connection.execute(
                "SELECT COUNT(*) AS count FROM conversations WHERE status = 'open'"
            ).fetchone()["count"]
            messages = connection.execute(
                "SELECT COUNT(*) AS count FROM messages"
            ).fetchone()["count"]
            failures = connection.execute(
                "SELECT COUNT(*) AS count FROM events WHERE level = 'error'"
            ).fetchone()["count"]
        return {
            "contacts": contacts,
            "open_conversations": open_conversations,
            "messages": messages,
            "failures": failures,
        }

    def get_or_create_conversation(
        self,
        contact_id: int,
        channel: str,
        external_thread_id: str | None = None,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM conversations
                WHERE contact_id = ? AND channel = ? AND status = 'open'
                ORDER BY id DESC LIMIT 1
                """,
                (contact_id, channel),
            ).fetchone()
            if row is None:
                now = utc_now()
                cursor = connection.execute(
                    """
                    INSERT INTO conversations (
                        contact_id, channel, external_thread_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (contact_id, channel, external_thread_id, now, now),
                )
                row = connection.execute(
                    "SELECT * FROM conversations WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
        return dict(row)

    def add_message(
        self,
        conversation_id: int,
        role: str,
        text: str,
        *,
        external_id: str | None = None,
        status: str = "stored",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages (
                    conversation_id, role, text, external_id, status, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    role,
                    text,
                    external_id,
                    status,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    utc_now(),
                ),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (utc_now(), conversation_id),
            )
            row = connection.execute(
                "SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        result = dict(row)
        result["metadata"] = json.loads(result["metadata"])
        return result

    def list_messages(
        self, conversation_id: int, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM (
                    SELECT * FROM messages
                    WHERE conversation_id = ?
                    ORDER BY id DESC LIMIT ?
                ) ORDER BY id
                """,
                (conversation_id, limit),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"])
            result.append(item)
        return result

    def upsert_memory(
        self,
        contact_id: int,
        key: str,
        value: str,
        *,
        confidence: float = 1.0,
        source_message_id: int | None = None,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    contact_id, key, value, confidence, source_message_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(contact_id, key) DO UPDATE SET
                    value = excluded.value,
                    confidence = excluded.confidence,
                    source_message_id = excluded.source_message_id,
                    updated_at = excluded.updated_at
                """,
                (
                    contact_id,
                    key,
                    value,
                    confidence,
                    source_message_id,
                    utc_now(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM memories WHERE contact_id = ? AND key = ?",
                (contact_id, key),
            ).fetchone()
        return dict(row)

    def find_memory(self, contact_id: int, key: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM memories WHERE contact_id = ? AND key = ?",
                (contact_id, key),
            ).fetchone()
        return dict(row) if row else None

    def list_memories(self, contact_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM memories WHERE contact_id = ? ORDER BY updated_at DESC",
                (contact_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def claim_webhook(self, external_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO processed_webhooks (external_id, processed_at)
                VALUES (?, ?)
                """,
                (external_id, utc_now()),
            )
        return cursor.rowcount == 1

    def add_event(
        self,
        category: str,
        level: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO events (category, level, message, details, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    category,
                    level,
                    message,
                    json.dumps(details or {}, ensure_ascii=False),
                    utc_now(),
                ),
            )

    def list_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item["details"])
            events.append(item)
        return events

    def add_evaluation(
        self,
        conversation_id: int,
        draft: str,
        evaluation: dict[str, Any],
    ) -> dict[str, Any]:
        scores = {
            key: evaluation[key]
            for key in (
                "naturalness",
                "relevance",
                "concision",
                "coherence",
                "repetition",
            )
            if key in evaluation
        }
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO evaluations (
                    conversation_id, draft, approved, scores, issues,
                    revision_instruction, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    draft,
                    int(bool(evaluation.get("approved"))),
                    json.dumps(scores, ensure_ascii=False),
                    json.dumps(evaluation.get("issues", []), ensure_ascii=False),
                    evaluation.get("revision_instruction", ""),
                    utc_now(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM evaluations WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return dict(row)

    def create_lab_session(self, name: str) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        contact = self.upsert_contact(f"lab:{session_id}", name)
        conversation = self.get_or_create_conversation(
            contact["id"],
            "lab",
            external_thread_id=session_id,
        )
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO lab_sessions (id, contact_id, name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, contact["id"], name, utc_now()),
            )
        return {
            "id": session_id,
            "contact_id": contact["id"],
            "conversation_id": conversation["id"],
            "name": name,
        }

    def get_lab_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    lab_sessions.id,
                    lab_sessions.contact_id,
                    lab_sessions.name,
                    conversations.id AS conversation_id,
                    lab_sessions.created_at
                FROM lab_sessions
                JOIN conversations
                    ON conversations.contact_id = lab_sessions.contact_id
                    AND conversations.channel = 'lab'
                    AND conversations.status = 'open'
                WHERE lab_sessions.id = ?
                ORDER BY conversations.id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def delete_lab_session(self, session_id: str) -> bool:
        session = self.get_lab_session(session_id)
        if session is None:
            return False
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM contacts WHERE id = ?", (session["contact_id"],)
            )
        return True

    def add_flow(
        self, name: str, trigger_intent: str, steps: list[dict[str, Any]]
    ) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO flows (name, trigger_intent, steps, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    trigger_intent,
                    json.dumps(steps, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM flows WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        result = dict(row)
        result["steps"] = json.loads(result["steps"])
        return result

    def get_flow(self, flow_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM flows WHERE id = ?", (flow_id,)
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["steps"] = json.loads(result["steps"])
        return result

    def update_flow(
        self,
        flow_id: int,
        name: str,
        trigger_intent: str,
        steps: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE flows SET
                    name = ?, trigger_intent = ?, steps = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    name,
                    trigger_intent,
                    json.dumps(steps, ensure_ascii=False),
                    now,
                    flow_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM flows WHERE id = ?", (flow_id,)
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["steps"] = json.loads(result["steps"])
        return result

    def delete_flow(self, flow_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM flows WHERE id = ?", (flow_id,)
            )
        return cursor.rowcount > 0

    def list_flows(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM flows ORDER BY name ASC"
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["steps"] = json.loads(item["steps"])
            result.append(item)
        return result


_repositories: dict[str, Repository] = {}


def get_repository() -> Repository:
    path = os.getenv(
        "DATABASE_PATH",
        str(Path(__file__).with_name("database.db")),
    )
    normalized = str(Path(path).resolve())
    if normalized not in _repositories:
        repository = Repository(normalized)
        repository.migrate()
        _repositories[normalized] = repository
    return _repositories[normalized]
