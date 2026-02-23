import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi_users import FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.manager import BaseUserManager
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from fitness.config import settings
from fitness.database_async import get_async_session
from fitness.models.user import User


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    def __init__(self, user_db: SQLAlchemyUserDatabase[User, uuid.UUID]):
        super().__init__(user_db)

    async def on_after_register(
        self, user: User, request: Request | None = None
    ) -> None:  # pragma: no cover - hook for future use
        return


async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase[User, uuid.UUID]]:
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase[User, uuid.UUID] = Depends(get_user_db),
) -> AsyncGenerator[UserManager]:
    yield UserManager(user_db)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.secret_key,
        lifetime_seconds=settings.jwt_lifetime_seconds,
        token_audience=["fastapi-users:auth"],
    )


cookie_transport = CookieTransport(
    cookie_name=settings.auth_cookie_name,
    cookie_secure=settings.is_production,
    cookie_max_age=settings.jwt_lifetime_seconds,
    cookie_httponly=True,
)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)
