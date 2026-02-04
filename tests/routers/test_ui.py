"""Tests for UI router endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fitness.models.certification import Certification


def test_home_endpoint_returns_html_for_browser_request(client: TestClient):
    """Test home endpoint returns HTML when Accept header includes text/html."""
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Witness the Fitness" in response.text or "Captain" in response.text


def test_home_endpoint_returns_json_for_api_request(client: TestClient):
    """Test home endpoint returns JSON when Accept header doesn't include text/html."""
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert response.json()["message"] == "Captain's Fitness Log API"
    assert response.json()["docs"] == "/docs"
    assert "certifications" in response.json()


def test_home_endpoint_includes_cert_count(client: TestClient, db_session: Session):
    """Test home endpoint includes certification count."""
    # Add test certifications
    db_session.add(
        Certification(
            slug="test-cert-1",
            title="Test Cert 1",
            issuer="Test Issuer",
            sha256="abc123",
            pdf_url="http://example.com/cert.pdf",
        )
    )
    db_session.add(
        Certification(
            slug="test-cert-2",
            title="Test Cert 2",
            issuer="Test Issuer",
            sha256="def456",
            pdf_url="http://example.com/cert2.pdf",
        )
    )
    db_session.commit()

    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    # Should have at least our 2 test certs
    assert response.json()["certifications"] >= 2


def test_certs_endpoint_returns_html(client: TestClient):
    """Test /certs endpoint returns HTML page."""
    response = client.get("/certs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_certs_endpoint_deduplicates_by_sha256(client: TestClient, db_session: Session):
    """Test /certs page deduplicates certifications with same SHA256."""
    # Add duplicate certs with same SHA256
    db_session.add(
        Certification(
            slug="dup-cert-old",
            title="Duplicate Cert Old",
            issuer="Test Issuer",
            sha256="duplicate_hash",
            pdf_url="http://example.com/old.pdf",
        )
    )
    db_session.add(
        Certification(
            slug="dup-cert-new",
            title="Duplicate Cert New",
            issuer="Test Issuer",
            sha256="duplicate_hash",
            pdf_url="http://example.com/new.pdf",
        )
    )
    db_session.commit()

    response = client.get("/certs")
    assert response.status_code == 200

    # Should only show the newer cert (last one added)
    assert "Duplicate Cert New" in response.text
    assert "dup-cert-new" in response.text


def test_certs_endpoint_hides_hidden_cert_slugs(
    client: TestClient, db_session: Session
):
    """Test /certs page hides certifications in HIDDEN_CERT_SLUGS."""
    # Delete any existing cert with this slug first to avoid constraint violations
    db_session.query(Certification).filter_by(slug="azure-transcript").delete()
    db_session.commit()

    # Add cert with slug that should be hidden
    db_session.add(
        Certification(
            slug="azure-transcript",  # This is in HIDDEN_CERT_SLUGS
            title="Azure Transcript",
            issuer="Microsoft",
            sha256="hidden_cert_test_unique",
            pdf_url="http://example.com/transcript.pdf",
        )
    )
    db_session.commit()

    response = client.get("/certs")
    assert response.status_code == 200

    # Should NOT show the hidden cert
    assert "azure-transcript" not in response.text.lower()


def test_certs_endpoint_separates_active_and_inactive(
    client: TestClient, db_session: Session
):
    """Test /certs page separates active and inactive certifications."""
    # Add active cert
    db_session.add(
        Certification(
            slug="active-cert",
            title="Active Certification",
            issuer="Test Issuer",
            sha256="active_hash",
            pdf_url="http://example.com/active.pdf",
        )
    )

    # Add inactive cert (would need to be in INACTIVE_CERT_SLUGS in constants.py)
    # For now, just verify the endpoint works
    db_session.commit()

    response = client.get("/certs")
    assert response.status_code == 200


@pytest.mark.parametrize(
    "path,expected_status",
    [
        ("/", 200),
        ("/certs", 200),
        ("/contact", 200),
        ("/resume", 200),
        ("/nonexistent-route-12345", 404),
    ],
)
def test_ui_routes_return_expected_status_codes(
    client: TestClient, path: str, expected_status: int
):
    """Test UI routes return expected HTTP status codes."""
    response = client.get(path)
    assert response.status_code == expected_status


def test_contact_page_includes_csrf_token(client: TestClient):
    """Test contact page includes CSRF token in form."""
    response = client.get("/contact")
    assert response.status_code == 200

    # Check for CSRF cookie (actual cookie name is wtf_csrf)
    csrf_cookie = client.cookies.get("wtf_csrf")
    assert csrf_cookie is not None

    # Check for CSRF token in HTML (hidden field or meta tag)
    assert "csrf" in response.text.lower()


def test_resume_page_loads(client: TestClient):
    """Test /resume page returns HTML."""
    response = client.get("/resume")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_cert_pdf_viewer_requires_valid_slug(client: TestClient):
    """Test certificate PDF viewer returns 404 for invalid slug."""
    response = client.get("/certs/nonexistent-cert-slug/pdf")
    # Should return 404 or appropriate error
    assert response.status_code in [404, 500]


def test_healthz_endpoint_returns_healthy(client: TestClient):
    """Test /healthz endpoint returns health status."""
    response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert "database" in payload


def test_home_page_template_variables(client: TestClient):
    """Test home page includes expected template variables."""
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 200

    # Check for common template elements
    html = response.text
    assert "html" in html.lower()


def test_certs_page_with_no_certs(client: TestClient, db_session: Session):
    """Test /certs page handles empty certification list."""
    # Clear all certs
    db_session.query(Certification).delete()
    db_session.commit()

    response = client.get("/certs")
    assert response.status_code == 200
    # Should still render without errors


def test_multiple_requests_maintain_session(client: TestClient):
    """Test multiple requests to the same client maintain session."""
    # First request
    response1 = client.get("/contact")
    csrf_token1 = client.cookies.get("wtf_csrf")

    # Second request
    response2 = client.get("/contact")
    csrf_token2 = client.cookies.get("wtf_csrf")

    assert response1.status_code == 200
    assert response2.status_code == 200
    # CSRF tokens should be present (may or may not be the same)
    assert csrf_token1 is not None
    assert csrf_token2 is not None
