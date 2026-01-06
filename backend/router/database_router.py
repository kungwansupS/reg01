from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
from datetime import datetime, timedelta
from memory.session_db import SessionDatabase

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
    admin_token = os.getenv("ADMIN_TOKEN", "your-secure-admin-token-here")
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
        db = SessionDatabase()
        with db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT session_id, user_name, user_picture, platform, 
                       bot_enabled, created_at, last_active
                FROM sessions
                ORDER BY last_active DESC
            """)
            
            sessions = []
            platforms = {}
            active_today = 0
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            for row in cursor.fetchall():
                session = {
                    'session_id': row[0],
                    'user_name': row[1],
                    'user_picture': row[2],
                    'platform': row[3],
                    'bot_enabled': bool(row[4]),
                    'created_at': row[5],
                    'last_active': row[6]
                }
                sessions.append(session)
                
                platform = row[3]
                platforms[platform] = platforms.get(platform, 0) + 1
                
                if datetime.fromisoformat(row[6]) >= today:
                    active_today += 1
            
            cursor = conn.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]
            
            stats = {
                'totalSessions': len(sessions),
                'totalMessages': total_messages,
                'activeSessions': active_today,
                'platforms': platforms
            }
            
            return {'success': True, 'sessions': sessions, 'stats': stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, x_admin_token: str = Header(None)):
    """Get all messages for a session"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        with db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, role, content, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at ASC
            """, (session_id,))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'id': row[0],
                    'role': row[1],
                    'content': row[2],
                    'created_at': row[3]
                })
            
            return {'success': True, 'messages': messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, updates: SessionUpdate, x_admin_token: str = Header(None)):
    """Update session"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        with db.get_connection() as conn:
            update_fields = []
            values = []
            
            if updates.user_name is not None:
                update_fields.append("user_name = ?")
                values.append(updates.user_name)
            if updates.user_picture is not None:
                update_fields.append("user_picture = ?")
                values.append(updates.user_picture)
            if updates.platform is not None:
                update_fields.append("platform = ?")
                values.append(updates.platform)
            if updates.bot_enabled is not None:
                update_fields.append("bot_enabled = ?")
                values.append(1 if updates.bot_enabled else 0)
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            values.append(session_id)
            
            query = f"UPDATE sessions SET {', '.join(update_fields)} WHERE session_id = ?"
            conn.execute(query, values)
            conn.commit()
            
            return {'success': True, 'message': 'Session updated'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, x_admin_token: str = Header(None)):
    """Delete session"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        with db.get_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
            return {'success': True, 'message': 'Session deleted'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/messages/{message_id}")
async def update_message(message_id: int, update: MessageUpdate, x_admin_token: str = Header(None)):
    """Update message"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        with db.get_connection() as conn:
            conn.execute("UPDATE messages SET content = ? WHERE id = ?", (update.content, message_id))
            conn.commit()
            return {'success': True, 'message': 'Message updated'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/messages/{message_id}")
async def delete_message(message_id: int, x_admin_token: str = Header(None)):
    """Delete message"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        with db.get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            conn.commit()
            return {'success': True, 'message': 'Message deleted'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup")
async def cleanup_old_sessions(days: int = 7, x_admin_token: str = Header(None)):
    """Cleanup old sessions"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        deleted_count = db.cleanup_old_sessions(days)
        return {
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Deleted {deleted_count} sessions older than {days} days'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export")
async def export_database(x_admin_token: str = Header(None)):
    """Export database"""
    verify_admin_token(x_admin_token)
    
    db_path = "backend/memory/sessions.db"
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database file not found")
    
    return FileResponse(
        path=db_path,
        filename=f"sessions_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
        media_type="application/x-sqlite3"
    )

@router.get("/stats")
async def get_database_stats(x_admin_token: str = Header(None)):
    """Get stats"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM sessions")
            total_sessions = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]
            
            return {
                'success': True,
                'stats': {
                    'sessions': {'total': total_sessions},
                    'messages': {'total': total_messages}
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))