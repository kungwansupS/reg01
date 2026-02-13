import sqlite3
import threading
from pathlib import Path
from typing import Any, List, Tuple


class SessionStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_session_time
                ON messages (session_id, created_at DESC)
                """
            )
            conn.commit()

    def append_message(self, session_id: str, platform: str, role: str, text: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO messages(session_id, platform, role, text) VALUES (?, ?, ?, ?)",
                    (session_id, platform, role, text),
                )
                conn.commit()

    def get_recent_messages(self, session_id: str, limit: int = 12) -> List[Tuple[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, text
                FROM messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        # reverse to chronological order
        return [(row["role"], row["text"]) for row in reversed(rows)]

    def get_history(self, session_id: str, limit: int = 200) -> List[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, text, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [
            {
                "role": row["role"],
                "parts": [{"text": row["text"]}],
                "timestamp": row["created_at"],
            }
            for row in rows
        ]

    def list_sessions(self, limit: int = 300) -> List[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id, platform, MAX(id) AS last_id, MAX(created_at) AS last_active
                FROM messages
                GROUP BY session_id, platform
                ORDER BY last_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result: List[dict[str, Any]] = []
        for row in rows:
            sid = row["session_id"]
            platform = row["platform"]
            result.append(
                {
                    "id": sid,
                    "platform": platform,
                    "profile": {
                        "name": f"{platform.title()} {sid[:8]}",
                        "picture": "https://www.gravatar.com/avatar/?d=mp",
                    },
                    "bot_enabled": True,
                    "last_active": row["last_active"],
                }
            )
        return result
