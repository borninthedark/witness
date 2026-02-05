"""Synchronous SQLAlchemy session helpers."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from fitness.config import settings


class Base(DeclarativeBase):
    """Declarative base class for ORM models."""


_database_url = settings.resolved_database_url
engine_kwargs = {
    "echo": settings.db_echo,
    "pool_pre_ping": True,
    "connect_args": {"check_same_thread": False},
}

engine: Engine = create_engine(_database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    """Yield a scoped session for dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
