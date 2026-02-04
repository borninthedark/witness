"""Security façade for CSRF, rate limiting, and headers middleware."""

# Re-export CSRF helpers
# Re-export the headers middleware from its actual module path (no collision)
from fitness.middleware.security import SecurityHeadersMiddleware  # noqa: F401

from .csrf import (  # noqa: F401
    CSRF_COOKIE_NAME,
    issue_csrf_token,
    set_csrf_cookie,
    validate_csrf,
    verify_csrf_header,
)

# Re-export limiter
from .rate_limit import limiter  # noqa: F401

# Re-export nonce util
from .utils import generate_nonce  # noqa: F401

__all__ = [
    "CSRF_COOKIE_NAME",
    "issue_csrf_token",
    "set_csrf_cookie",
    "validate_csrf",
    "verify_csrf_header",
    "generate_nonce",
    "limiter",
    "SecurityHeadersMiddleware",
]
