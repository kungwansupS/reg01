#!/usr/bin/env python3
"""
สร้าง test sessions สำหรับทดสอบ Database Management
"""

import sys
import os
from datetime import datetime, timedelta
import random

# เพิ่ม path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import SessionDatabase
try:
    from memory.session_db import SessionDatabase
except ImportError:
    print("❌ Cannot import SessionDatabase")
    print("💡 ให้วางสคริปต์นี้ใน root directory ของโปรเจค")
    sys.exit(1)

def create_test_sessions():
    """สร้าง test sessions"""
    print("🔵 Creating test sessions...")
    
    test_users = [
        {"name": "Alice Smith", "platform": "line", "pic": "https://ui-avatars.com/api/?name=Alice+Smith"},
        {"name": "Bob Johnson", "platform": "messenger", "pic": "https://ui-avatars.com/api/?name=Bob+Johnson"},
        {"name": "Charlie Brown", "platform": "line", "pic": "https://ui-avatars.com/api/?name=Charlie+Brown"},
        {"name": "Diana Prince", "platform": "messenger", "pic": "https://ui-avatars.com/api/?name=Diana+Prince"},
        {"name": "สมชาย ใจดี", "platform": "line", "pic": "https://ui-avatars.com/api/?name=สมชาย+ใจดี"},
    ]
    
    conversations = [
        [
            {"role": "user", "content": "สวัสดีครับ"},
            {"role": "assistant", "content": "สวัสดีค่ะ มีอะไรให้ช่วยไหมคะ"},
            {"role": "user", "content": "ขอข้อมูลการลงทะเบียนหน่อยครับ"},
            {"role": "assistant", "content": "ได้เลยค่ะ คุณสนใจลงทะเบียนวิชาอะไรคะ"},
        ],
        [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help you today?"},
        ],
        [
            {"role": "user", "content": "ตารางเรียนยังไง"},
            {"role": "assistant", "content": "คุณสามารถดูตารางเรียนได้ที่ระบบ REG CMU ค่ะ"},
        ]
    ]
    
    # สร้าง database instance (ไม่ใช้ context manager)
    db = SessionDatabase()
    
    try:
        created_count = 0
        
        for i, user in enumerate(test_users):
            session_id = f"test_session_{i+1}_{random.randint(1000, 9999)}"
            
            # สร้าง session
            created_at = (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat()
            last_active = (datetime.now() - timedelta(hours=random.randint(0, 72))).isoformat()
            bot_enabled = random.choice([True, False])
            
            db.conn.execute("""
                INSERT OR IGNORE INTO sessions 
                (session_id, user_name, user_picture, platform, bot_enabled, created_at, last_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, user["name"], user["pic"], user["platform"], 
                  1 if bot_enabled else 0, created_at, last_active))
            
            # สร้าง messages
            conv = random.choice(conversations)
            for msg in conv:
                timestamp = (datetime.now() - timedelta(minutes=random.randint(1, 1440))).isoformat()
                db.conn.execute("""
                    INSERT INTO messages (session_id, role, content, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (session_id, msg["role"], msg["content"], timestamp))
            
            db.conn.commit()
            created_count += 1
            print(f"  ✅ Created: {user['name']} ({session_id})")
        
        print(f"\n✅ Created {created_count} test sessions!")
        
        # แสดงสถิติ
        cursor = db.conn.execute("SELECT COUNT(*) FROM sessions")
        total_sessions = cursor.fetchone()[0]
        
        cursor = db.conn.execute("SELECT COUNT(*) FROM messages")
        total_messages = cursor.fetchone()[0]
        
        print(f"\n📊 Database Stats:")
        print(f"   Total Sessions: {total_sessions}")
        print(f"   Total Messages: {total_messages}")
        
    finally:
        # ปิด connection
        if hasattr(db, 'conn') and db.conn:
            db.conn.close()

if __name__ == "__main__":
    try:
        create_test_sessions()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()