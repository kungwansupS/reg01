from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth import require_admin
from memory.session_db import session_db

router = APIRouter(prefix="/api/admin/database", tags=["database"])


class SessionUpdate(BaseModel):
    user_name: Optional[str] = None
    user_picture: Optional[str] = None
    platform: Optional[str] = None
    bot_enabled: Optional[bool] = None


class MessageUpdate(BaseModel):
    content: str


@router.get("/sessions")
async def get_all_sessions(_claims: dict = Depends(require_admin)):
    """Get all sessions with statistics."""
    try:
        data = await session_db.get_all_sessions_with_stats()
        return {"success": True, "sessions": data["sessions"], "stats": data["stats"]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, _claims: dict = Depends(require_admin)):
    """Get all messages for a session."""
    try:
        messages = await session_db.get_session_messages(session_id)
        return {"success": True, "messages": messages}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str,
    updates: SessionUpdate,
    _claims: dict = Depends(require_admin),
):
    """Update session."""
    try:
        kwargs = {}
        if updates.user_name is not None:
            kwargs["user_name"] = updates.user_name
        if updates.user_picture is not None:
            kwargs["user_picture"] = updates.user_picture
        if updates.platform is not None:
            kwargs["platform"] = updates.platform
        if updates.bot_enabled is not None:
            kwargs["bot_enabled"] = updates.bot_enabled

        if not kwargs:
            raise HTTPException(status_code=400, detail="No fields to update")

        await session_db.update_session(session_id, **kwargs)
        return {"success": True, "message": "Session updated"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, _claims: dict = Depends(require_admin)):
    """Delete session."""
    try:
        await session_db.delete_session(session_id)
        return {"success": True, "message": "Session deleted"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/messages/{message_id}")
async def update_message(
    message_id: int,
    update: MessageUpdate,
    _claims: dict = Depends(require_admin),
):
    """Update message."""
    try:
        await session_db.update_message(message_id, update.content)
        return {"success": True, "message": "Message updated"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/messages/{message_id}")
async def delete_message(message_id: int, _claims: dict = Depends(require_admin)):
    """Delete message."""
    try:
        await session_db.delete_message(message_id)
        return {"success": True, "message": "Message deleted"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/cleanup")
async def cleanup_old_sessions(days: int = 7, _claims: dict = Depends(require_admin)):
    """Cleanup old sessions."""
    try:
        deleted_count = await session_db.cleanup_old_sessions(days)
        return {
            "success": True,
            "deleted_count": deleted_count,
            "message": f"Deleted {deleted_count} sessions older than {days} days",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/export")
async def export_database(_claims: dict = Depends(require_admin)):
    """Export database as JSON (PostgreSQL, no .db file)."""
    try:
        data = await session_db.get_all_sessions_with_stats()
        sessions_export = []
        for session in data["sessions"]:
            messages = await session_db.get_session_messages(session["session_id"])
            sessions_export.append({**session, "messages": messages})

        export = {
            "exported_at": datetime.now().isoformat(),
            "stats": data["stats"],
            "sessions": sessions_export,
        }
        return JSONResponse(
            content=export,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="sessions_backup_'
                    f'{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
                )
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/stats")
async def get_database_stats(_claims: dict = Depends(require_admin)):
    """Get database stats."""
    try:
        stats = await session_db.get_db_stats()
        return {"success": True, "stats": stats}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
