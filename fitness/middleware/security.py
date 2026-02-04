from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def _is_secure_request(request: Request) -> bool:
    # Honor reverse proxy headers if present
    xf_proto = request.headers.get("x-forwarded-proto")
    if xf_proto:
        return "https" in xf_proto
    return request.url.scheme == "https"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Sets a hardened set of security headers on every response.
    - HTTPS-aware HSTS
    - Strict CSP with optional per-request nonce
    - Modern cross-origin protections
    """

    def __init__(
        self,
        app,
        *,
        # Base CSP directives; a per-request nonce will be appended
        # to script/style if use_nonce=True
        csp_directives: Iterable[str] | None = None,
        use_nonce: bool = True,
        report_only: bool = False,  # flip to True for CSP-Report-Only during rollout
        extra_csp: str | None = None,  # append raw directives if needed
        hsts: str = "max-age=63072000; includeSubDomains; preload",
        referrer_policy: str = "strict-origin-when-cross-origin",
        permissions_policy: str = "geolocation=(), microphone=(), camera=()",
        add_coop_corp: bool = True,
        enable_hsts_on_http: bool = False,  # leave False: avoid HSTS in dev/http
        skip_hsts_hosts: set[str] | None = None,
        frame_options: str = "SAMEORIGIN",  # allow same-origin iframes (for PDF embeds)
    ) -> None:
        super().__init__(app)
        self.use_nonce = use_nonce
        self.report_only = report_only
        self.extra_csp = extra_csp
        self.hsts = hsts
        self.referrer_policy = referrer_policy
        self.permissions_policy = permissions_policy
        self.add_coop_corp = add_coop_corp
        self.enable_hsts_on_http = enable_hsts_on_http
        self.skip_hsts_hosts = skip_hsts_hosts or {"localhost", "127.0.0.1"}
        self.frame_options = frame_options

        # Safe, strict baseline. You can extend with extra_csp.
        default_csp = [
            "default-src 'self'",
            "base-uri 'none'",
            "frame-ancestors 'self'",  # ← allow same-origin frames (PDF iframes)
            "img-src 'self' data:",
            "font-src 'self'",
            "connect-src 'self'",
            # If you self-host all CSS/JS, these stay strict.
            # Nonces get added to script-src/style-src at runtime if use_nonce=True.
            "script-src 'self'",
            "style-src 'self'",
            # Mixed content hardening (harmless under full HTTPS)
            "upgrade-insecure-requests",
        ]
        self.csp_directives = list(csp_directives or default_csp)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate a nonce if desired and expose it on request.state for templates
        nonce = None
        if self.use_nonce:
            nonce = secrets.token_urlsafe(16)
            # Templates can set <script nonce="..."> / inline <style nonce="...">
            setattr(request.state, "csp_nonce", nonce)

        # Build CSP string (append nonce to script/style if present)
        csp_parts: list[str] = []
        for d in self.csp_directives:
            if nonce and d.startswith("script-src"):
                d = f"{d} 'nonce-{nonce}'"
            if nonce and d.startswith("style-src"):
                d = f"{d} 'nonce-{nonce}'"
            csp_parts.append(d)
        if self.extra_csp:
            csp_parts.append(self.extra_csp.strip())
        csp_value = "; ".join(csp_parts)

        response = await call_next(request)

        # CSP (or report-only for soft rollouts)
        csp_header = (
            "Content-Security-Policy-Report-Only"
            if self.report_only
            else "Content-Security-Policy"
        )
        response.headers.setdefault(csp_header, csp_value)

        # HSTS: only on HTTPS and non-dev hosts unless explicitly enabled
        if _is_secure_request(request) or self.enable_hsts_on_http:
            if request.url.hostname not in self.skip_hsts_hosts:
                response.headers.setdefault("Strict-Transport-Security", self.hsts)

        # Modern, practical defaults
        response.headers.setdefault("Referrer-Policy", self.referrer_policy)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault(
            "X-Frame-Options", self.frame_options
        )  # SAMEORIGIN by default

        # Cross-origin protections
        if self.add_coop_corp:
            response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
            response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
            # COEP is powerful but breaking; enable only if required:
            # response.headers.setdefault(
            #     "Cross-Origin-Embedder-Policy", "require-corp"
            # )

        # Reasonable, locked-down capabilities
        if self.permissions_policy:
            response.headers.setdefault("Permissions-Policy", self.permissions_policy)

        # Optional/legacy but harmless
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        response.headers.setdefault("Origin-Agent-Cluster", "?1")

        return response
