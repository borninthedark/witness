"""Add users table and verification url column.

Revision ID: 20241119_01
Revises:
Create Date: 2024-11-19 00:00:00
"""

# pylint: disable=invalid-name,missing-module-docstring

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from alembic import op

# revision identifiers, used by Alembic.
revision = "20241119_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("users"):
        try:
            op.create_table(
                "users",
                sa.Column("id", sa.String(length=36), primary_key=True),
                sa.Column("email", sa.String(length=320), nullable=False),
                sa.Column("hashed_password", sa.String(length=1024), nullable=False),
                sa.Column(
                    "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
                ),
                sa.Column(
                    "is_superuser",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
                sa.Column(
                    "is_verified",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
                sa.Column("first_name", sa.String(length=255), nullable=True),
                sa.Column("last_name", sa.String(length=255), nullable=True),
            )
            op.create_index("ix_users_email", "users", ["email"], unique=True)
        except OperationalError as exc:
            if "already exists" not in str(exc).lower():
                raise

    if inspector.has_table("certifications"):
        cert_cols = {col["name"] for col in inspector.get_columns("certifications")}
        if "verification_url" not in cert_cols:
            try:
                op.add_column(
                    "certifications",
                    sa.Column(
                        "verification_url",
                        sa.String(length=1024),
                        nullable=False,
                        server_default="",
                    ),
                )
            except OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise


def downgrade():
    op.drop_column("certifications", "verification_url")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
