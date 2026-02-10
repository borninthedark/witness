"""Tests for Astrometrics service and routes."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from fitness.main import app
from fitness.services.astrometrics import (
    AstrometricsBriefing,
    AstrometricsService,
    NeoObject,
)

# ── Model tests ─────────────────────────────────────────────────


class TestAstrometricsBriefing:
    def test_defaults(self):
        """Briefing model should have sane defaults."""
        b = AstrometricsBriefing()
        assert b.apod_title == ""
        assert b.neo_count == 0

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


# ── NeoObject model tests ─────────────────────────────────────────


class TestNeoObject:
    def test_defaults(self):
        """NeoObject should have sane defaults for optional fields."""
        obj = NeoObject(name="Test")
        assert obj.estimated_diameter_km_min == 0.0
        assert obj.is_potentially_hazardous is False
        assert obj.miss_distance_km == 0.0
        assert obj.close_approach_epoch == 0

    def test_parse_neo_objects(self):
        """_parse_neo_objects extracts full NEO list from NASA feed data."""
        neo_data = {
            "element_count": 2,
            "near_earth_objects": {
                "2025-06-01": [
                    {
                        "name": "HazardousRock",
                        "absolute_magnitude_h": 22.5,
                        "is_potentially_hazardous_asteroid": True,
                        "estimated_diameter": {
                            "kilometers": {
                                "estimated_diameter_min": 0.05,
                                "estimated_diameter_max": 0.12,
                            }
                        },
                        "close_approach_data": [
                            {
                                "miss_distance": {
                                    "kilometers": "750000",
                                    "lunar": "1.95",
                                },
                                "relative_velocity": {"kilometers_per_second": "12.5"},
                                "epoch_date_close_approach": 1717200000000,
                            }
                        ],
                    },
                    {
                        "name": "SafeRock",
                        "absolute_magnitude_h": 25.0,
                        "is_potentially_hazardous_asteroid": False,
                        "estimated_diameter": {
                            "kilometers": {
                                "estimated_diameter_min": 0.01,
                                "estimated_diameter_max": 0.03,
                            }
                        },
                        "close_approach_data": [
                            {
                                "miss_distance": {
                                    "kilometers": "5000000",
                                    "lunar": "13.0",
                                },
                                "relative_velocity": {"kilometers_per_second": "8.2"},
                                "epoch_date_close_approach": 1717250000000,
                            }
                        ],
                    },
                ]
            },
        }
        objects = AstrometricsService._parse_neo_objects(neo_data)
        assert len(objects) == 2

        hazardous = next(o for o in objects if o.name == "HazardousRock")
        assert hazardous.is_potentially_hazardous is True
        assert hazardous.miss_distance_km == 750000.0
        assert hazardous.miss_distance_lunar == 1.95
        assert hazardous.relative_velocity_km_s == 12.5
        assert hazardous.estimated_diameter_km_max == 0.12

        safe = next(o for o in objects if o.name == "SafeRock")
        assert safe.is_potentially_hazardous is False
        assert safe.miss_distance_km == 5000000.0

    def test_briefing_with_neo_objects_serialization(self):
        """Briefing with neo_objects should serialize and deserialize."""
        neo = NeoObject(name="TestNEO", miss_distance_km=1000000.0)
        b = AstrometricsBriefing(
            neo_count=1,
            neo_objects=[neo],
            generated_at="2025-06-01T00:00:00+00:00",
        )
        data = json.loads(b.model_dump_json())
        b2 = AstrometricsBriefing(**data)
        assert len(b2.neo_objects) == 1
        assert b2.neo_objects[0].name == "TestNEO"
        assert b2.neo_objects[0].miss_distance_km == 1000000.0

    def test_briefing_backward_compat_no_neo_objects(self):
        """Old cached briefings without neo_objects should still load."""
        old_data = {
            "apod_title": "Old APOD",
            "neo_count": 3,
            "neo_closest": "OldRock (100,000 km)",
            "stardate": "101500.0",
            "generated_at": "2025-06-01T00:00:00+00:00",
        }
        b = AstrometricsBriefing(**old_data)
        assert b.neo_objects == []
        assert b.neo_count == 3
