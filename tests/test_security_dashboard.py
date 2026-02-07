"""Tests for security advisory dashboard (behind admin auth)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from fitness.main import app


@pytest.mark.asyncio
async def test_security_dashboard():
    """Test tactical dashboard requires auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/admin/tactical/dashboard", follow_redirects=False)
    assert response.status_code in [302, 401]


@pytest.mark.asyncio
async def test_get_advisories():
    """Test advisories endpoint requires auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/admin/tactical/advisories?days=7", follow_redirects=False
        )
    assert response.status_code in [302, 401]


@pytest.mark.asyncio
async def test_get_advisories_with_filters():
    """Test advisories endpoint with filters requires auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/admin/tactical/advisories?days=30&severity=CRITICAL&source=NIST",
            follow_redirects=False,
        )
    assert response.status_code in [302, 401]


@pytest.mark.asyncio
async def test_get_stats():
    """Test stats endpoint requires auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/admin/tactical/stats?days=30", follow_redirects=False)
    assert response.status_code in [302, 401]
