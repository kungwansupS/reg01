import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

import asyncpg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection pool (initialized at app startup via init_db / closed via close_db)
# ---------------------------------------------------------------------------
_pool: Optional[asyncpg.Pool] = None


async def init_db(dsn: str, min_size: int = 2, max_size: int = 10):
    """
    สร้าง connection pool และ tables
    เรียกครั้งเดียวตอน application startup (main.py)
    """
    global _pool
    _pool = await asyncpg.create_pool(dsn=dsn, min_size=min_size, max_size=max_size)
    await _init_tables()
    logger.info("✅ PostgreSQL pool initialized (min=%d, max=%d)", min_size, max_size)


async def close_db():
    """ปิด connection pool — เรียกตอน shutdown"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("✅ PostgreSQL pool closed")


def _get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database not initialized — call init_db() first")
    return _pool


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

async def _init_tables():
    """สร้างตารางในฐานข้อมูล (idempotent)"""
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id  TEXT PRIMARY KEY,
                user_name   TEXT NOT NULL,
                user_picture TEXT,
                platform    TEXT NOT NULL DEFAULT 'web',
                bot_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_active TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id          SERIAL PRIMARY KEY,
                session_id  TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id, created_at)
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_last_active
            ON sessions(last_active)
        """)


# ---------------------------------------------------------------------------
# SessionDatabase — async methods (same public API as the old SQLite version)
# ---------------------------------------------------------------------------

