"""Test fixtures for API and database."""

from __future__ import annotations

import os
from pathlib import Path

TESTS_ROOT = Path(__file__).parent

# Set DATABASE_URL *before* importing fitness modules so the app doesn't try to
# open the default production database path (which may not exist in test envs).
os.environ.setdefault("DATABASE_URL", "sqlite:///test_app.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import fitness.main as main_module  # noqa: E402
from fitness.database import Base  # noqa: E402
from fitness.database import get_db as db_dependency  # noqa: E402
from fitness.main import app  # noqa: E402
from fitness.models import (  # noqa: E402,F401 - ensure metadata is populated
    blog,
    certification,
)
from fitness.security.rate_limit import limiter  # noqa: E402

# Disable rate limiting in tests to prevent cross-test 429 flakes
limiter.enabled = False

TEST_DB_PATH = Path("test_app.db")
TESTING_SESSION_FACTORY: sessionmaker | None = None


@pytest.fixture(scope="session")
def client():
    global TESTING_SESSION_FACTORY
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    engine = create_engine(
        f"sqlite:///{TEST_DB_PATH}",
        connect_args={"check_same_thread": False},
    )
    TESTING_SESSION_FACTORY = sessionmaker(
        bind=engine, autocommit=False, autoflush=False
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TESTING_SESSION_FACTORY()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[db_dependency] = override_get_db
    main_module.get_db = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(db_dependency, None)
    if TESTING_SESSION_FACTORY:
        TESTING_SESSION_FACTORY.close_all()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
def db_session(client):
    if TESTING_SESSION_FACTORY is None:
        raise RuntimeError("Session factory not initialized")
    session = TESTING_SESSION_FACTORY()
    try:
        yield session
    finally:
        # Ensure database state is isolated between tests
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()
