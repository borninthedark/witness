"""Async SQLAlchemy session helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from fitness.config import settings

_async_url = settings.resolved_async_database_url
engine_kwargs: dict[str, object] = {"echo": settings.db_echo, "pool_pre_ping": True}

async_engine = create_async_engine(_async_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session for FastAPI dependencies."""
    async with AsyncSessionLocal() as session:
        yield session
