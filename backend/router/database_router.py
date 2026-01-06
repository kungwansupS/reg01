from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
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
    """Verify admin token from X-Admin-Token header (same as other endpoints)"""
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
        try:
            # Get all sessions
            cursor = db.conn.execute("""
                SELECT 
                    session_id, user_name, user_picture, platform, 
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
                
                # Count platforms
                platform = row[3]
                platforms[platform] = platforms.get(platform, 0) + 1
                
                # Count active today
                if datetime.fromisoformat(row[6]) >= today:
                    active_today += 1
            
            # Get total messages
            cursor = db.conn.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]
            
            stats = {
                'totalSessions': len(sessions),
                'totalMessages': total_messages,
                'activeSessions': active_today,
                'platforms': platforms
            }
            
            return {
                'success': True,
                'sessions': sessions,
                'stats': stats
            }
        finally:
            if hasattr(db, "conn") and db.conn:
                db.conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, x_admin_token: str = Header(None)):
    """Get all messages for a specific session"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        try:
            cursor = db.conn.execute("""
                SELECT id, role, content, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
            """, (session_id,))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'id': row[0],
                    'role': row[1],
                    'content': row[2],
                    'timestamp': row[3]
                })
            
            return {
                'success': True,
                'messages': messages
            }
        finally:
            if hasattr(db, "conn") and db.conn:
                db.conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, updates: SessionUpdate, x_admin_token: str = Header(None)):
    """Update session information"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        try:
            # Build update query
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
            
            # Add session_id to values
            values.append(session_id)
            
            # Execute update
            query = f"""
                UPDATE sessions 
                SET {', '.join(update_fields)}
                WHERE session_id = ?
            """
            db.conn.execute(query, values)
            db.conn.commit()
            
            return {'success': True, 'message': 'Session updated'}
        finally:
            if hasattr(db, "conn") and db.conn:
                db.conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, x_admin_token: str = Header(None)):
    """Delete a session and all its messages"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        try:
            # Delete session (messages will be cascade deleted)
            db.conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            db.conn.commit()
            
            return {'success': True, 'message': 'Session deleted'}
        finally:
            if hasattr(db, "conn") and db.conn:
                db.conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/messages/{message_id}")
async def update_message(message_id: int, update: MessageUpdate, x_admin_token: str = Header(None)):
    """Update message content"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        try:
            db.conn.execute("""
                UPDATE messages 
                SET content = ?
                WHERE id = ?
            """, (update.content, message_id))
            db.conn.commit()
            
            return {'success': True, 'message': 'Message updated'}
        finally:
            if hasattr(db, "conn") and db.conn:
                db.conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/messages/{message_id}")
async def delete_message(message_id: int, x_admin_token: str = Header(None)):
    """Delete a message"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        try:
            db.conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            db.conn.commit()
            
            return {'success': True, 'message': 'Message deleted'}
        finally:
            if hasattr(db, "conn") and db.conn:
                db.conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup")
async def cleanup_old_sessions(days: int = 7, x_admin_token: str = Header(None)):
    """Delete sessions older than specified days"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        try:
            deleted_count = db.cleanup_old_sessions(days)
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'message': f'Deleted {deleted_count} sessions older than {days} days'
            }
        finally:
            if hasattr(db, "conn") and db.conn:
                db.conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export")
async def export_database(x_admin_token: str = Header(None)):
    """Export the entire database file"""
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
    """Get detailed database statistics"""
    verify_admin_token(x_admin_token)
    
    try:
        db = SessionDatabase()
        try:
            # Session stats
            cursor = db.conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN bot_enabled = 1 THEN 1 END) as bot_enabled,
                    platform,
                    COUNT(*) as count
                FROM sessions
                GROUP BY platform
            """)
            
            platform_stats = {}
            total_sessions = 0
            bot_enabled_count = 0
            
            for row in cursor.fetchall():
                total_sessions = row[0]
                bot_enabled_count = row[1]
                platform = row[2]
                count = row[3]
                platform_stats[platform] = count
            
            # Message stats
            cursor = db.conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    role,
                    COUNT(*) as count
                FROM messages
                GROUP BY role
            """)
            
            message_stats = {}
            total_messages = 0
            for row in cursor.fetchall():
                total_messages = row[0]
                role = row[1]
                count = row[2]
                message_stats[role] = count
            
            # Database size
            cursor = db.conn.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            db_size = cursor.fetchone()[0]
            
            return {
                'success': True,
                'stats': {
                    'sessions': {
                        'total': total_sessions,
                        'bot_enabled': bot_enabled_count,
                        'by_platform': platform_stats
                    },
                    'messages': {
                        'total': total_messages,
                        'by_role': message_stats
                    },
                    'database': {
                        'size_bytes': db_size,
                        'size_mb': round(db_size / (1024 * 1024), 2)
                    }
                }
            }
        finally:
            if hasattr(db, "conn") and db.conn:
                db.conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))