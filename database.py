"""
Ava Agent - SQLite Database Layer
Handles conversation storage and retrieval.
"""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager

from config import DB_PATH


def init_db():
    """Initialize the database and create tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_calls TEXT,
                tool_call_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
            ON messages(conversation_id)
        """)
        conn.commit()


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_conversation(title: str = "New Conversation") -> dict:
    """Create a new conversation and return it."""
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (conv_id, title, now, now),
        )
        conn.commit()
    return {"id": conv_id, "title": title, "created_at": now, "updated_at": now}


def list_conversations() -> list[dict]:
    """List all conversations, newest first."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(conv_id: str) -> dict | None:
    """Get a single conversation by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_conversation(conv_id: str) -> bool:
    """Delete a conversation and all its messages."""
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        conn.commit()
        return cursor.rowcount > 0


def rename_conversation(conv_id: str, title: str) -> bool:
    """Rename a conversation."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, conv_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def add_message(conversation_id: str, role: str, content: str,
                tool_calls: list | None = None, tool_call_id: str | None = None) -> dict:
    """Add a message to a conversation."""
    content = content or ""
    now = datetime.now(timezone.utc).isoformat()
    tool_calls_json = json.dumps(tool_calls) if tool_calls else None
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO messages (conversation_id, role, content, tool_calls, tool_call_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (conversation_id, role, content, tool_calls_json, tool_call_id, now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        conn.commit()
        msg_id = cursor.lastrowid
    return {
        "id": msg_id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "tool_calls": tool_calls,
        "tool_call_id": tool_call_id,
        "created_at": now,
    }


def get_messages(conversation_id: str) -> list[dict]:
    """Get all messages for a conversation in order."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
    messages = []
    for r in rows:
        msg = dict(r)
        if msg["tool_calls"]:
            try:
                msg["tool_calls"] = json.loads(msg["tool_calls"])
            except json.JSONDecodeError:
                print(f"WARNING: Corrupt tool_calls JSON in message {msg.get('id')}, conversation {conversation_id}")
                msg["tool_calls"] = None
        messages.append(msg)
    return messages
