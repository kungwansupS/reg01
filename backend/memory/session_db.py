import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List

from sqlalchemy import delete, func, select, update

from memory.database import get_session
from memory.models import Message, Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SessionDatabase — async methods via SQLAlchemy 2 ORM
# ---------------------------------------------------------------------------

class SessionDatabase:
    """
    จัดการ Sessions ผ่าน PostgreSQL Database (SQLAlchemy 2 async)

    โครงสร้างตาราง:
    - sessions: เก็บข้อมูล session, user info, และ settings
    - messages: เก็บประวัติการสนทนา
    """

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
        async with get_session() as db:
            row = await db.get(Session, session_id)

            if row:
                # อัปเดต last_active + user info ถ้ามีการส่งมา
                row.last_active = func.now()
                if user_name:
                    row.user_name = user_name
                if user_picture:
                    row.user_picture = user_picture
                await db.commit()
                session_info = {
                    "session_id": row.session_id,
                    "user_name": row.user_name,
                    "user_picture": row.user_picture,
                    "platform": row.platform,
                    "bot_enabled": row.bot_enabled,
                }
            else:
                # สร้าง session ใหม่
                is_fb = session_id.startswith("fb_")
                detected_platform = platform or ("facebook" if is_fb else "web")
                clean_uid = session_id.replace("fb_", "")

                default_name = user_name or f"{detected_platform.capitalize()} User {clean_uid[:5]}"
                default_picture = user_picture or "https://www.gravatar.com/avatar/?d=mp"

                new_session = Session(
                    session_id=session_id,
                    user_name=default_name,
                    user_picture=default_picture,
                    platform=detected_platform,
                    bot_enabled=True,
                )
                db.add(new_session)
                await db.commit()

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
        async with get_session() as db:
            stmt = (
                select(Message.role, Message.content)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at.asc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            rows = result.all()

        return [
            {"role": r.role, "parts": [{"text": r.content}]}
            for r in rows
        ]

    async def add_message(self, session_id: str, role: str, content: str):
        """เพิ่มข้อความใหม่"""
        async with get_session() as db:
            db.add(Message(session_id=session_id, role=role, content=content))
            await db.execute(
                update(Session)
                .where(Session.session_id == session_id)
                .values(last_active=func.now())
            )
            await db.commit()

    # -- bot toggle -------------------------------------------------------

    async def get_bot_enabled(self, session_id: str) -> bool:
        """ดึงสถานะ bot_enabled"""
        async with get_session() as db:
            stmt = select(Session.bot_enabled).where(Session.session_id == session_id)
            val = await db.scalar(stmt)
        return bool(val) if val is not None else True

    async def set_bot_enabled(self, session_id: str, enabled: bool) -> bool:
        """ตั้งค่าสถานะ bot_enabled"""
        async with get_session() as db:
            result = await db.execute(
                update(Session)
                .where(Session.session_id == session_id)
                .values(bot_enabled=enabled)
            )
            await db.commit()
        return result.rowcount > 0

    # -- maintenance ------------------------------------------------------

    async def cleanup_old_sessions(self, days: int = 7) -> int:
        """ลบ sessions และข้อความเก่า (CASCADE)"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        async with get_session() as db:
            result = await db.execute(
                delete(Session).where(Session.last_active < cutoff)
            )
            await db.commit()
        deleted_count = result.rowcount
        logger.info("🧹 Cleaned up %d old sessions", deleted_count)
        return deleted_count

    async def clear_history(self, session_id: str):
        """ลบประวัติการสนทนาของ session"""
        async with get_session() as db:
            await db.execute(
                delete(Message).where(Message.session_id == session_id)
            )
            await db.commit()

    # -- admin queries ----------------------------------------------------

    async def get_all_sessions(self) -> List[Dict]:
        """ดึงรายการ sessions ทั้งหมด (สำหรับ Admin)"""
        async with get_session() as db:
            stmt = select(Session).order_by(Session.last_active.desc())
            result = await db.execute(stmt)
            rows = result.scalars().all()
        return [
            {
                "session_id": r.session_id,
                "user_name": r.user_name,
                "user_picture": r.user_picture,
                "platform": r.platform,
                "bot_enabled": r.bot_enabled,
                "created_at": r.created_at,
                "last_active": r.last_active,
            }
            for r in rows
        ]

    async def get_session_count(self) -> int:
        """นับจำนวน sessions ทั้งหมด"""
        async with get_session() as db:
            return await db.scalar(select(func.count()).select_from(Session)) or 0

    # -- admin detail queries (used by database_router) -------------------

    async def get_all_sessions_with_stats(self) -> Dict:
        """ดึง sessions + stats สำหรับ database dashboard"""
        async with get_session() as db:
            stmt = select(Session).order_by(Session.last_active.desc())
            result = await db.execute(stmt)
            rows = result.scalars().all()

            total_messages = await db.scalar(select(func.count()).select_from(Message)) or 0

        sessions = []
        platforms: Dict[str, int] = {}
        active_today = 0
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        for r in rows:
            sessions.append({
                "session_id": r.session_id,
                "user_name": r.user_name,
                "user_picture": r.user_picture,
                "platform": r.platform,
                "bot_enabled": r.bot_enabled,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "last_active": r.last_active.isoformat() if r.last_active else None,
            })
            plat = r.platform
            platforms[plat] = platforms.get(plat, 0) + 1
            if r.last_active:
                la = r.last_active if r.last_active.tzinfo else r.last_active.replace(tzinfo=timezone.utc)
                if la >= today:
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
        async with get_session() as db:
            stmt = (
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at.asc())
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "role": r.role,
                "content": r.content,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    async def update_session(self, session_id: str, **kwargs) -> bool:
        """อัปเดต session fields (user_name, user_picture, platform, bot_enabled)"""
        allowed = {"user_name", "user_picture", "platform", "bot_enabled"}
        values = {k: v for k, v in kwargs.items() if k in allowed}
        if not values:
            return False
        async with get_session() as db:
            result = await db.execute(
                update(Session).where(Session.session_id == session_id).values(**values)
            )
            await db.commit()
        return result.rowcount > 0

    async def delete_session(self, session_id: str):
        """ลบ session (CASCADE ลบ messages ด้วย)"""
        async with get_session() as db:
            await db.execute(delete(Session).where(Session.session_id == session_id))
            await db.commit()

    async def update_message(self, message_id: int, content: str) -> bool:
        """อัปเดตเนื้อหาข้อความ"""
        async with get_session() as db:
            result = await db.execute(
                update(Message).where(Message.id == message_id).values(content=content)
            )
            await db.commit()
        return result.rowcount > 0

    async def delete_message(self, message_id: int):
        """ลบข้อความ"""
        async with get_session() as db:
            await db.execute(delete(Message).where(Message.id == message_id))
            await db.commit()

    async def get_db_stats(self) -> Dict:
        """ดึงสถิติ DB"""
        async with get_session() as db:
            total_sessions = await db.scalar(select(func.count()).select_from(Session)) or 0
            total_messages = await db.scalar(select(func.count()).select_from(Message)) or 0
        return {
            "sessions": {"total": total_sessions},
            "messages": {"total": total_messages},
        }


# สร้าง singleton instance
session_db = SessionDatabase()
