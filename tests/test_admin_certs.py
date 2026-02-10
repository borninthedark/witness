"""Tests for admin certification HTMX mutations (status, visibility, delete, add)."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from fitness.auth import current_active_user
from fitness.main import app
from fitness.models.certification import Certification

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


def _seed_cert(db_session, **overrides) -> Certification:
    """Insert a certification and return it."""
    defaults = dict(
        slug="test-cert",
        title="Test Cert",
        issuer="TestOrg",
        pdf_url="/static/certs/test-cert.pdf",
        sha256="a" * 64,
        status="active",
        is_visible=True,
        is_active=True,
    )
    defaults.update(overrides)
    cert = Certification(**defaults)
    db_session.add(cert)
    db_session.commit()
    db_session.refresh(cert)
    return cert


# ── Auth-guard tests ─────────────────────────────────────────────


class TestCertAuthRequired:
    def test_status_change_requires_auth(self, client):
        resp = client.post("/admin/certs/1/status", data={"status": "active"})
        assert resp.status_code in (302, 401)

    def test_visibility_toggle_requires_auth(self, client):
        resp = client.post("/admin/certs/1/visibility", data={})
        assert resp.status_code in (302, 401)

    def test_delete_requires_auth(self, client):
        resp = client.delete("/admin/certs/1")
        assert resp.status_code in (302, 401)


# ── Status change tests ─────────────────────────────────────────


class TestCertStatusChange:
    def test_status_change_updates_db(self, auth_client, db_session):
        cert = _seed_cert(db_session)
        resp = auth_client.post(
            f"/admin/certs/{cert.id}/status",
            data={"status": "deprecated", "csrf_token": CSRF_TOKEN},
        )
        assert resp.status_code == 200
        assert resp.headers.get("HX-Refresh") == "true"
        db_session.refresh(cert)
        assert cert.status == "deprecated"
        assert cert.is_active is False

    def test_status_change_invalid_value(self, auth_client, db_session):
        cert = _seed_cert(db_session)
        resp = auth_client.post(
            f"/admin/certs/{cert.id}/status",
            data={"status": "invalid", "csrf_token": CSRF_TOKEN},
        )
        assert resp.status_code == 400

    def test_status_change_cert_not_found(self, auth_client):
        resp = auth_client.post(
            "/admin/certs/99999/status",
            data={"status": "active", "csrf_token": CSRF_TOKEN},
        )
        assert resp.status_code == 404


# ── Visibility toggle tests ─────────────────────────────────────


class TestCertVisibilityToggle:
    def test_visibility_toggle_flips(self, auth_client, db_session):
        cert = _seed_cert(db_session, is_visible=True)
        resp = auth_client.post(
            f"/admin/certs/{cert.id}/visibility",
            data={"csrf_token": CSRF_TOKEN},
        )
        assert resp.status_code == 200
        assert resp.headers.get("HX-Refresh") == "true"
        db_session.refresh(cert)
        assert cert.is_visible is False

    def test_visibility_toggle_cert_not_found(self, auth_client):
        resp = auth_client.post(
            "/admin/certs/99999/visibility",
            data={"csrf_token": CSRF_TOKEN},
        )
        assert resp.status_code == 404


# ── Delete tests ─────────────────────────────────────────────────


class TestCertDelete:
    def test_delete_removes_cert(self, auth_client, db_session):
        cert = _seed_cert(db_session, slug="delete-me")
        cert_id = cert.id
        with patch("fitness.routers.admin.Path.exists", return_value=False):
            resp = auth_client.delete(f"/admin/certs/{cert_id}")
        assert resp.status_code == 200
        assert db_session.query(Certification).filter_by(id=cert_id).first() is None

    def test_delete_cert_not_found(self, auth_client):
        resp = auth_client.delete("/admin/certs/99999")
        assert resp.status_code == 404


# ── Add cert test ────────────────────────────────────────────────


class TestCertAdd:
    def test_add_cert(self, auth_client, db_session):
        pdf_content = b"%PDF-1.4 fake content"
        with (
            patch(
                "fitness.routers.admin.LocalStorage.save",
                return_value="/static/certs/new-cert.pdf",
            ),
            patch("fitness.routers.admin.hash_file", return_value="b" * 64),
        ):
            resp = auth_client.post(
                "/admin/certs",
                data={
                    "slug": "new-cert",
                    "title": "New Cert",
                    "issuer": "NewOrg",
                    "verification_url": "",
                    "assertion_url": "",
                    "csrf_token": CSRF_TOKEN,
                },
                files={
                    "file": ("new-cert.pdf", BytesIO(pdf_content), "application/pdf")
                },
            )
        assert resp.status_code == 200
        cert = db_session.query(Certification).filter_by(slug="new-cert").first()
        assert cert is not None
        assert cert.title == "New Cert"
        assert cert.issuer == "NewOrg"
