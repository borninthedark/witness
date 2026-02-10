"""Tests for Captain's Log service and routes."""

from __future__ import annotations

import re

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
    async def test_entry_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/admin/log/entry/test-slug", follow_redirects=False
            )
        assert response.status_code in [302, 401]
