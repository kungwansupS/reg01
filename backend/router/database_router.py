from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import os
from datetime import datetime
from memory.session_db import session_db

router = APIRouter(prefix="/admin/api/database", tags=["database"])

class SessionUpdate(BaseModel):
    user_name: Optional[str] = None
    user_picture: Optional[str] = None
    platform: Optional[str] = None
    bot_enabled: Optional[bool] = None

class MessageUpdate(BaseModel):
    content: str

def verify_admin_token(x_admin_token: str = Header(None)):
    """Verify admin token"""
    admin_token = os.getenv("ADMIN_TOKEN", "super-secret-key")
    if not x_admin_token:
        raise HTTPException(status_code=401, detail="X-Admin-Token header missing")
    if x_admin_token != admin_token:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True

@router.get("/sessions")
async def get_all_sessions(x_admin_token: str = Header(None)):
    """Get all sessions with statistics"""
    verify_admin_token(x_admin_token)
    
    try:
        data = await session_db.get_all_sessions_with_stats()
        return {'success': True, 'sessions': data['sessions'], 'stats': data['stats']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, x_admin_token: str = Header(None)):
    """Get all messages for a session"""
    verify_admin_token(x_admin_token)
    
    try:
        messages = await session_db.get_session_messages(session_id)
        return {'success': True, 'messages': messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, updates: SessionUpdate, x_admin_token: str = Header(None)):
    """Update session"""
    verify_admin_token(x_admin_token)
    
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
        return {'success': True, 'message': 'Session updated'}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, x_admin_token: str = Header(None)):
    """Delete session"""
    verify_admin_token(x_admin_token)
    
    try:
        await session_db.delete_session(session_id)
        return {'success': True, 'message': 'Session deleted'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/messages/{message_id}")
async def update_message(message_id: int, update: MessageUpdate, x_admin_token: str = Header(None)):
    """Update message"""
    verify_admin_token(x_admin_token)
    
    try:
        await session_db.update_message(message_id, update.content)
        return {'success': True, 'message': 'Message updated'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/messages/{message_id}")
async def delete_message(message_id: int, x_admin_token: str = Header(None)):
    """Delete message"""
    verify_admin_token(x_admin_token)
    
    try:
        await session_db.delete_message(message_id)
        return {'success': True, 'message': 'Message deleted'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup")
async def cleanup_old_sessions(days: int = 7, x_admin_token: str = Header(None)):
    """Cleanup old sessions"""
    verify_admin_token(x_admin_token)
    
    try:
        deleted_count = await session_db.cleanup_old_sessions(days)
        return {
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Deleted {deleted_count} sessions older than {days} days'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export")
async def export_database(x_admin_token: str = Header(None)):
    """Export database as JSON (PostgreSQL — no .db file)"""
    verify_admin_token(x_admin_token)
    
    try:
        data = await session_db.get_all_sessions_with_stats()
        # Build a full export with messages per session
        sessions_export = []
        for s in data["sessions"]:
            messages = await session_db.get_session_messages(s["session_id"])
            sessions_export.append({**s, "messages": messages})
        
        export = {
            "exported_at": datetime.now().isoformat(),
            "stats": data["stats"],
            "sessions": sessions_export,
        }
        return JSONResponse(
            content=export,
            headers={
                "Content-Disposition": f'attachment; filename="sessions_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_database_stats(x_admin_token: str = Header(None)):
    """Get stats"""
    verify_admin_token(x_admin_token)
    
    try:
        stats = await session_db.get_db_stats()
        return {'success': True, 'stats': stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
