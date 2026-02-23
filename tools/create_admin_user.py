#!/usr/bin/env python3
"""Create admin user from environment variables on startup."""

import asyncio
import sys

from fitness.auth import get_user_db, get_user_manager
from fitness.config import settings
from fitness.database_async import AsyncSessionLocal
from fitness.schemas.user import UserCreate


async def create_admin_user():
    """Create admin user if it doesn't exist."""
    async with AsyncSessionLocal() as session, session.begin():
        async for user_db in get_user_db(session):
            async for user_manager in get_user_manager(user_db):
                # Check if admin user already exists
                try:
                    existing_user = await user_manager.get_by_email(
                        settings.admin_username
                    )
                    if existing_user:
                        username = settings.admin_username
                        print(f"✅ Admin user '{username}' already exists")
                        return
                except Exception:  # noqa: S110
                    pass  # user doesn't exist yet — fall through to create

                # Create admin user
                try:
                    user = await user_manager.create(
                        UserCreate(
                            email=settings.admin_username,
                            password=settings.admin_password,
                            is_superuser=True,
                            is_verified=True,
                        )
                    )
                    print(f"✅ Created admin user: {user.email}")
                except Exception as e:
                    print(f"❌ Failed to create admin user: {e}", file=sys.stderr)
                    raise


if __name__ == "__main__":
    asyncio.run(create_admin_user())
