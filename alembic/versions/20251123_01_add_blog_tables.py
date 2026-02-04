"""Add blog_entries table for Captain's Personal Log.

Revision ID: 20251123_01
Revises: 20251115_01
Create Date: 2025-11-23 00:00:00
"""

# pylint: disable=invalid-name,missing-module-docstring

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251123_01"
down_revision = "20251115_01"
branch_labels = None
depends_on = None


def upgrade():
    """Create blog_entries table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Check if table already exists
    if inspector.has_table("blog_entries"):
        return

    # Create blog_entries table
    op.create_table(
        "blog_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("tags", sa.Text(), nullable=False, server_default=""),
        sa.Column("stardate", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "reading_time_minutes", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(op.f("ix_blog_entries_id"), "blog_entries", ["id"], unique=False)
    op.create_index(op.f("ix_blog_entries_slug"), "blog_entries", ["slug"], unique=True)
    op.create_index(
        op.f("ix_blog_entries_category"), "blog_entries", ["category"], unique=False
    )
    op.create_index(
        op.f("ix_blog_entries_status"), "blog_entries", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_blog_entries_created_at"),
        "blog_entries",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_blog_entries_published_at"),
        "blog_entries",
        ["published_at"],
        unique=False,
    )


def downgrade():
    """Drop blog_entries table."""
    op.drop_index(op.f("ix_blog_entries_published_at"), table_name="blog_entries")
    op.drop_index(op.f("ix_blog_entries_created_at"), table_name="blog_entries")
    op.drop_index(op.f("ix_blog_entries_status"), table_name="blog_entries")
    op.drop_index(op.f("ix_blog_entries_category"), table_name="blog_entries")
    op.drop_index(op.f("ix_blog_entries_slug"), table_name="blog_entries")
    op.drop_index(op.f("ix_blog_entries_id"), table_name="blog_entries")
    op.drop_table("blog_entries")
