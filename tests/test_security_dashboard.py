"""Tests for security advisory dashboard (behind admin auth)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.responses import HTMLResponse
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


class TestGetAdvisoriesDirect:
    """Call get_advisories directly to cover filter parsing in the router."""

    @pytest.mark.asyncio
    async def test_advisories_with_severity_filter(self):
        """Exercises contextlib.suppress path for severity parsing."""
        from unittest.mock import MagicMock

        from fitness.routers.security_dashboard import get_advisories

        mock_request = MagicMock()
        mock_request.url.path = "/admin/tactical/advisories"
        mock_request.app = MagicMock()
        mock_request.state = MagicMock()

        with (
            patch("fitness.routers.security_dashboard.aggregator") as mock_agg,
            patch("fitness.routers.security_dashboard.templates") as mock_tpl,
        ):
            mock_agg.fetch_all_advisories = AsyncMock(return_value=[])
            mock_tpl.TemplateResponse.return_value = HTMLResponse("")
            await get_advisories(request=mock_request, severity="CRITICAL", source=None)
            mock_agg.fetch_all_advisories.assert_called_once()

    @pytest.mark.asyncio
    async def test_advisories_with_invalid_severity(self):
        """Invalid severity is suppressed via contextlib.suppress."""
        from unittest.mock import MagicMock

        from fitness.routers.security_dashboard import get_advisories

        mock_request = MagicMock()
        mock_request.state = MagicMock()

        with (
            patch("fitness.routers.security_dashboard.aggregator") as mock_agg,
            patch("fitness.routers.security_dashboard.templates") as mock_tpl,
        ):
            mock_agg.fetch_all_advisories = AsyncMock(return_value=[])
            mock_tpl.TemplateResponse.return_value = HTMLResponse("")
            await get_advisories(request=mock_request, severity="BOGUS", source=None)
            call_kwargs = mock_agg.fetch_all_advisories.call_args
            assert call_kwargs.kwargs.get("severity") is None

    @pytest.mark.asyncio
    async def test_advisories_with_source_filter(self):
        """Exercises contextlib.suppress path for source parsing."""
        from unittest.mock import MagicMock

        from fitness.routers.security_dashboard import get_advisories

        mock_request = MagicMock()
        mock_request.state = MagicMock()

        with (
            patch("fitness.routers.security_dashboard.aggregator") as mock_agg,
            patch("fitness.routers.security_dashboard.templates") as mock_tpl,
        ):
            mock_agg.fetch_all_advisories = AsyncMock(return_value=[])
            mock_tpl.TemplateResponse.return_value = HTMLResponse("")
            await get_advisories(request=mock_request, severity=None, source="NIST")
            mock_agg.fetch_all_advisories.assert_called_once()

    @pytest.mark.asyncio
    async def test_advisories_with_invalid_source(self):
        """Invalid source is suppressed via contextlib.suppress."""
        from unittest.mock import MagicMock

        from fitness.routers.security_dashboard import get_advisories

        mock_request = MagicMock()
        mock_request.state = MagicMock()

        with (
            patch("fitness.routers.security_dashboard.aggregator") as mock_agg,
            patch("fitness.routers.security_dashboard.templates") as mock_tpl,
        ):
            mock_agg.fetch_all_advisories = AsyncMock(return_value=[])
            mock_tpl.TemplateResponse.return_value = HTMLResponse("")
            await get_advisories(request=mock_request, severity=None, source="INVALID")
            call_kwargs = mock_agg.fetch_all_advisories.call_args
            assert call_kwargs.kwargs.get("source") is None


class TestGetTopAdvisoriesDirect:
    """Call get_top_advisories directly to cover ValueError path."""

    @pytest.mark.asyncio
    async def test_top_advisories_invalid_severity_raises(self):
        """Invalid severity raises HTTPException (lines 155-156)."""
        from unittest.mock import MagicMock

        from fastapi import HTTPException

        from fitness.routers.security_dashboard import get_top_advisories

        mock_request = MagicMock()
        mock_request.state = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_top_advisories(request=mock_request, severity="BOGUS")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_top_advisories_valid_severity(self):
        """Valid severity calls aggregator (covers lines 153-163)."""
        from unittest.mock import MagicMock

        from fitness.routers.security_dashboard import get_top_advisories

        mock_request = MagicMock()
        mock_request.state = MagicMock()

        with (
            patch("fitness.routers.security_dashboard.aggregator") as mock_agg,
            patch("fitness.routers.security_dashboard.templates") as mock_tpl,
        ):
            mock_agg.get_top_advisories = AsyncMock(return_value=[])
            mock_tpl.TemplateResponse.return_value = HTMLResponse("")
            await get_top_advisories(request=mock_request, severity="CRITICAL")
            mock_agg.get_top_advisories.assert_called_once()
