"""Form security utilities: CSRF."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Optional

from fastapi import HTTPException, Request
from starlette.responses import Response

from fitness.config import settings

CSRF_COOKIE_NAME = "csrf_token"
CSRF_FORM_FIELD = "csrf_token"
CSRF_HASH_ALG = hashlib.sha256


def _urlsafe_b64(value: bytes) -> str:
    """Base64-url safe without padding."""
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _sign(value: bytes, secret: bytes) -> str:
    """HMAC-SHA256 signature for the given value."""
    sig = hmac.new(secret, value, CSRF_HASH_ALG).digest()
    return _urlsafe_b64(sig)


def issue_csrf(response: Response) -> str:
    """Issue a double-submit-cookie CSRF token and set it as a cookie.

    Returns the token so callers can embed it in a hidden form field.
    """
    secret = settings.csrf_secret.encode("utf-8")
    nonce = os.urandom(18)
    payload = _urlsafe_b64(nonce)
    sig = _sign(nonce, secret)
    token = f"{payload}.{sig}"

    # Cookie is not HttpOnly because the browser must echo it with the form.
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        max_age=60 * 60,  # 1 hour
        secure=settings.is_production,
        samesite="Lax",
        path="/",
    )
    return token


async def _get_form_token(request: Request) -> str:
    """Safely extract the CSRF token from the submitted form."""
    try:
        form = await request.form()
        token = form.get(CSRF_FORM_FIELD)
        if not token:
            raise HTTPException(status_code=400, detail="Missing CSRF token")
        return token
    except Exception as exc:  # narrow here if you prefer
        raise HTTPException(status_code=400, detail="Unable to read form data") from exc


async def verify_csrf(request: Request, token: Optional[str] = None) -> None:
    """Validate CSRF by comparing hidden-field value with cookie and signature.

    If ``token`` is not provided, it is read from the request form.
    """
    form_val = token or await _get_form_token(request)

    cookie_val = request.cookies.get(CSRF_COOKIE_NAME)
    if not cookie_val:
        raise HTTPException(status_code=400, detail="Missing CSRF cookie")

    if form_val != cookie_val:
        raise HTTPException(status_code=400, detail="CSRF mismatch")

    try:
        payload_b64, sig = form_val.split(".", 1)
        payload = base64.urlsafe_b64decode(payload_b64 + "===")
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail="Invalid CSRF token format"
        ) from exc

    expected = _sign(payload, settings.csrf_secret.encode("utf-8"))
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
