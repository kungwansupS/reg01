"""
SQLAlchemy 2 async engine & session factory

Usage:
    from memory.database import init_db, close_db, get_session

    # At startup:
    await init_db(DATABASE_URL)

    # In business logic:
    async with get_session() as session:
        ...

    # At shutdown:
    await close_db()
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from memory.models import Base

logger = logging.getLogger(__name__)

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


async def init_db(
    dsn: str,
    pool_size: int = 5,
    max_overflow: int = 5,
    echo: bool = False,
):
    """
    สร้าง async engine + session factory และ create tables (idempotent)
    เรียกครั้งเดียวตอน application startup (main.py)
    """
    global _engine, _session_factory

    # SQLAlchemy async ใช้ asyncpg driver — DSN ต้องเริ่มด้วย postgresql+asyncpg://
    sa_dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)

    _engine = create_async_engine(
        sa_dsn,
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo=echo,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    # Create tables (idempotent — safe for dev; production uses Alembic)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info(
        "✅ SQLAlchemy async engine initialized (pool_size=%d, max_overflow=%d)",
        pool_size,
        max_overflow,
    )


async def close_db():
    """ปิด engine — เรียกตอน shutdown"""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("✅ SQLAlchemy engine disposed")


def get_session() -> AsyncSession:
    """Return a new AsyncSession (use as async context manager)."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized — call init_db() first")
    return _session_factory()


def get_engine() -> AsyncEngine:
    """Return the current engine (for Alembic or raw ops)."""
    if _engine is None:
        raise RuntimeError("Database not initialized — call init_db() first")
    return _engine
