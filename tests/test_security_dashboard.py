"""Tests for security advisory dashboard."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from fitness.main import app


@pytest.mark.asyncio
async def test_security_dashboard():
    """Test security dashboard page loads."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/security/dashboard")
    assert response.status_code == 200
    assert b"Advisory Dashboard" in response.content


@pytest.mark.asyncio
async def test_get_advisories():
    """Test advisories endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/security/advisories?days=7")
    assert response.status_code == 200
    # Should contain advisory container
    assert b"advisories-container" in response.content


@pytest.mark.asyncio
async def test_get_advisories_with_filters():
    """Test advisories endpoint with filters."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(
            "/security/advisories?days=30&severity=CRITICAL&source=NIST"
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_stats():
    """Test stats endpoint with Chart.js doughnut chart."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/security/stats?days=30")
    assert response.status_code == 200
    # Should contain stats grid
    assert b"stats-grid" in response.content
    # Should contain Chart.js doughnut chart
    assert b"severity-doughnut-chart" in response.content
    assert b"chart.min.js" in response.content
    # Should contain chart configuration
    assert b"doughnut" in response.content
