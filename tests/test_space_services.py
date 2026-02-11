"""Tests for new space data services (celestrak, noaa, exoplanet, mars_rover)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fitness.services.celestrak import CelesTrakService, SatelliteTLE
from fitness.services.exoplanet import Exoplanet, ExoplanetService
from fitness.services.mars_rover import MarsRoverPhoto, MarsRoverService
from fitness.services.noaa_space_weather import SpaceWeatherReport, SpaceWeatherService

# ── CelesTrak ────────────────────────────────────────────────────


class TestSatelliteTLE:
    def test_defaults(self):
        tle = SatelliteTLE(norad_id="25544", name="ISS")
        assert tle.inclination == 0.0
        assert tle.object_type == ""


class TestCelesTrakService:
    @pytest.mark.asyncio
    async def test_api_fallback(self):
        svc = CelesTrakService()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "NORAD_CAT_ID": 25544,
                "OBJECT_NAME": "ISS (ZARYA)",
                "INCLINATION": 51.6,
                "ECCENTRICITY": 0.0001,
            },
        ]
        mock_resp.raise_for_status = MagicMock()

        with patch("fitness.services.celestrak.settings") as mock_settings:
            mock_settings.use_data_store = False
            with patch("fitness.services.celestrak.httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client

                result = await svc.get_active_satellites(limit=5)
                assert len(result) == 1
                assert result[0].name == "ISS (ZARYA)"


# ── NOAA Space Weather ──────────────────────────────────────────


class TestSpaceWeatherReport:
    def test_defaults(self):
        r = SpaceWeatherReport(report_type="solar_wind")
        assert r.kp_index == 0.0
        assert r.solar_wind_speed == 0.0


class TestSpaceWeatherService:
    @pytest.mark.asyncio
    async def test_empty_on_api_failure(self):
        svc = SpaceWeatherService()
        with patch("fitness.services.noaa_space_weather.settings") as mock_settings:
            mock_settings.use_data_store = False
            with patch(
                "fitness.services.noaa_space_weather.httpx.AsyncClient"
            ) as MockClient:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=Exception("Network error"))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client

                result = await svc.get_current_conditions()
                assert result == []


# ── Exoplanet ───────────────────────────────────────────────────


class TestExoplanet:
    def test_defaults(self):
        p = Exoplanet(planet_name="Kepler-22b")
        assert p.discovery_year == 0
        assert p.orbital_period_days == 0.0


class TestExoplanetService:
    @pytest.mark.asyncio
    async def test_api_fetch(self):
        svc = ExoplanetService()
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "pl_name": "TOI-700 d",
                "hostname": "TOI-700",
                "discoverymethod": "Transit",
                "disc_year": 2025,
            },
        ]
        mock_resp.raise_for_status = MagicMock()

        with patch("fitness.services.exoplanet.settings") as mock_settings:
            mock_settings.use_data_store = False
            mock_settings.nasa_api_key = None
            with patch("fitness.services.exoplanet.httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client

                result = await svc.get_recent_discoveries(limit=5)
                assert len(result) == 1
                assert result[0].planet_name == "TOI-700 d"


# ── Mars Rover ──────────────────────────────────────────────────


class TestMarsRoverPhoto:
    def test_defaults(self):
        p = MarsRoverPhoto(
            rover_name="Curiosity", camera_name="NAVCAM", img_src="http://img.jpg"
        )
        assert p.sol == 0
        assert p.earth_date == ""


class TestMarsRoverService:
    @pytest.mark.asyncio
    async def test_api_fetch(self):
        svc = MarsRoverService()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "latest_photos": [
                {
                    "id": 12345,
                    "rover": {"name": "Curiosity"},
                    "camera": {"name": "NAVCAM", "full_name": "Navigation Camera"},
                    "img_src": "http://mars.nasa.gov/img.jpg",
                    "earth_date": "2026-02-01",
                    "sol": 4000,
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("fitness.services.mars_rover.settings") as mock_settings:
            mock_settings.use_data_store = False
            mock_settings.nasa_api_key = "DEMO_KEY"
            with patch("fitness.services.mars_rover.httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client

                result = await svc.get_latest_photos(limit=5)
                assert len(result) == 1
                assert result[0].rover_name == "Curiosity"
                assert result[0].photo_id == 12345
