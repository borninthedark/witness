"""Tests for fitness/middleware/security.py — SecurityHeadersMiddleware."""

from __future__ import annotations

from starlette.testclient import TestClient

from fitness.middleware.security import SecurityHeadersMiddleware


class TestSecurityMiddleware:
    """Verify security headers are set on responses."""

    def test_csp_headers_present(self, client):
        """Content-Security-Policy header is set."""
        resp = client.get("/healthz")
        assert "Content-Security-Policy" in resp.headers

    def test_xframe_options_present(self, client):
        """X-Frame-Options header is present."""
        resp = client.get("/healthz")
        assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"

    def test_content_type_nosniff(self, client):
        """X-Content-Type-Options: nosniff is set."""
        resp = client.get("/healthz")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_referrer_policy_present(self, client):
        """Referrer-Policy header is set."""
        resp = client.get("/healthz")
        assert "Referrer-Policy" in resp.headers

    def test_permissions_policy_present(self, client):
        """Permissions-Policy header is set."""
        resp = client.get("/healthz")
        assert "Permissions-Policy" in resp.headers

    def test_csp_contains_default_src(self, client):
        """CSP includes default-src directive."""
        resp = client.get("/healthz")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "default-src" in csp

    def test_cross_origin_headers(self, client):
        """Cross-origin protections are present."""
        resp = client.get("/healthz")
        assert resp.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
        assert resp.headers.get("Cross-Origin-Resource-Policy") == "same-origin"


class TestSecurityMiddlewareNonce:
    """Verify CSP nonce injection into script-src and style-src."""

    def test_nonce_injected_into_csp(self):
        """When use_nonce=True, CSP contains nonce- directives."""
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route

        def homepage(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(
            SecurityHeadersMiddleware,
            use_nonce=True,
            csp_directives=[
                "default-src 'self'",
                "script-src 'self'",
                "style-src 'self'",
            ],
        )
        tc = TestClient(app)
        resp = tc.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "'nonce-" in csp
        assert "script-src 'self' 'nonce-" in csp
        assert "style-src 'self' 'nonce-" in csp

    def test_hsts_on_skip_host(self):
        """HSTS header is not set for skip_hsts_hosts."""
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route

        def homepage(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(
            SecurityHeadersMiddleware,
            skip_hsts_hosts={"testserver"},
            enable_hsts_on_http=True,
        )
        tc = TestClient(app)
        resp = tc.get("/")
        assert "Strict-Transport-Security" not in resp.headers

    def test_extra_csp_appended(self):
        """extra_csp string is appended to CSP."""
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route

        def homepage(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(
            SecurityHeadersMiddleware,
            extra_csp="frame-ancestors 'none'",
        )
        tc = TestClient(app)
        resp = tc.get("/")
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors 'none'" in csp
