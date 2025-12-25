# backend/database/connection.py
"""
Database Connection Manager
รองรับ SQLite และ PostgreSQL
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# ========================================================================
# Configuration
# ========================================================================

DB_TYPE = os.getenv("DB_TYPE", "sqlite")  # sqlite หรือ postgresql
DB_PATH = os.getenv("DB_PATH", "backend/database/reg01.db")
DB_URL = os.getenv("DATABASE_URL", "")  # สำหรับ PostgreSQL

# ========================================================================
# Engine Setup
# ========================================================================

def get_database_url():
    """สร้าง Database URL ตาม configuration"""
    if DB_TYPE == "postgresql" and DB_URL:
        return DB_URL
    else:
        # SQLite (default)
        db_dir = os.path.dirname(DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        return f"sqlite:///{DB_PATH}"


def create_db_engine():
    """สร้าง SQLAlchemy Engine"""
    database_url = get_database_url()
    
    if database_url.startswith("sqlite"):
        # SQLite Configuration
        engine = create_engine(
            database_url,
            connect_args={
                "check_same_thread": False,  # สำหรับ FastAPI async
                "timeout": 30  # Timeout 30 วินาที
            },
            poolclass=StaticPool,  # ใช้ Static Pool สำหรับ SQLite
            echo=False  # เปลี่ยนเป็น True เพื่อ debug SQL
        )
        
        # เปิดใช้งาน Foreign Keys ใน SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
            cursor.close()
        
        logger.info(f"✅ SQLite Database: {DB_PATH}")
    
    else:
        # PostgreSQL Configuration
        engine = create_engine(
            database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # ตรวจสอบ connection ก่อนใช้
            echo=False
        )
        logger.info(f"✅ PostgreSQL Database connected")
    
    return engine


# สร้าง Engine (Global)
engine = create_db_engine()

# สร้าง Session Factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Thread-safe Session
db_session = scoped_session(SessionLocal)


# ========================================================================
# Context Manager
# ========================================================================

@contextmanager
def get_db():
    """
    Context Manager สำหรับ Database Session
    
    Usage:
        with get_db() as db:
            user = db.query(User).first()
    """
    session = db_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Database Error: {e}")
        raise
    finally:
        session.close()


def get_db_dependency():
    """
    Dependency สำหรับ FastAPI
    
    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db_dependency)):
            return db.query(User).all()
    """
    db = db_session()
    try:
        yield db
    finally:
        db.close()


# ========================================================================
# Utility Functions
# ========================================================================

def init_database():
    """
    เริ่มต้น Database (สร้างตาราง)
    """
    from database.models import create_all_tables
    
    try:
        create_all_tables(engine)
        logger.info("✅ Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        return False


def check_database_health():
    """
    ตรวจสอบสถานะ Database
    """
    from sqlalchemy import text
    
    try:
        with get_db() as db:
            db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"❌ Database health check failed: {e}")
        return False


def get_database_stats():
    """
    ดึงสถิติ Database
    """
    from database.models import User, Message, FAQ, AuditLog
    
    try:
        with get_db() as db:
            stats = {
                'total_users': db.query(User).count(),
                'total_messages': db.query(Message).count(),
                'total_faqs': db.query(FAQ).count(),
                'total_logs': db.query(AuditLog).count(),
                'database_type': DB_TYPE,
                'database_path': DB_PATH if DB_TYPE == 'sqlite' else 'PostgreSQL'
            }
            return stats
    except Exception as e:
        logger.error(f"❌ Failed to get database stats: {e}")
        return {}


def backup_database(backup_path: str = None):
    """
    สำรองฐานข้อมูล SQLite
    """
    if DB_TYPE != "sqlite":
        logger.warning("⚠️ Backup only works with SQLite")
        return False
    
    import shutil
    from datetime import datetime
    
    if not backup_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backend/database/backups/reg01_backup_{timestamp}.db"
    
    try:
        # สร้างโฟลเดอร์ backup
        backup_dir = os.path.dirname(backup_path)
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir, exist_ok=True)
        
        # Copy database file
        shutil.copy2(DB_PATH, backup_path)
        logger.info(f"✅ Database backed up to: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Backup failed: {e}")
        return False


def vacuum_database():
    """
    ทำความสะอาด Database (SQLite)
    """
    from sqlalchemy import text
    
    if DB_TYPE != "sqlite":
        return False
    
    try:
        with get_db() as db:
            db.execute(text("VACUUM"))
        logger.info("✅ Database vacuumed successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Vacuum failed: {e}")
        return False


# ========================================================================
# Cleanup
# ========================================================================

def close_database():
    """
    ปิด Database connection
    """
    try:
        db_session.remove()
        engine.dispose()
        logger.info("✅ Database connections closed")
    except Exception as e:
        logger.error(f"❌ Failed to close database: {e}")


# ========================================================================
# Auto-initialize
# ========================================================================

# หมายเหตุ: ปิด auto-initialize เพราะจะเรียกจาก run.py แทน
# เพื่อให้ควบคุมการ initialize ได้ดีกว่า

# if __name__ != "__main__":
#     # เริ่มต้น database เมื่อ import module
#     init_database()