"""Tests for Astrometrics service and routes."""

from __future__ import annotations

import json
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from fitness.main import app
from fitness.services.astrometrics import AstrometricsBriefing, AstrometricsService

# ── Model tests ─────────────────────────────────────────────────


class TestAstrometricsBriefing:
    def test_defaults(self):
        """Briefing model should have sane defaults."""
        b = AstrometricsBriefing()
        assert b.apod_title == ""
        assert b.neo_count == 0
        assert b.briefing_narrative == ""

    def test_round_trip(self):
        """Briefing should serialize and deserialize cleanly."""
        b = AstrometricsBriefing(
            apod_title="Test",
            neo_count=5,
            stardate="101500.0",
            generated_at="2025-06-01T00:00:00+00:00",
        )
        data = json.loads(b.model_dump_json())
        b2 = AstrometricsBriefing(**data)
        assert b2.apod_title == "Test"
        assert b2.neo_count == 5


# ── Service unit tests ──────────────────────────────────────────


class TestAstrometricsService:
    @pytest.mark.asyncio
    async def test_fetch_apod_mock(self):
        """_fetch_apod returns dict from NASA API."""
        svc = AstrometricsService()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "title": "Test APOD",
            "url": "https://apod.nasa.gov/test.jpg",
            "media_type": "image",
            "explanation": "A test image.",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("fitness.services.astrometrics.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await svc._fetch_apod()
            assert result["title"] == "Test APOD"

    @pytest.mark.asyncio
    async def test_parse_closest_neo(self):
        """_parse_closest_neo extracts count and closest approach."""
        neo_data = {
            "element_count": 3,
            "near_earth_objects": {
                "2025-06-01": [
                    {
                        "name": "TestAsteroid",
                        "close_approach_data": [
                            {"miss_distance": {"kilometers": "500000"}}
                        ],
                    },
                    {
                        "name": "FarAsteroid",
                        "close_approach_data": [
                            {"miss_distance": {"kilometers": "9000000"}}
                        ],
                    },
                ]
            },
        }
        count, closest = AstrometricsService._parse_closest_neo(neo_data)
        assert count == 3
        assert "TestAsteroid" in closest
        assert "500,000" in closest

    @pytest.mark.asyncio
    async def test_get_briefing_uses_cache(self, tmp_path):
        """get_briefing returns cached data when available."""
        svc = AstrometricsService()

        from datetime import datetime

        cached = AstrometricsBriefing(
            apod_title="Cached APOD",
            stardate="101500.0",
            generated_at=datetime.now(UTC).isoformat(),
        )

        cache_file = tmp_path / "astrometrics-cache.json"
        cache_file.write_text(cached.model_dump_json(), encoding="utf-8")

        with patch("fitness.services.astrometrics.CACHE_PATH", cache_file):
            result = await svc.get_briefing()
            assert result.apod_title == "Cached APOD"

    @pytest.mark.asyncio
    async def test_narrative_no_api_key(self):
        """Narrative falls back gracefully without API key."""
        svc = AstrometricsService()
        with patch("fitness.services.astrometrics.settings") as mock_settings:
            mock_settings.anthropic_api_key = None
            svc._anthropic_client = None
            result = await svc._generate_narrative({}, 0, "None")
        assert "unavailable" in result.lower()


# ── Route tests (auth required) ────────────────────────────────


class TestAstrometricsRoutes:
    @pytest.mark.asyncio
    async def test_dashboard_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/admin/astrometrics", follow_redirects=False)
        assert response.status_code in [302, 401]

    @pytest.mark.asyncio
    async def test_refresh_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/admin/astrometrics/refresh", follow_redirects=False
            )
        assert response.status_code in [302, 401]
