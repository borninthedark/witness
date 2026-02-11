"""NOAA Space Weather Prediction Center data service."""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from fitness.config import settings

logger = logging.getLogger(__name__)

NOAA_SWPC_URL = "https://services.swpc.noaa.gov/products"


class SpaceWeatherReport(BaseModel):
    """Space weather observation data point."""

    report_type: str  # solar_wind, geomagnetic, mag_field
    kp_index: float = 0.0
    solar_wind_speed: float = 0.0
    bt: float = 0.0
    bz: float = 0.0
    observed_at: str = ""
    summary: str = ""


class SpaceWeatherService:
    """Fetch space weather data from NOAA SWPC."""

    def _read_from_dynamo(self, limit: int = 24) -> list[SpaceWeatherReport] | None:
        """Read space weather data from DynamoDB."""
        try:
            from fitness.services.data_store import data_store_service

            items = data_store_service.query_by_type("space_weather", limit=limit)
            if not items:
                return None
            return [SpaceWeatherReport(**item.get("payload", {})) for item in items]
        except Exception:
            logger.warning("DynamoDB space weather read failed")
            return None

    async def _fetch_swpc_data(
        self,
        endpoint: str,
        report_type: str,
        value_field: str,
        tail: int,
        label: str,
    ) -> list[SpaceWeatherReport]:
        """Fetch and parse an NOAA SWPC time-series endpoint."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{NOAA_SWPC_URL}/{endpoint}")
                resp.raise_for_status()
                data = resp.json()
                if len(data) <= 1:
                    return []
                return [
                    SpaceWeatherReport(
                        report_type=report_type,
                        observed_at=row[0] if row else "",
                        **{
                            value_field: (
                                float(row[1]) if len(row) > 1 and row[1] else 0.0
                            )
                        },
                    )
                    for row in data[-tail:]
                ]
        except Exception:
            logger.warning("NOAA %s fetch failed", label)
            return []

    async def _fetch_solar_wind(self) -> list[SpaceWeatherReport]:
        """Fetch recent solar wind plasma observations from NOAA SWPC."""
        return await self._fetch_swpc_data(
            "solar-wind/plasma-7-day.json",
            "solar_wind",
            "solar_wind_speed",
            12,
            "solar wind",
        )

    async def _fetch_kp_index(self) -> list[SpaceWeatherReport]:
        """Fetch recent planetary Kp index observations from NOAA SWPC."""
        return await self._fetch_swpc_data(
            "noaa-planetary-k-index.json",
            "geomagnetic",
            "kp_index",
            8,
            "Kp index",
        )

    async def get_current_conditions(self) -> list[SpaceWeatherReport]:
        """Get current space weather conditions."""
        if settings.use_data_store:
            result = self._read_from_dynamo()
            if result is not None:
                return result

        solar_wind = await self._fetch_solar_wind()
        kp_index = await self._fetch_kp_index()
        return solar_wind + kp_index


space_weather_service = SpaceWeatherService()
