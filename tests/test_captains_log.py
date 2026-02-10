"""Tests for Captain's Log service and routes."""

from __future__ import annotations

import json
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from fitness.main import app
from fitness.services.captains_log import CaptainsLogService, compute_stardate

# ── Stardate ────────────────────────────────────────────────────


class TestComputeStardate:
    def test_format(self):
        """Stardate should be a float-like string with one decimal."""
        sd = compute_stardate()
        assert re.match(r"^\d{6}\.\d$", sd), f"Bad stardate format: {sd}"

    def test_range(self):
        """Stardate should be in the 101xxx-103xxx range for 2024-2026."""
        sd = float(compute_stardate())
        assert 101000.0 <= sd <= 104000.0


# ── Service unit tests ──────────────────────────────────────────


class TestCaptainsLogService:
    @pytest.mark.asyncio
    async def test_generate_entry_no_api_key(self):
        """generate_entry returns None when API key is unset."""
        svc = CaptainsLogService()
        with patch("fitness.services.captains_log.settings") as mock_settings:
            mock_settings.anthropic_api_key = None
            svc._client = None  # force re-check
            result = await svc.generate_entry({"stardate": "101500.0"})
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_entry_success(self):
        """generate_entry returns dict when AI call succeeds."""
        svc = CaptainsLogService()

        canned = {
            "title": "Test Log Entry",
            "summary": "A brief summary.",
            "content": "Full content here.",
            "tags": ["test", "ai"],
        }

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps(canned))]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        svc._client = mock_client

        telemetry = {
            "stardate": "101500.0",
            "timestamp": "2025-06-01T00:00:00+00:00",
            "cert_count": 5,
            "log_entry_count": 0,
            "cve_summary": "10 advisories in 7d (critical=1, high=3)",
        }
        result = await svc.generate_entry(telemetry)

        assert result is not None
        assert result["title"] == "Test Log Entry"
        assert result["stardate"] == "101500.0"
        assert isinstance(result["tags"], list)

    @pytest.mark.asyncio
    async def test_generate_entry_handles_api_error(self):
        """generate_entry returns None on API failure."""
        svc = CaptainsLogService()
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))
        svc._client = mock_client

        telemetry = {
            "stardate": "101500.0",
            "timestamp": "2025-06-01T00:00:00+00:00",
            "cert_count": 5,
            "log_entry_count": 0,
            "cve_summary": "CVE data unavailable",
        }
        result = await svc.generate_entry(telemetry)
        assert result is None

    @pytest.mark.asyncio
    async def test_collect_telemetry(self, db_session):
        """collect_telemetry returns expected dict keys."""
        svc = CaptainsLogService()
        telemetry = await svc.collect_telemetry(db_session)

        assert "stardate" in telemetry
        assert "cert_count" in telemetry
        assert "log_entry_count" in telemetry
        assert "cve_summary" in telemetry
        assert telemetry["cert_count"] >= 0


# ── Route tests (auth required) ────────────────────────────────


class TestCaptainsLogRoutes:
    @pytest.mark.asyncio
    async def test_dashboard_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/admin/log", follow_redirects=False)
        assert response.status_code in [302, 401]

    @pytest.mark.asyncio
    async def test_generate_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/admin/log/generate", follow_redirects=False)
        assert response.status_code in [302, 401]

    @pytest.mark.asyncio
    async def test_entry_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/admin/log/entry/test-slug", follow_redirects=False
            )
        assert response.status_code in [302, 401]
