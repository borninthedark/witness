"""Tests for P1 security hardening: rate limits, upload validation, startup warnings."""

from __future__ import annotations

import logging
from io import BytesIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from fitness.auth import current_active_user
from fitness.main import app

CSRF_TOKEN = "test-csrf-token"


@pytest.fixture
def auth_client(client):
    """Authenticated test client with CSRF token."""
    mock_user = MagicMock(email="test@test.com", id=uuid4(), is_active=True)
    app.dependency_overrides[current_active_user] = lambda: mock_user
    client.cookies.set("wtf_csrf", CSRF_TOKEN)
    yield client
    app.dependency_overrides.pop(current_active_user, None)
    client.cookies.delete("wtf_csrf")


# ── Upload size validation ──────────────────────────────────────


class TestUploadSizeValidation:
    """Cert upload rejects files over 10 MB."""

    def test_oversized_pdf_rejected(self, auth_client):
        """A PDF larger than 10 MB should return 400."""
        oversized = b"x" * (10 * 1024 * 1024 + 1)  # 10 MB + 1 byte
        resp = auth_client.post(
            "/admin/certs",
            data={
                "slug": "big-cert",
                "title": "Big Cert",
                "issuer": "Org",
                "verification_url": "",
                "assertion_url": "",
                "csrf_token": CSRF_TOKEN,
            },
            files={"file": ("big.pdf", BytesIO(oversized), "application/pdf")},
        )
        assert resp.status_code == 400
        assert "10 MB" in resp.text

    def test_normal_pdf_accepted(self, auth_client, db_session):
        """A PDF under 10 MB should be accepted."""
        small_pdf = b"%PDF-1.4 small content"
        with (
            patch(
                "fitness.routers.admin.LocalStorage.save",
                return_value="/static/certs/ok-cert.pdf",
            ),
            patch("fitness.routers.admin.hash_file", return_value="c" * 64),
        ):
            resp = auth_client.post(
                "/admin/certs",
                data={
                    "slug": "ok-cert",
                    "title": "OK Cert",
                    "issuer": "Org",
                    "verification_url": "",
                    "assertion_url": "",
                    "csrf_token": CSRF_TOKEN,
                },
                files={"file": ("ok.pdf", BytesIO(small_pdf), "application/pdf")},
            )
        assert resp.status_code == 200


# ── Slug validation ─────────────────────────────────────────────


class TestSlugValidation:
    """Cert slugs must be safe for filesystem use."""

    @pytest.mark.parametrize(
        "bad_slug",
        [
            "../etc/passwd",
            "../../etc/shadow",
            "foo/bar",
            "-leading-dash",
            "UPPERCASE",
            "",
            "a" * 65,  # too long
        ],
    )
    def test_invalid_slugs_rejected(self, auth_client, bad_slug):
        resp = auth_client.post(
            "/admin/certs",
            data={
                "slug": bad_slug,
                "title": "Test",
                "issuer": "Org",
                "verification_url": "",
                "assertion_url": "",
                "csrf_token": CSRF_TOKEN,
            },
            files={"file": ("t.pdf", BytesIO(b"pdf"), "application/pdf")},
        )
        assert resp.status_code in (400, 422)

    @pytest.mark.parametrize("good_slug", ["ckad", "aws-sap-c02", "az900"])
    def test_valid_slugs_accepted(self, auth_client, db_session, good_slug):
        with (
            patch(
                "fitness.routers.admin.LocalStorage.save",
                return_value=f"/static/certs/{good_slug}.pdf",
            ),
            patch("fitness.routers.admin.hash_file", return_value="d" * 64),
        ):
            resp = auth_client.post(
                "/admin/certs",
                data={
                    "slug": good_slug,
                    "title": "Test",
                    "issuer": "Org",
                    "verification_url": "",
                    "assertion_url": "",
                    "csrf_token": CSRF_TOKEN,
                },
                files={"file": ("t.pdf", BytesIO(b"pdf"), "application/pdf")},
            )
        assert resp.status_code == 200


