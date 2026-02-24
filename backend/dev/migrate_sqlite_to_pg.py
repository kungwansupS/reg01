"""
Migration script: SQLite → PostgreSQL

Usage:
  cd backend
  python -m dev.migrate_sqlite_to_pg [--sqlite PATH] [--pg DSN]

Defaults:
  --sqlite  memory/sessions.db
  --pg      postgresql://postgres:postgres@localhost:5432/reg01

Steps:
  1. Reads all sessions + messages from the SQLite database
  2. Creates tables in PostgreSQL (same schema as session_db.init_db)
  3. Inserts all data with ON CONFLICT DO NOTHING (safe to re-run)
  4. Prints migration summary
"""

import argparse
import asyncio
import os
import sqlite3
import sys
import logging

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("migrate")

DEFAULT_SQLITE = os.path.join(os.path.dirname(__file__), "..", "memory", "sessions.db")
DEFAULT_PG_DSN = "postgresql://postgres:postgres@localhost:5432/reg01"


# ── Schema (same as session_db._init_tables) ──────────────────────────────

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    user_name   TEXT NOT NULL,
    user_picture TEXT,
    platform    TEXT NOT NULL DEFAULT 'web',
    bot_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id          SERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages(session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_sessions_last_active
    ON sessions(last_active);
"""


async def migrate(sqlite_path: str, pg_dsn: str):
    # ── 1. Read SQLite ────────────────────────────────────────────────────
    if not os.path.exists(sqlite_path):
        logger.error("SQLite file not found: %s", sqlite_path)
        sys.exit(1)

    conn_lite = sqlite3.connect(sqlite_path)
    conn_lite.row_factory = sqlite3.Row

    sessions = conn_lite.execute(
        "SELECT session_id, user_name, user_picture, platform, bot_enabled, created_at, last_active FROM sessions"
    ).fetchall()
    messages = conn_lite.execute(
        "SELECT id, session_id, role, content, created_at FROM messages ORDER BY id"
    ).fetchall()
    conn_lite.close()

    logger.info("Read %d sessions and %d messages from SQLite", len(sessions), len(messages))

    if not sessions:
        logger.warning("No data to migrate — exiting")
        return

    # ── 2. Connect to PostgreSQL & create schema ──────────────────────────
    conn_pg = await asyncpg.connect(pg_dsn)
    logger.info("Connected to PostgreSQL")

    await conn_pg.execute(CREATE_SQL)
    logger.info("Schema ensured (tables + indexes)")

    # ── 3. Insert sessions ────────────────────────────────────────────────
    inserted_sessions = 0
    for s in sessions:
        try:
            await conn_pg.execute(
                """INSERT INTO sessions (session_id, user_name, user_picture, platform, bot_enabled, created_at, last_active)
                   VALUES ($1, $2, $3, $4, $5, $6::timestamptz, $7::timestamptz)
                   ON CONFLICT (session_id) DO NOTHING""",
                s["session_id"],
                s["user_name"],
                s["user_picture"],
                s["platform"],
                bool(s["bot_enabled"]),
                s["created_at"],
                s["last_active"],
            )
            inserted_sessions += 1
        except Exception as e:
            logger.warning("Skip session %s: %s", s["session_id"], e)

    logger.info("Inserted %d / %d sessions", inserted_sessions, len(sessions))

    # ── 4. Insert messages ────────────────────────────────────────────────
    inserted_messages = 0
    for m in messages:
        try:
            await conn_pg.execute(
                """INSERT INTO messages (session_id, role, content, created_at)
                   VALUES ($1, $2, $3, $4::timestamptz)""",
                m["session_id"],
                m["role"],
                m["content"],
                m["created_at"],
            )
            inserted_messages += 1
        except Exception as e:
            logger.warning("Skip message id=%s: %s", m["id"], e)

    logger.info("Inserted %d / %d messages", inserted_messages, len(messages))

    # ── 5. Sync sequences (so SERIAL continues from the right id) ─────────
    max_id = await conn_pg.fetchval("SELECT COALESCE(MAX(id), 0) FROM messages")
    await conn_pg.execute(f"SELECT setval('messages_id_seq', {max_id + 1}, false)")
    logger.info("messages_id_seq reset to %d", max_id + 1)

    await conn_pg.close()

    # ── Summary ──────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  Migration Complete!")
    print(f"  Sessions : {inserted_sessions} / {len(sessions)}")
    print(f"  Messages : {inserted_messages} / {len(messages)}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Migrate sessions.db (SQLite) → PostgreSQL")
    parser.add_argument("--sqlite", default=DEFAULT_SQLITE, help="Path to SQLite file")
    parser.add_argument("--pg", default=DEFAULT_PG_DSN, help="PostgreSQL DSN")
    args = parser.parse_args()

    asyncio.run(migrate(os.path.abspath(args.sqlite), args.pg))


if __name__ == "__main__":
    main()