class SessionDatabase:
    """
    จัดการ Sessions ผ่าน PostgreSQL Database (asyncpg)

    โครงสร้างตาราง:
    - sessions: เก็บข้อมูล session, user info, และ settings
    - messages: เก็บประวัติการสนทนา
    """

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _pool() -> asyncpg.Pool:
        return _get_pool()

    # -- session CRUD -----------------------------------------------------

    async def get_or_create_session(
        self,
        session_id: str,
        user_name: Optional[str] = None,
        user_picture: Optional[str] = None,
        platform: str = "web",
    ) -> Dict:
        """
        ดึงหรือสร้าง session ใหม่

        Returns:
            Dict ที่มี session info และ history
        """
        pool = self._pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM sessions WHERE session_id = $1", session_id
            )

            if row:
                # อัปเดต last_active + user info ถ้ามีการส่งมา
                sets = ["last_active = NOW()"]
                vals: list = []
                idx = 1
                if user_name:
                    idx += 1
                    sets.append(f"user_name = ${idx}")
                    vals.append(user_name)
                if user_picture:
                    idx += 1
                    sets.append(f"user_picture = ${idx}")
                    vals.append(user_picture)
                await conn.execute(
                    f"UPDATE sessions SET {', '.join(sets)} WHERE session_id = $1",
                    session_id,
                    *vals,
                )
                session_info = dict(row)
            else:
                # สร้าง session ใหม่
                is_fb = session_id.startswith("fb_")
                detected_platform = platform or ("facebook" if is_fb else "web")
                clean_uid = session_id.replace("fb_", "")

                default_name = user_name or f"{detected_platform.capitalize()} User {clean_uid[:5]}"
                default_picture = user_picture or "https://www.gravatar.com/avatar/?d=mp"

                await conn.execute(
                    """INSERT INTO sessions (session_id, user_name, user_picture, platform, bot_enabled)
                       VALUES ($1, $2, $3, $4, TRUE)""",
                    session_id, default_name, default_picture, detected_platform,
                )

                session_info = {
                    "session_id": session_id,
                    "user_name": default_name,
                    "user_picture": default_picture,
                    "platform": detected_platform,
                    "bot_enabled": True,
                }

        # ดึงประวัติการสนทนา
        history = await self.get_history(session_id)

        return {"session_info": session_info, "history": history}

    # -- history ----------------------------------------------------------

    async def get_history(self, session_id: str, limit: int = 30) -> List[Dict]:
        """
        ดึงประวัติการสนทนา

        Returns:
            List of messages ในรูปแบบ [{"role": "user", "parts": [{"text": "..."}]}]
        """
        pool = self._pool()
        rows = await pool.fetch(
            """SELECT role, content FROM messages
               WHERE session_id = $1
               ORDER BY created_at ASC
               LIMIT $2""",
            session_id, limit,
        )
        return [
            {"role": r["role"], "parts": [{"text": r["content"]}]}
            for r in rows
        ]

    async def add_message(self, session_id: str, role: str, content: str):
        """เพิ่มข้อความใหม่"""
        pool = self._pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES ($1, $2, $3)",
                session_id, role, content,
            )
            await conn.execute(
                "UPDATE sessions SET last_active = NOW() WHERE session_id = $1",
                session_id,
            )

    # -- bot toggle -------------------------------------------------------

    async def get_bot_enabled(self, session_id: str) -> bool:
        """ดึงสถานะ bot_enabled"""
        pool = self._pool()
        val = await pool.fetchval(
            "SELECT bot_enabled FROM sessions WHERE session_id = $1", session_id
        )
        return bool(val) if val is not None else True

    async def set_bot_enabled(self, session_id: str, enabled: bool) -> bool:
        """ตั้งค่าสถานะ bot_enabled"""
        pool = self._pool()
        result = await pool.execute(
            "UPDATE sessions SET bot_enabled = $1 WHERE session_id = $2",
            enabled, session_id,
        )
        # result = "UPDATE N"
        return result != "UPDATE 0"

    # -- maintenance ------------------------------------------------------

    async def cleanup_old_sessions(self, days: int = 7) -> int:
        """ลบ sessions และข้อความเก่า (CASCADE)"""
        pool = self._pool()
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await pool.execute(
            "DELETE FROM sessions WHERE last_active < $1", cutoff,
        )
        deleted_count = int(result.split()[-1])  # "DELETE N"
        logger.info("🧹 Cleaned up %d old sessions", deleted_count)
        return deleted_count

    async def clear_history(self, session_id: str):
        """ลบประวัติการสนทนาของ session"""
        pool = self._pool()
        await pool.execute(
            "DELETE FROM messages WHERE session_id = $1", session_id,
        )

    # -- admin queries ----------------------------------------------------

    async def get_all_sessions(self) -> List[Dict]:
        """ดึงรายการ sessions ทั้งหมด (สำหรับ Admin)"""
        pool = self._pool()
        rows = await pool.fetch(
            "SELECT * FROM sessions ORDER BY last_active DESC"
        )
        return [dict(r) for r in rows]

    async def get_session_count(self) -> int:
        """นับจำนวน sessions ทั้งหมด"""
        pool = self._pool()
        return await pool.fetchval("SELECT COUNT(*) FROM sessions") or 0

    # -- admin detail queries (used by database_router) -------------------

    async def get_all_sessions_with_stats(self) -> Dict:
        """ดึง sessions + stats สำหรับ database dashboard"""
        pool = self._pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT session_id, user_name, user_picture, platform,
                          bot_enabled, created_at, last_active
                   FROM sessions ORDER BY last_active DESC"""
            )

            total_messages = await conn.fetchval("SELECT COUNT(*) FROM messages") or 0

        sessions = []
        platforms: Dict[str, int] = {}
        active_today = 0
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        for r in rows:
            sessions.append({
                "session_id": r["session_id"],
                "user_name": r["user_name"],
                "user_picture": r["user_picture"],
                "platform": r["platform"],
                "bot_enabled": bool(r["bot_enabled"]),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "last_active": r["last_active"].isoformat() if r["last_active"] else None,
            })
            plat = r["platform"]
            platforms[plat] = platforms.get(plat, 0) + 1
            if r["last_active"] and r["last_active"].replace(tzinfo=None) >= today:
                active_today += 1

        return {
            "sessions": sessions,
            "stats": {
                "totalSessions": len(sessions),
                "totalMessages": total_messages,
                "activeSessions": active_today,
                "platforms": platforms,
            },
        }

    async def get_session_messages(self, session_id: str) -> List[Dict]:
        """ดึง messages ทั้งหมดของ session (รวม id, created_at)"""
        pool = self._pool()
        rows = await pool.fetch(
            """SELECT id, role, content, created_at FROM messages
               WHERE session_id = $1 ORDER BY created_at ASC""",
            session_id,
        )
        return [
            {
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]

    async def update_session(self, session_id: str, **kwargs) -> bool:
        """อัปเดต session fields (user_name, user_picture, platform, bot_enabled)"""
        allowed = {"user_name", "user_picture", "platform", "bot_enabled"}
        sets = []
        vals = [session_id]
        idx = 1
        for k, v in kwargs.items():
            if k not in allowed:
                continue
            idx += 1
            sets.append(f"{k} = ${idx}")
            vals.append(v)
        if not sets:
            return False
        pool = self._pool()
        result = await pool.execute(
            f"UPDATE sessions SET {', '.join(sets)} WHERE session_id = $1", *vals
        )
        return result != "UPDATE 0"

    async def delete_session(self, session_id: str):
        """ลบ session (CASCADE ลบ messages ด้วย)"""
        pool = self._pool()
        await pool.execute("DELETE FROM sessions WHERE session_id = $1", session_id)

    async def update_message(self, message_id: int, content: str) -> bool:
        """อัปเดตเนื้อหาข้อความ"""
        pool = self._pool()
        result = await pool.execute(
            "UPDATE messages SET content = $1 WHERE id = $2", content, message_id
        )
        return result != "UPDATE 0"

    async def delete_message(self, message_id: int):
        """ลบข้อความ"""
        pool = self._pool()
        await pool.execute("DELETE FROM messages WHERE id = $1", message_id)

    async def get_db_stats(self) -> Dict:
        """ดึงสถิติ DB"""
        pool = self._pool()
        async with pool.acquire() as conn:
            total_sessions = await conn.fetchval("SELECT COUNT(*) FROM sessions") or 0
            total_messages = await conn.fetchval("SELECT COUNT(*) FROM messages") or 0
        return {
            "sessions": {"total": total_sessions},
            "messages": {"total": total_messages},
        }


# สร้าง singleton instance
session_db = SessionDatabase()
