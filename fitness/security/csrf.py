from __future__ import annotations

import hmac
import secrets

from fastapi import HTTPException, Request, Response

from fitness.config import settings

CSRF_COOKIE_NAME = "wtf_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"


def issue_csrf_token(request: Request) -> str:
    token: str | None = getattr(request.state, "csrf_token", None)
    if token:
        return token
    incoming = request.cookies.get(CSRF_COOKIE_NAME)
    token = incoming or secrets.token_urlsafe(32)
    request.state.csrf_token = token
    return token


def set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        secure=not settings.debug,
        httponly=True,
        samesite="strict",
        max_age=60 * 60 * 12,
    )


def verify_csrf_header(request: Request) -> str | None:
    return request.headers.get(CSRF_HEADER_NAME)


def validate_csrf(request: Request, token: str | None) -> bool:
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = verify_csrf_header(request)
    candidate = token or header_token
    if not cookie_token or not candidate:
        raise HTTPException(status_code=403, detail="Invalid CSRF token.")
    if not hmac.compare_digest(cookie_token, candidate):
        raise HTTPException(status_code=403, detail="Invalid CSRF token.")
    return True
