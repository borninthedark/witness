"""Tests for security advisory dashboard (behind admin auth)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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


@pytest.mark.asyncio
async def test_shutdown_event():
    """Shutdown event calls aggregator.close() without error."""
    from fitness.routers.security_dashboard import shutdown_event

    with patch("fitness.routers.security_dashboard.aggregator") as mock_agg:
        mock_agg.close = AsyncMock()
        await shutdown_event()
        mock_agg.close.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown_event_suppresses_runtime_error():
    """Shutdown suppresses RuntimeError from aggregator.close()."""
    from fitness.routers.security_dashboard import shutdown_event

    with patch("fitness.routers.security_dashboard.aggregator") as mock_agg:
        mock_agg.close = AsyncMock(side_effect=RuntimeError("event loop closed"))
        await shutdown_event()  # should not raise


class TestSeverityFilterParsing:
    """Unit tests for contextlib.suppress filter parsing in get_advisories."""

    @pytest.mark.asyncio
    async def test_invalid_severity_ignored(self):
        """Invalid severity string is suppressed, not raised."""
        # Verify the contextlib.suppress path
        import contextlib

        from fitness.models.security import SeverityLevel

        severity_filter = None
        with contextlib.suppress(ValueError):
            severity_filter = SeverityLevel("BOGUS")
        assert severity_filter is None

    @pytest.mark.asyncio
    async def test_valid_severity_parsed(self):
        """Valid severity string is parsed to enum."""
        import contextlib

        from fitness.models.security import SeverityLevel

        severity_filter = None
        with contextlib.suppress(ValueError):
            severity_filter = SeverityLevel("CRITICAL")
        assert severity_filter == SeverityLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_invalid_source_ignored(self):
        """Invalid source string is suppressed."""
        import contextlib

        from fitness.models.security import AdvisorySource

        source_filter = None
        with contextlib.suppress(ValueError):
            source_filter = AdvisorySource("BOGUS")
        assert source_filter is None

    @pytest.mark.asyncio
    async def test_valid_source_parsed(self):
        """Valid source string is parsed to enum."""
        import contextlib

        from fitness.models.security import AdvisorySource

        source_filter = None
        with contextlib.suppress(ValueError):
            source_filter = AdvisorySource("NIST")
        assert source_filter == AdvisorySource.NIST
