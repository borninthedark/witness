"""Tests for custom 404 error page."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_404_page_returns_custom_template_for_html_request(client: TestClient):
    """Test that 404 errors return custom LCARS-styled template for HTML requests."""
    response = client.get("/nonexistent-page", headers={"Accept": "text/html"})
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    # Check for LCARS-specific content
    assert "404" in response.text
    assert "RESOURCE NOT FOUND" in response.text
    assert "ship's database" in response.text.lower()


def test_404_page_returns_json_for_api_request(client: TestClient):
    """Test that 404 errors return JSON for API requests."""
    response = client.get(
        "/nonexistent-api-endpoint", headers={"Accept": "application/json"}
    )
    assert response.status_code == 404
    assert "application/json" in response.headers["content-type"]
    data = response.json()
    assert "detail" in data


def test_404_page_includes_navigation_links(client: TestClient):
    """Test that 404 page includes helpful navigation links."""
    response = client.get("/does-not-exist", headers={"Accept": "text/html"})
    assert response.status_code == 404
    # Check for navigation links
    assert 'href="/"' in response.text  # Home link
    assert 'href="/certs"' in response.text  # Certifications link
    assert 'href="/resume"' in response.text  # Resume link
    assert 'href="/admin/status"' in response.text  # Status link
    assert 'href="/contact"' in response.text  # Contact link


def test_404_page_has_lcars_styling(client: TestClient):
    """Test that 404 page has LCARS theming."""
    response = client.get("/missing", headers={"Accept": "text/html"})
    assert response.status_code == 404
    # Check for LCARS-specific CSS classes and styling
    assert "error-code" in response.text
    assert "error-message" in response.text
    assert "lcars-divider" in response.text
    assert "--lcars-" in response.text  # CSS variables
