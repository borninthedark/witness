"""Tests for custom 401 unauthorized error page."""

from __future__ import annotations

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from fitness.main import app


def test_401_page_returns_custom_template_for_html_request(client: TestClient):
    """Test that 401 errors return custom LCARS-styled template for HTML requests."""

    # Add a test route that raises 401
    @app.get("/test-401-html")
    async def test_401_html():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Test 401 error",
        )

    response = client.get("/test-401-html", headers={"Accept": "text/html"})
    assert response.status_code == 401
    assert "text/html" in response.headers["content-type"]
    # Check for LCARS-specific content
    assert "401" in response.text
    assert "AUTHORIZATION REQUIRED" in response.text


def test_401_page_returns_json_for_api_request(client: TestClient):
    """Test that 401 errors return JSON for API requests."""

    @app.get("/test-401-json")
    async def test_401_json():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized access"
        )

    response = client.get("/test-401-json", headers={"Accept": "application/json"})
    assert response.status_code == 401
    assert "application/json" in response.headers["content-type"]
    data = response.json()
    assert "detail" in data


def test_401_page_includes_navigation_links(client: TestClient):
    """Test that 401 page includes helpful navigation links."""

    @app.get("/test-401-navigation")
    async def test_401_nav():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized"
        )

    response = client.get("/test-401-navigation", headers={"Accept": "text/html"})
    assert response.status_code == 401
    # Check for navigation links
    assert 'href="/"' in response.text  # Home link
    assert 'href="/certs"' in response.text  # Certifications link
    assert 'href="/resume"' in response.text  # Resume link
    assert 'href="/contact"' in response.text  # Contact link


def test_401_page_has_lcars_styling(client: TestClient):
    """Test that 401 page has LCARS theming."""

    @app.get("/test-401-styling")
    async def test_401_style():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth required"
        )

    response = client.get("/test-401-styling", headers={"Accept": "text/html"})
    assert response.status_code == 401
    # Check for LCARS-specific CSS classes and styling
    assert "error-code" in response.text
    assert "error-message" in response.text
    assert "lcars-divider" in response.text
    assert "--lcars-" in response.text  # CSS variables


def test_403_also_uses_401_template(client: TestClient):
    """Test that 403 Forbidden also uses the 401 template."""

    @app.get("/test-403-forbidden")
    async def test_403():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden resource"
        )

    response = client.get("/test-403-forbidden", headers={"Accept": "text/html"})
    assert response.status_code == 403
    assert "text/html" in response.headers["content-type"]
    # Should use same 401 template
    assert "401" in response.text  # Template shows 401 code
    assert "AUTHORIZATION REQUIRED" in response.text


def test_status_page_returns_401_without_auth(client: TestClient):
    """Test that /status/ returns 401 error page when accessed without auth."""
    response = client.get("/status/", headers={"Accept": "text/html"})
    assert response.status_code == 401
    assert "text/html" in response.headers["content-type"]
    assert "AUTHORIZATION REQUIRED" in response.text
