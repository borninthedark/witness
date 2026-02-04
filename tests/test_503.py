"""Tests for custom 503 error page."""

from __future__ import annotations

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from fitness.main import app


def test_503_template_has_lcars_styling(client: TestClient):
    """Test that 503.html template has proper LCARS styling and content."""

    # Add a test route that raises 503
    @app.get("/test-503-error-styling")
    async def test_503_styling():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Test 503 error",
        )

    response = client.get("/test-503-error-styling", headers={"Accept": "text/html"})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "text/html" in response.headers["content-type"]

    # Check for LCARS-specific content
    assert "503" in response.text
    assert "SERVICE UNAVAILABLE" in response.text
    assert "systems are currently offline" in response.text.lower()

    # Check for LCARS styling elements
    assert "error-code" in response.text
    assert "error-message" in response.text
    assert "status-indicator" in response.text  # Blinking status light
    assert "lcars-divider" in response.text
    assert "--lcars-" in response.text  # CSS variables
    assert "lcars-amber" in response.text
    assert "lcars-red" in response.text  # 503 uses red for urgency


def test_503_returns_json_for_api_request(client: TestClient):
    """Test that 503 errors return JSON for API requests."""

    @app.get("/test-503-json-response")
    async def test_503_json():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service down"
        )

    response = client.get(
        "/test-503-json-response", headers={"Accept": "application/json"}
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "application/json" in response.headers["content-type"]
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Service down"


def test_503_template_includes_recovery_actions(client: TestClient):
    """Test that 503 page includes helpful recovery actions."""

    @app.get("/test-503-recovery-actions")
    async def test_503_recovery():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable",
        )

    response = client.get("/test-503-recovery-actions", headers={"Accept": "text/html"})

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    # Check for recovery action links
    assert "Retry Current Request" in response.text
    assert 'href="/"' in response.text  # Home link
    assert 'href="/status"' in response.text  # Status dashboard link
    assert 'href="/contact"' in response.text  # Contact/support link


def test_503_template_differs_from_404_styling(client: TestClient):
    """Test that 503 page uses different color scheme from 404."""

    @app.get("/test-503-vs-404-1")
    async def test_503_compare():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Down"
        )

    @app.get("/test-503-vs-404-2")
    async def test_404_compare():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    response_503 = client.get("/test-503-vs-404-1", headers={"Accept": "text/html"})
    response_404 = client.get("/test-503-vs-404-2", headers={"Accept": "text/html"})

    # 503 uses amber/red color scheme
    assert "lcars-amber" in response_503.text
    assert "lcars-red" in response_503.text
    assert "status-indicator" in response_503.text  # Blinking indicator

    # 404 uses peach/amber color scheme (different from 503)
    assert "lcars-peach" in response_404.text
    assert "status-indicator" not in response_404.text  # 404 doesn't have this
