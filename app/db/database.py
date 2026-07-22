"""Database connection and session management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    pass


async def get_engine() -> AsyncEngine:
    global engine
    if engine is None:
        engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
    return engine


async def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global async_session_factory
    if async_session_factory is None:
        eng = await get_engine()
        async_session_factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    return async_session_factory


async def create_db_and_tables():
    """Create all tables on startup."""
    eng = await get_engine()
    async with eng.begin() as conn:
        from app.models.session import SessionModel  # noqa: F401 — ensure models are imported
        from app.models.audit_log import AuditLogModel  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    factory = await get_session_factory()
    async with factory() as session:
        yield session
