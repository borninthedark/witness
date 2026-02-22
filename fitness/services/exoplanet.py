"""NASA Exoplanet Archive data service."""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from fitness.config import settings

logger = logging.getLogger(__name__)

EXOPLANET_TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"


class Exoplanet(BaseModel):
    """Confirmed exoplanet record from NASA Exoplanet Archive."""

    planet_name: str
    host_star: str = ""
    discovery_method: str = ""
    discovery_year: int = 0
    orbital_period_days: float = 0.0
    planet_radius_earth: float = 0.0
    planet_mass_earth: float = 0.0
    distance_parsec: float = 0.0
    equilibrium_temp_k: float = 0.0


class ExoplanetService:
    """Fetch exoplanet data from NASA Exoplanet Archive."""

    @staticmethod
    def _read_from_dynamo(limit: int = 50) -> list[Exoplanet] | None:
        from fitness.services.data_store import read_latest_from_dynamo

        return read_latest_from_dynamo("NASA_EXOPLANET", Exoplanet, limit, logger)

    async def get_recent_discoveries(self, limit: int = 50) -> list[Exoplanet]:
        """Get recently discovered exoplanets."""
        if settings.use_data_store:
            result = self._read_from_dynamo(limit)
            if result is not None:
                return result

        query = (
            "select+pl_name,hostname,discoverymethod,disc_year,pl_orbper,"
            "pl_rade,pl_bmasse,sy_dist,pl_eqt"
            "+from+ps+where+disc_year>=2025+and+default_flag=1"
            "+order+by+disc_year+desc"
        )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    EXOPLANET_TAP_URL,
                    params={"query": query, "format": "json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            logger.warning("NASA Exoplanet Archive fetch failed")
            return []

        planets = []
        for row in data[:limit]:
            planets.append(
                Exoplanet(
                    planet_name=row.get("pl_name", "Unknown"),
                    host_star=row.get("hostname", ""),
                    discovery_method=row.get("discoverymethod", ""),
                    discovery_year=row.get("disc_year", 0),
                    orbital_period_days=float(row.get("pl_orbper") or 0),
                    planet_radius_earth=float(row.get("pl_rade") or 0),
                    planet_mass_earth=float(row.get("pl_bmasse") or 0),
                    distance_parsec=float(row.get("sy_dist") or 0),
                    equilibrium_temp_k=float(row.get("pl_eqt") or 0),
                )
            )
        return planets


exoplanet_service = ExoplanetService()
