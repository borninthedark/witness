"""Tests for geolocation, sky service, and stargazing router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from fitness.main import app
from fitness.services.geolocation import GeoLocation, GeoLocationService
from fitness.services.sky_service import SkyConditions, SkyService

# ── GeoLocation model ───────────────────────────────────────────


class TestGeoLocationModel:
    def test_defaults(self):
        loc = GeoLocation(
            lat=40.7,
            lon=-74.0,
            city="NYC",
            region="NY",
            country="US",
            timezone="America/New_York",
        )
        assert loc.lat == 40.7
        assert loc.city == "NYC"


# ── GeoLocationService ──────────────────────────────────────────


class TestGeoLocationService:
    @pytest.mark.asyncio
    async def test_local_ip_returns_default(self):
        svc = GeoLocationService()
        loc = await svc.geolocate("127.0.0.1")
        assert loc.city == "New York"
        assert loc.lat == 40.7128

    @pytest.mark.asyncio
    async def test_localhost_returns_default(self):
        svc = GeoLocationService()
        loc = await svc.geolocate("localhost")
        assert loc.city == "New York"

    @pytest.mark.asyncio
    async def test_testclient_returns_default(self):
        svc = GeoLocationService()
        loc = await svc.geolocate("testclient")
        assert loc.city == "New York"

    @pytest.mark.asyncio
    async def test_api_success(self):
        svc = GeoLocationService()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "success",
            "lat": 51.5,
            "lon": -0.1,
            "city": "London",
            "regionName": "England",
            "countryCode": "GB",
            "timezone": "Europe/London",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("fitness.services.geolocation.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            loc = await svc.geolocate("8.8.8.8")
            assert loc.city == "London"
            assert loc.lat == 51.5

    @pytest.mark.asyncio
    async def test_api_failure_returns_default(self):
        svc = GeoLocationService()
        with patch("fitness.services.geolocation.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            loc = await svc.geolocate("8.8.8.8")
            assert loc.city == "New York"

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        svc = GeoLocationService()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "success",
            "lat": 48.8,
            "lon": 2.3,
            "city": "Paris",
            "regionName": "Ile-de-France",
            "countryCode": "FR",
            "timezone": "Europe/Paris",
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("fitness.services.geolocation.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            loc1 = await svc.geolocate("1.2.3.4")
            loc2 = await svc.geolocate("1.2.3.4")
            assert loc1.city == "Paris"
            assert loc2.city == "Paris"
            # Second call should use cache — only 1 HTTP call
            assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_api_fail_status(self):
        svc = GeoLocationService()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "fail", "message": "reserved range"}
        mock_resp.raise_for_status = MagicMock()

        with patch("fitness.services.geolocation.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            loc = await svc.geolocate("10.0.0.1")
            assert loc.city == "New York"


# ── SkyService unit tests ───────────────────────────────────────


class TestSkyService:
    def test_compute_stargazing_score(self):
        score = SkyService._compute_stargazing_score(
            cloud_pct=0, bortle=1, moon_illum=0.0, aqi=1
        )
        assert score == 100.0

    def test_compute_stargazing_score_worst_case(self):
        score = SkyService._compute_stargazing_score(
            cloud_pct=100, bortle=9, moon_illum=100.0, aqi=5
        )
        assert score == 0.0

    def test_compute_moon_phase(self):
        phase, illum = SkyService._compute_moon_phase()
        assert phase in [
            "new",
            "waxing_crescent",
            "first_quarter",
            "waxing_gibbous",
            "full",
            "waning_gibbous",
            "last_quarter",
            "waning_crescent",
        ]
        assert 0.0 <= illum <= 100.0

    def test_estimate_bortle(self):
        # High latitude → rural
        loc_rural = GeoLocation(
            lat=65.0,
            lon=25.0,
            city="Rovaniemi",
            region="Lapland",
            country="FI",
            timezone="Europe/Helsinki",
        )
        assert SkyService._estimate_bortle(loc_rural) == 3

        # Mid latitude → suburban
        loc_suburban = GeoLocation(
            lat=50.0,
            lon=14.0,
            city="Prague",
            region="Prague",
            country="CZ",
            timezone="Europe/Prague",
        )
        assert SkyService._estimate_bortle(loc_suburban) == 5

    def test_build_summary_excellent(self):
        summary = SkyService._build_summary(
            score=85,
            cloud_pct=10,
            moon_phase="new",
            aurora_visible=False,
        )
        assert "Excellent" in summary
        assert "mostly clear" in summary

    def test_build_summary_with_aurora(self):
        summary = SkyService._build_summary(
            score=50,
            cloud_pct=30,
            moon_phase="waxing_crescent",
            aurora_visible=True,
        )
        assert "Aurora" in summary

    @pytest.mark.asyncio
    async def test_get_conditions_no_api_keys(self):
        """get_conditions should return valid data even without OWM API key."""
        svc = SkyService()
        location = GeoLocation(
            lat=40.7,
            lon=-74.0,
            city="NYC",
            region="NY",
            country="US",
            timezone="America/New_York",
        )

        with (
            patch.object(
                svc,
                "_compute_satellite_passes",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch.object(
                svc,
                "_compute_aurora",
                new_callable=AsyncMock,
                return_value=(0.1, False),
            ),
            patch("fitness.services.sky_service.settings") as mock_settings,
        ):
            mock_settings.openweathermap_api_key = None
            conditions = await svc.get_conditions(location)
            assert isinstance(conditions, SkyConditions)
            assert conditions.location.city == "NYC"
            assert 0 <= conditions.stargazing_score <= 100

    @pytest.mark.asyncio
    async def test_aurora_high_latitude_high_kp(self):
        """High Kp + high latitude → aurora visible."""
        svc = SkyService()
        location = GeoLocation(
            lat=65.0,
            lon=25.0,
            city="Rovaniemi",
            region="Lapland",
            country="FI",
            timezone="Europe/Helsinki",
        )

        from fitness.services.noaa_space_weather import SpaceWeatherReport

        mock_reports = [
            SpaceWeatherReport(report_type="geomagnetic", kp_index=7.0),
        ]
        with patch(
            "fitness.services.sky_service.space_weather_service.get_current_conditions",
            new_callable=AsyncMock,
            return_value=mock_reports,
        ):
            prob, visible = await svc._compute_aurora(location)
            assert prob >= 0.4
            assert visible is True


# ── Stargazing router tests ─────────────────────────────────────


class TestStargazingRoutes:
    @pytest.mark.asyncio
    async def test_dashboard_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/admin/stargazing", follow_redirects=False)
        assert response.status_code in [302, 401]
