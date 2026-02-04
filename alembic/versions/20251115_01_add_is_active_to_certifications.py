"""Add status and visibility columns to certifications table.

Revision ID: 20251115_01
Revises: 20241119_01
Create Date: 2025-11-15 00:00:00
"""

# pylint: disable=invalid-name,missing-module-docstring

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251115_01"
down_revision = "20241119_01"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column_name: str, column: sa.Column):
    """Add column to table if it doesn't already exist.

    Args:
        table_name: Name of the table to modify
        column_name: Name of the column to add
        column: SQLAlchemy Column object to add
    """
    try:
        op.add_column(table_name, column)
    except OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


def upgrade():
    """Add status, is_visible, and is_active columns to certifications table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("certifications"):
        return

    cert_cols = {col["name"] for col in inspector.get_columns("certifications")}

    # Add status column (active/deprecated/expired)
    if "status" not in cert_cols:
        _add_column_if_missing(
            "certifications",
            "status",
            sa.Column(
                "status",
                sa.String(length=50),
                nullable=False,
                server_default="active",
            ),
        )

    # Add is_visible column (public visibility control)
    if "is_visible" not in cert_cols:
        _add_column_if_missing(
            "certifications",
            "is_visible",
            sa.Column(
                "is_visible",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )

    # Add is_active column (legacy compatibility)
    if "is_active" not in cert_cols:
        _add_column_if_missing(
            "certifications",
            "is_active",
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )


def downgrade():
    """Remove status, is_visible, and is_active columns from certifications table."""
    op.drop_column("certifications", "status")
    op.drop_column("certifications", "is_visible")
    op.drop_column("certifications", "is_active")
