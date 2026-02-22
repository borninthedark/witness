"""Tests for fitness/middleware/security.py — SecurityHeadersMiddleware."""

from __future__ import annotations


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
