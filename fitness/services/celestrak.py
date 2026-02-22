"""CelesTrak satellite TLE data service."""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from fitness.config import settings

logger = logging.getLogger(__name__)

CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"


class SatelliteTLE(BaseModel):
    """Two-Line Element set for satellite tracking."""

    norad_id: str
    name: str
    line1: str = ""
    line2: str = ""
    epoch: str = ""
    inclination: float = 0.0
    eccentricity: float = 0.0
    object_type: str = ""


class CelesTrakService:
    """Fetch satellite TLE data from CelesTrak."""

    @staticmethod
    def _read_from_dynamo(limit: int = 50) -> list[SatelliteTLE] | None:
        from fitness.services.data_store import read_latest_from_dynamo

        return read_latest_from_dynamo("CELESTRAK", SatelliteTLE, limit, logger)

    async def get_active_satellites(self, limit: int = 50) -> list[SatelliteTLE]:
        """Get active satellite TLE data."""
        if settings.use_data_store:
            result = self._read_from_dynamo(limit)
            if result is not None:
                return result

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    CELESTRAK_GP_URL,
                    params={"GROUP": "active", "FORMAT": "json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            logger.warning("CelesTrak API fetch failed")
            return []

        satellites = []
        for sat in data[:limit]:
            satellites.append(
                SatelliteTLE(
                    norad_id=str(sat.get("NORAD_CAT_ID", "")),
                    name=sat.get("OBJECT_NAME", ""),
                    line1=sat.get("TLE_LINE1", ""),
                    line2=sat.get("TLE_LINE2", ""),
                    epoch=sat.get("EPOCH", ""),
                    inclination=float(sat.get("INCLINATION", 0)),
                    eccentricity=float(sat.get("ECCENTRICITY", 0)),
                    object_type=sat.get("OBJECT_TYPE", ""),
                )
            )
        return satellites


celestrak_service = CelesTrakService()
