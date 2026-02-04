"""Legacy SQL Server engine event helpers (unused in SQLite-only mode)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, DisconnectionError


def _configure_sql_server(dbapi_connection: Any, connection_record: Any) -> None:
    """Ensure new SQL Server connections have expected session options."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SET IMPLICIT_TRANSACTIONS OFF")
        cursor.execute("SET QUOTED_IDENTIFIER ON")
    finally:
        cursor.close()


def _ping_connection(connection: Any, branch: Any) -> None:
    """Ping SQL Server connections so invalid sockets are recycled."""
    if branch:
        return
    try:
        connection.execution_options(isolation_level="AUTOCOMMIT").execute(
            text("SELECT 1")
        )
    except DBAPIError as err:
        if err.connection_invalidated:
            connection.execution_options(isolation_level="AUTOCOMMIT").execute(
                text("SELECT 1")
            )
        else:  # pragma: no cover - passthrough to SQLAlchemy
            raise


def _validate_connection(
    dbapi_connection: Any, connection_record: Any, connection_proxy: Any
) -> None:
    """Validate pooled connections before checkout."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SELECT 1")
    except Exception as exc:  # pragma: no cover - depends on backend failures
        raise DisconnectionError() from exc
    finally:
        cursor.close()


def attach_sql_server_listeners(engine: Engine) -> None:
    """Attach connection/pool listeners for SQL Server backends."""
    event.listen(engine, "connect", _configure_sql_server)
    event.listen(engine, "engine_connect", _ping_connection)
    event.listen(engine.pool, "checkout", _validate_connection)
