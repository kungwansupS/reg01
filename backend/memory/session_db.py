import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Database path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "sessions.db")


class SessionDatabase:
    """
    จัดการ Sessions ผ่าน SQLite Database
    
    โครงสร้างตาราง:
    - sessions: เก็บข้อมูล session, user info, และ settings
    - messages: เก็บประวัติการสนทนา
    """
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager สำหรับจัดการ database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # ให้สามารถเข้าถึงข้อมูลแบบ dict ได้
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_database(self):
        """สร้างตารางในฐานข้อมูล"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # ตาราง sessions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_name TEXT NOT NULL,
                    user_picture TEXT,
                    platform TEXT NOT NULL DEFAULT 'web',
                    bot_enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # ตาราง messages
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            
            # สร้าง index เพื่อเพิ่มประสิทธิภาพ
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session 
                ON messages(session_id, created_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_last_active 
                ON sessions(last_active)
            """)
            
            conn.commit()
            logger.info(f"✅ Database initialized at {self.db_path}")
    
    def get_or_create_session(
        self, 
        session_id: str,
        user_name: Optional[str] = None,
        user_picture: Optional[str] = None,
        platform: str = "web"
    ) -> Dict:
        """
        ดึงหรือสร้าง session ใหม่
        
        Returns:
            Dict ที่มี session info และ history
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # ตรวจสอบว่ามี session นี้อยู่แล้วหรือไม่
            cursor.execute("""
                SELECT * FROM sessions WHERE session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            
            if row:
                # อัปเดต last_active
                cursor.execute("""
                    UPDATE sessions 
                    SET last_active = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                """, (session_id,))
                
                # อัปเดต user info ถ้ามีการส่งมา
                if user_name:
                    cursor.execute("""
                        UPDATE sessions SET user_name = ? WHERE session_id = ?
                    """, (user_name, session_id))
                
                if user_picture:
                    cursor.execute("""
                        UPDATE sessions SET user_picture = ? WHERE session_id = ?
                    """, (user_picture, session_id))
                
                conn.commit()
                
                session_info = dict(row)
            else:
                # สร้าง session ใหม่
                is_fb = session_id.startswith("fb_")
                detected_platform = platform or ("facebook" if is_fb else "web")
                clean_uid = session_id.replace("fb_", "")
                
                default_name = user_name or f"{detected_platform.capitalize()} User {clean_uid[:5]}"
                default_picture = user_picture or "https://www.gravatar.com/avatar/?d=mp"
                
                cursor.execute("""
                    INSERT INTO sessions (session_id, user_name, user_picture, platform, bot_enabled)
                    VALUES (?, ?, ?, ?, 1)
                """, (session_id, default_name, default_picture, detected_platform))
                
                conn.commit()
                
                session_info = {
                    'session_id': session_id,
                    'user_name': default_name,
                    'user_picture': default_picture,
                    'platform': detected_platform,
                    'bot_enabled': 1
                }
            
            # ดึงประวัติการสนทนา
            history = self.get_history(session_id)
            
            return {
                'session_info': session_info,
                'history': history
            }
    
    def get_history(self, session_id: str, limit: int = 30) -> List[Dict]:
        """
        ดึงประวัติการสนทนา
        
        Args:
            session_id: Session ID
            limit: จำนวนข้อความสูงสุดที่ต้องการ (default: 30)
        
        Returns:
            List of messages ในรูปแบบ [{"role": "user", "parts": [{"text": "..."}]}]
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT role, content FROM messages
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            """, (session_id, limit))
            
            rows = cursor.fetchall()
            
            return [
                {
                    "role": row['role'],
                    "parts": [{"text": row['content']}]
                }
                for row in rows
            ]
    
    def add_message(self, session_id: str, role: str, content: str):
        """
        เพิ่มข้อความใหม่
        
        Args:
            session_id: Session ID
            role: "user" หรือ "model"
            content: เนื้อหาข้อความ
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # เพิ่มข้อความ
            cursor.execute("""
                INSERT INTO messages (session_id, role, content)
                VALUES (?, ?, ?)
            """, (session_id, role, content))
            
            # อัปเดต last_active
            cursor.execute("""
                UPDATE sessions 
                SET last_active = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, (session_id,))
            
            conn.commit()
    
    def get_bot_enabled(self, session_id: str) -> bool:
        """ดึงสถานะ bot_enabled"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT bot_enabled FROM sessions WHERE session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            
            if row:
                return bool(row['bot_enabled'])
            
            return True  # Default
    
    def set_bot_enabled(self, session_id: str, enabled: bool) -> bool:
        """ตั้งค่าสถานะ bot_enabled"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE sessions 
                SET bot_enabled = ?
                WHERE session_id = ?
            """, (1 if enabled else 0, session_id))
            
            conn.commit()
            
            return cursor.rowcount > 0
    
    def cleanup_old_sessions(self, days: int = 7) -> int:
        """
        ลบ sessions และข้อความเก่า
        
        Args:
            days: จำนวนวันที่ไม่มีกิจกรรม
        
        Returns:
            จำนวน sessions ที่ถูกลบ
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # ลบ sessions เก่า (CASCADE จะลบ messages อัตโนมัติ)
            cursor.execute("""
                DELETE FROM sessions
                WHERE last_active < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"🧹 Cleaned up {deleted_count} old sessions")
            
            # Vacuum เพื่อคืนพื้นที่
            conn.execute("VACUUM")
            
            return deleted_count
    
    def clear_history(self, session_id: str):
        """ลบประวัติการสนทนาของ session"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM messages WHERE session_id = ?
            """, (session_id,))
            
            conn.commit()
    
    def get_all_sessions(self) -> List[Dict]:
        """
        ดึงรายการ sessions ทั้งหมด (สำหรับ Admin)
        
        Returns:
            List of session info
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM sessions
                ORDER BY last_active DESC
            """)
            
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    def get_session_count(self) -> int:
        """นับจำนวน sessions ทั้งหมด"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as count FROM sessions")
            row = cursor.fetchone()
            
            return row['count'] if row else 0


# สร้าง singleton instance
session_db = SessionDatabase()
