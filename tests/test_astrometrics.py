"""Tests for the Astrometrics service — NASA APOD + NEO data."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from fitness.services.astrometrics import (
    AstrometricsBriefing,
    AstrometricsService,
    NeoObject,
)

# ── Sample NASA NEO response ────────────────────────────────────

SAMPLE_NEO_DATA = {
    "element_count": 2,
    "near_earth_objects": {
        "2026-02-22": [
            {
                "name": "(2024 AB1)",
                "estimated_diameter": {
                    "kilometers": {
                        "estimated_diameter_min": 0.1,
                        "estimated_diameter_max": 0.2,
                    }
                },
                "is_potentially_hazardous_asteroid": False,
                "close_approach_data": [
                    {
                        "miss_distance": {"kilometers": "500000", "lunar": "1.3"},
                        "relative_velocity": {"kilometers_per_second": "10.5"},
                        "epoch_date_close_approach": 1740268800000,
                    }
                ],
                "absolute_magnitude_h": 25.5,
            },
            {
                "name": "(2024 CD2)",
                "estimated_diameter": {
                    "kilometers": {
                        "estimated_diameter_min": 0.05,
                        "estimated_diameter_max": 0.12,
                    }
                },
                "is_potentially_hazardous_asteroid": True,
                "close_approach_data": [
                    {
                        "miss_distance": {"kilometers": "200000", "lunar": "0.5"},
                        "relative_velocity": {"kilometers_per_second": "15.2"},
                        "epoch_date_close_approach": 1740300000000,
                    }
                ],
                "absolute_magnitude_h": 27.1,
            },
        ],
    },
}


# ── NeoObject model ─────────────────────────────────────────────


class TestNeoObject:
    """Verify NeoObject pydantic model defaults."""

    def test_defaults(self):
        neo = NeoObject(name="Test NEO")
        assert neo.name == "Test NEO"
        assert neo.estimated_diameter_km_min == 0.0
        assert neo.estimated_diameter_km_max == 0.0
        assert neo.is_potentially_hazardous is False
        assert neo.miss_distance_km == 0.0
        assert neo.miss_distance_lunar == 0.0
        assert neo.relative_velocity_km_s == 0.0
        assert neo.close_approach_epoch == 0
        assert neo.absolute_magnitude == 0.0


# ── AstrometricsBriefing model ──────────────────────────────────


class TestAstrometricsBriefing:
    """Verify AstrometricsBriefing pydantic model."""

    def test_defaults(self):
        briefing = AstrometricsBriefing()
        assert briefing.apod_title == ""
        assert briefing.apod_url == ""
        assert briefing.apod_media_type == "image"
        assert briefing.apod_explanation == ""
        assert briefing.neo_count == 0
        assert briefing.neo_closest == ""
        assert briefing.neo_objects == []
        assert briefing.stardate == ""
        assert briefing.generated_at == ""

    def test_with_data(self):
        neo = NeoObject(name="Asteroid X", miss_distance_km=42000.0)
        briefing = AstrometricsBriefing(
            apod_title="Pillars of Creation",
            apod_url="https://apod.nasa.gov/image.jpg",
            apod_media_type="image",
            apod_explanation="A famous nebula.",
            neo_count=3,
            neo_closest="Asteroid X (42,000 km)",
            neo_objects=[neo],
            stardate="103145.7",
            generated_at="2026-02-22T12:00:00+00:00",
        )
        assert briefing.apod_title == "Pillars of Creation"
        assert briefing.neo_count == 3
        assert len(briefing.neo_objects) == 1
        assert briefing.neo_objects[0].name == "Asteroid X"
        assert briefing.generated_at == "2026-02-22T12:00:00+00:00"


# ── AstrometricsService ─────────────────────────────────────────


class TestAstrometricsService:
    """Tests for AstrometricsService parsing, caching, and fetch logic."""

    # ── Parsing ──────────────────────────────────────────────

    def test_parse_closest_neo(self):
        svc = AstrometricsService()
        count, closest = svc._parse_closest_neo(SAMPLE_NEO_DATA)
        assert count == 2
        # (2024 CD2) is closer at 200,000 km
        assert "(2024 CD2)" in closest
        assert "200,000" in closest

    def test_parse_closest_neo_empty(self):
        svc = AstrometricsService()
        count, closest = svc._parse_closest_neo({"near_earth_objects": {}})
        assert count == 0
        assert closest == "None detected"

    def test_parse_neo_objects(self):
        svc = AstrometricsService()
        objects = svc._parse_neo_objects(SAMPLE_NEO_DATA)
        assert len(objects) == 2

        ab1 = next(o for o in objects if "AB1" in o.name)
        assert ab1.estimated_diameter_km_min == 0.1
        assert ab1.estimated_diameter_km_max == 0.2
        assert ab1.is_potentially_hazardous is False
        assert ab1.miss_distance_km == 500000.0
        assert ab1.miss_distance_lunar == 1.3
        assert ab1.relative_velocity_km_s == 10.5
        assert ab1.close_approach_epoch == 1740268800000
        assert ab1.absolute_magnitude == 25.5

        cd2 = next(o for o in objects if "CD2" in o.name)
        assert cd2.is_potentially_hazardous is True
        assert cd2.miss_distance_km == 200000.0

    def test_parse_neo_objects_empty(self):
        svc = AstrometricsService()
        objects = svc._parse_neo_objects({"near_earth_objects": {}})
        assert objects == []

    # ── Cache ────────────────────────────────────────────────

    def test_read_cache_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "fitness.services.astrometrics.CACHE_PATH",
            tmp_path / "nonexistent.json",
        )
        svc = AstrometricsService()
        assert svc._read_cache() is None

    def test_read_cache_expired(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "astrometrics-cache.json"
        monkeypatch.setattr("fitness.services.astrometrics.CACHE_PATH", cache_file)
        old_time = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
        briefing = AstrometricsBriefing(apod_title="Old", generated_at=old_time)
        cache_file.write_text(briefing.model_dump_json(indent=2), encoding="utf-8")

        svc = AstrometricsService()
        assert svc._read_cache() is None

    def test_read_cache_valid(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "astrometrics-cache.json"
        monkeypatch.setattr("fitness.services.astrometrics.CACHE_PATH", cache_file)
        fresh_time = datetime.now(UTC).isoformat()
        briefing = AstrometricsBriefing(
            apod_title="Fresh APOD", generated_at=fresh_time
        )
        cache_file.write_text(briefing.model_dump_json(indent=2), encoding="utf-8")

        svc = AstrometricsService()
        result = svc._read_cache()
        assert result is not None
        assert isinstance(result, AstrometricsBriefing)
        assert result.apod_title == "Fresh APOD"

    def test_write_cache(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "astrometrics-cache.json"
        monkeypatch.setattr("fitness.services.astrometrics.CACHE_PATH", cache_file)
        briefing = AstrometricsBriefing(
            apod_title="Cached",
            generated_at=datetime.now(UTC).isoformat(),
        )
        svc = AstrometricsService()
        svc._write_cache(briefing)

        assert cache_file.exists()
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert data["apod_title"] == "Cached"

    # ── get_briefing ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_briefing_cached(self, monkeypatch):
        monkeypatch.setattr(
            "fitness.services.astrometrics.settings.use_data_store", False
        )
        cached_briefing = AstrometricsBriefing(
            apod_title="From Cache",
            generated_at=datetime.now(UTC).isoformat(),
        )
        svc = AstrometricsService()

        with (
            patch.object(
                svc, "_read_cache", return_value=cached_briefing
            ) as mock_cache,
            patch.object(svc, "_fetch_apod") as mock_apod,
            patch.object(svc, "_fetch_neo") as mock_neo,
        ):
            result = await svc.get_briefing()

        mock_cache.assert_called_once()
        mock_apod.assert_not_called()
        mock_neo.assert_not_called()
        assert result.apod_title == "From Cache"

    @pytest.mark.asyncio
    async def test_get_briefing_api_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "fitness.services.astrometrics.settings.use_data_store", False
        )
        monkeypatch.setattr(
            "fitness.services.astrometrics.CACHE_PATH",
            tmp_path / "no-cache.json",
        )
        apod_response = {
            "title": "Test APOD",
            "url": "https://apod.nasa.gov/test.jpg",
            "media_type": "image",
            "explanation": "A test image.",
        }
        svc = AstrometricsService()

        with (
            patch.object(
                svc, "_fetch_apod", new_callable=AsyncMock, return_value=apod_response
            ) as mock_apod,
            patch.object(
                svc, "_fetch_neo", new_callable=AsyncMock, return_value=SAMPLE_NEO_DATA
            ) as mock_neo,
        ):
            result = await svc.get_briefing()

        mock_apod.assert_awaited_once()
        mock_neo.assert_awaited_once()
        assert result.apod_title == "Test APOD"
        assert result.neo_count == 2
        assert "(2024 CD2)" in result.neo_closest
        assert len(result.neo_objects) == 2

    @pytest.mark.asyncio
    async def test_get_briefing_apod_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "fitness.services.astrometrics.settings.use_data_store", False
        )
        monkeypatch.setattr(
            "fitness.services.astrometrics.CACHE_PATH",
            tmp_path / "no-cache.json",
        )
        svc = AstrometricsService()

        with (
            patch.object(
                svc,
                "_fetch_apod",
                new_callable=AsyncMock,
                side_effect=Exception("APOD down"),
            ),
            patch.object(
                svc, "_fetch_neo", new_callable=AsyncMock, return_value=SAMPLE_NEO_DATA
            ),
        ):
            result = await svc.get_briefing()

        # APOD should fall back gracefully
        assert result.apod_title == "Unavailable"
        assert result.apod_url == ""
        # NEO data should still be populated
        assert result.neo_count == 2
        assert len(result.neo_objects) == 2

    @pytest.mark.asyncio
    async def test_get_briefing_neo_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "fitness.services.astrometrics.settings.use_data_store", False
        )
        monkeypatch.setattr(
            "fitness.services.astrometrics.CACHE_PATH",
            tmp_path / "no-cache.json",
        )
        apod_response = {
            "title": "Working APOD",
            "url": "https://apod.nasa.gov/ok.jpg",
            "media_type": "image",
            "explanation": "This one works.",
        }
        svc = AstrometricsService()

        with (
            patch.object(
                svc, "_fetch_apod", new_callable=AsyncMock, return_value=apod_response
            ),
            patch.object(
                svc,
                "_fetch_neo",
                new_callable=AsyncMock,
                side_effect=Exception("NEO down"),
            ),
        ):
            result = await svc.get_briefing()

        # APOD should still work
        assert result.apod_title == "Working APOD"
        # NEO should fall back gracefully
        assert result.neo_count == 0
        assert result.neo_closest == "Data unavailable"
        assert result.neo_objects == []

    @pytest.mark.asyncio
    async def test_get_briefing_force_refresh(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "fitness.services.astrometrics.settings.use_data_store", False
        )
        monkeypatch.setattr(
            "fitness.services.astrometrics.CACHE_PATH",
            tmp_path / "cache.json",
        )
        # Write a valid cache that would normally be returned
        cache_file = tmp_path / "cache.json"
        cached = AstrometricsBriefing(
            apod_title="Stale Cached",
            generated_at=datetime.now(UTC).isoformat(),
        )
        cache_file.write_text(cached.model_dump_json(indent=2), encoding="utf-8")

        apod_response = {
            "title": "Fresh From API",
            "url": "https://apod.nasa.gov/fresh.jpg",
            "media_type": "image",
            "explanation": "Fresh data.",
        }
        svc = AstrometricsService()

        with (
            patch.object(
                svc, "_fetch_apod", new_callable=AsyncMock, return_value=apod_response
            ),
            patch.object(
                svc, "_fetch_neo", new_callable=AsyncMock, return_value=SAMPLE_NEO_DATA
            ),
        ):
            result = await svc.get_briefing(force_refresh=True)

        # Cache should be skipped; fresh API data used
        assert result.apod_title == "Fresh From API"
        assert result.neo_count == 2