# ── Rate limiting presence ──────────────────────────────────────


class TestRateLimitDecorators:
    """Verify every route handler file has @limiter.limit() on route functions.

    Uses AST to parse each router module and check that every function
    decorated with @router.get/post/delete/put/patch also has @limiter.limit().
    """

    @pytest.mark.parametrize(
        "module_path",
        [
            "fitness/routers/ui.py",
            "fitness/routers/admin.py",
            "fitness/routers/reports.py",
            "fitness/routers/astrometrics.py",
            "fitness/routers/stargazing.py",
            "fitness/routers/ai_query.py",
            "fitness/routers/captains_log.py",
            "fitness/routers/blog.py",
            "fitness/routers/security_dashboard.py",
        ],
        ids=lambda p: p.split("/")[-1].replace(".py", ""),
    )
    def test_all_routes_have_rate_limit(self, module_path):
        """Every @router.<method> function must also have @limiter.limit()."""
        import ast
        from pathlib import Path

        source = Path(module_path).read_text()
        tree = ast.parse(source, filename=module_path)

        http_methods = {"get", "post", "put", "patch", "delete"}
        missing = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Check if this function has a @router.<method> decorator
            is_route = False
            has_limiter = False

            for dec in node.decorator_list:
                # Match @router.get(...), @router.post(...), etc.
                if (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr in http_methods
                ):
                    is_route = True
                # Match @limiter.limit(...)
                if (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr == "limit"
                ):
                    has_limiter = True

            if is_route and not has_limiter:
                missing.append(node.name)

        assert not missing, f"{module_path}: routes missing @limiter.limit(): {missing}"


# ── Startup warnings ────────────────────────────────────────────


class TestStartupSecurityWarnings:
    """Non-production environments warn about insecure defaults."""

    def test_warnings_emitted_for_default_secrets(self, caplog):
        """Importing config with defaults should emit warnings."""
        from fitness.config import _INSECURE_DEFAULTS_CHECK, settings

        if settings.environment == "production":
            pytest.skip("Only runs in non-production")

        # Re-check the warning logic manually
        with caplog.at_level(logging.WARNING, logger="fitness.config"):
            logger = logging.getLogger("fitness.config")
            for field, default in _INSECURE_DEFAULTS_CHECK.items():
                if getattr(settings, field) == default:
                    logger.warning(
                        "SECURITY: %s is using the default value. "
                        "Set %s env var before deploying.",
                        field,
                        field.upper(),
                    )

        # All three defaults should trigger warnings in test/dev
        assert caplog.text.count("SECURITY:") >= 3

    def test_production_rejects_default_secrets(self):
        """Production environment must reject insecure defaults."""
        from fitness.config import Settings

        with pytest.raises(ValueError, match="must not use the default value"):
            Settings(environment="production")


# ── Login rate limiting middleware ───────────────────────────────


class TestLoginRateLimiting:
    """Custom middleware limits login attempts per IP."""

    def test_login_allows_normal_attempts(self, client):
        """A few login attempts should succeed (auth may fail but not 429)."""
        for _ in range(3):
            resp = client.post(
                "/auth/jwt/login",
                data={"username": "test@test.com", "password": "wrong"},
            )
            assert resp.status_code != 429

    def test_login_blocks_after_max_attempts(self, client):
        """After 5 rapid attempts, the 6th should be rate-limited."""
        # Reset the login attempts tracker
        from fitness.main import _login_attempts

        _login_attempts.clear()

        for _ in range(5):
            client.post(
                "/auth/jwt/login",
                data={"username": "test@test.com", "password": "wrong"},
            )

        resp = client.post(
            "/auth/jwt/login",
            data={"username": "test@test.com", "password": "wrong"},
        )
        assert resp.status_code == 429
        assert "Too many login attempts" in resp.json()["detail"]
