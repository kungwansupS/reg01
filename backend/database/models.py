# backend/database/models.py
"""
Database Models for REG-01 System
รองรับ SQLite และ PostgreSQL
"""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, 
    ForeignKey, JSON, Index, Float
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import json

Base = declarative_base()


class User(Base):
    """
    ตาราง Users - เก็บข้อมูลผู้ใช้
    """
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    platform = Column(String(50), nullable=False, index=True)  # facebook, web, line
    
    # ข้อมูลโปรไฟล์
    name = Column(String(255), nullable=False)
    picture_url = Column(String(512))
    
    # สถานะ Bot
    bot_enabled = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_user_platform', 'platform'),
        Index('idx_user_last_active', 'last_active'),
    )
    
    def to_dict(self):
        """แปลงเป็น dict"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'platform': self.platform,
            'profile': {
                'name': self.name,
                'picture': self.picture_url
            },
            'bot_enabled': self.bot_enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_active': self.last_active.timestamp() if self.last_active else None
        }


class Session(Base):
    """
    ตาราง Sessions - เก็บข้อมูลการสนทนา
    """
    __tablename__ = 'sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Summary ของ conversation
    summary = Column(Text)
    message_count = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime)
    last_message_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship
    user = relationship("User", back_populates="sessions")
    
    # Indexes
    __table_args__ = (
        Index('idx_session_user', 'user_id'),
        Index('idx_session_last_message', 'last_message_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'summary': self.summary,
            'message_count': self.message_count,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None
        }


class Message(Base):
    """
    ตาราง Messages - เก็บข้อความทั้งหมด
    """
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # ข้อความ
    role = Column(String(20), nullable=False)  # user, model, system
    content = Column(Text, nullable=False)
    
    # Metadata
    motion = Column(String(50))  # ท่าทางของ avatar
    latency = Column(Float)  # เวลาในการประมวลผล (วินาที)
    from_faq = Column(Boolean, default=False)  # มาจาก FAQ cache หรือไม่
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationship
    user = relationship("User", back_populates="messages")
    
    # Indexes
    __table_args__ = (
        Index('idx_message_user', 'user_id'),
        Index('idx_message_role', 'role'),
        Index('idx_message_created', 'created_at'),
    )
    
    def to_dict(self):
        """แปลงเป็น dict (รูปแบบเดิมของ session)"""
        return {
            'role': self.role,
            'parts': [{'text': self.content}],
            'motion': self.motion,
            'latency': self.latency,
            'from_faq': self.from_faq,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class FAQ(Base):
    """
    ตาราง FAQ - เก็บคำถามที่ถามบ่อย
    """
    __tablename__ = 'faqs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # คำถามและคำตอบ
    question = Column(Text, nullable=False, unique=True)
    answer = Column(Text, nullable=False)
    
    # สถิติ
    hit_count = Column(Integer, default=1, nullable=False)
    
    # Embedding สำหรับ semantic search (optional)
    question_embedding = Column(Text)  # เก็บเป็น JSON array
    
    # Metadata
    is_learned = Column(Boolean, default=False)  # เรียนรู้อัตโนมัติหรือเพิ่มเอง
    category = Column(String(100))  # หมวดหมู่
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_faq_hit_count', 'hit_count'),
        Index('idx_faq_category', 'category'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'question': self.question,
            'answer': self.answer,
            'hit_count': self.hit_count,
            'is_learned': self.is_learned,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class AuditLog(Base):
    """
    ตาราง Audit Logs - เก็บ logs การใช้งาน
    """
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User info (anonymized)
    anon_id = Column(String(50), nullable=False, index=True)
    platform = Column(String(50), nullable=False, index=True)
    
    # Request/Response
    user_input = Column(Text, nullable=False)
    ai_output = Column(Text, nullable=False)
    
    # Performance
    latency = Column(Float, nullable=False)  # milliseconds
    
    # Rating (optional)
    rating = Column(String(20), default='none')  # none, good, bad
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_audit_platform', 'platform'),
        Index('idx_audit_created', 'created_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.created_at.isoformat() if self.created_at else None,
            'anon_id': self.anon_id,
            'platform': self.platform,
            'input': self.user_input[:300],
            'output': self.ai_output[:300],
            'latency': self.latency,
            'rating': self.rating
        }


# ========================================================================
# Helper Functions
# ========================================================================

def create_all_tables(engine):
    """สร้างตารางทั้งหมด"""
    Base.metadata.create_all(engine)
    print("✅ Database tables created successfully")


def drop_all_tables(engine):
    """ลบตารางทั้งหมด (ระวัง!)"""
    Base.metadata.drop_all(engine)
    print("⚠️ All database tables dropped")
