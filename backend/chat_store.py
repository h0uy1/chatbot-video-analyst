import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


class ChatStore:
    def __init__(self, db_path=None):
        base_dir = Path(__file__).resolve().parent
        self.db_path = Path(db_path) if db_path else base_dir / "data" / "chat_history.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _initialize(self):
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    file_path TEXT NOT NULL DEFAULT '',
                    response_kind TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_session_id_id
                ON messages(session_id, id)
                """
            )

    def add_message(
        self,
        session_id,
        role,
        content,
        file_path="",
        response_kind="",
    ):
        now = datetime.now(timezone.utc).isoformat()
        clean_session_id = session_id or "default-session"

        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (id, created_at, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (clean_session_id, now, now),
            )
            connection.execute(
                """
                INSERT INTO messages (
                    session_id,
                    role,
                    content,
                    file_path,
                    response_kind,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_session_id,
                    role,
                    content or "",
                    file_path or "",
                    response_kind or "",
                    now,
                ),
            )

    def get_messages(self, session_id):
        with self._lock, self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    id,
                    session_id,
                    role,
                    content,
                    file_path,
                    response_kind,
                    created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id or "default-session",),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_history_text(self, session_id):
        messages = self.get_messages(session_id)
        lines = []

        for message in messages:
            role = message["role"].strip() or "unknown"
            content = message["content"].strip()
            file_path = message["file_path"].strip()

            if not content and not file_path:
                continue

            if file_path:
                lines.append(f"{role}: {content}\nAttached file: {file_path}")
            else:
                lines.append(f"{role}: {content}")

        return "\n\n".join(lines)

    def get_latest_file_path(self, session_id):
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT file_path
                FROM messages
                WHERE session_id = ?
                  AND file_path != ''
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id or "default-session",),
            ).fetchone()

        return row[0] if row else ""

    def clear_history(self):
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM messages")
            connection.execute("DELETE FROM sessions")
