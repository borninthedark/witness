"""Server-side IP geolocation via ip-api.com (free, no API key)."""

from __future__ import annotations

import logging
import time

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

IP_API_URL = "http://ip-api.com/json"

# Default location (New York City) when geolocation fails or IP is local
DEFAULT_LAT = 40.7128
DEFAULT_LON = -74.0060
DEFAULT_CITY = "New York"
DEFAULT_REGION = "New York"
DEFAULT_COUNTRY = "US"
DEFAULT_TIMEZONE = "America/New_York"


class GeoLocation(BaseModel):
    """Geolocation result for an IP address."""

    lat: float
    lon: float
    city: str
    region: str
    country: str
    timezone: str


class GeoLocationService:
    """IP geolocation with 5-minute in-memory TTL cache."""

    def __init__(self, cache_ttl: int = 300) -> None:
        self._cache: dict[str, tuple[GeoLocation, float]] = {}
        self._cache_ttl = cache_ttl

    def _default_location(self) -> GeoLocation:
        return GeoLocation(
            lat=DEFAULT_LAT,
            lon=DEFAULT_LON,
            city=DEFAULT_CITY,
            region=DEFAULT_REGION,
            country=DEFAULT_COUNTRY,
            timezone=DEFAULT_TIMEZONE,
        )

    def _is_local_ip(self, ip: str) -> bool:
        return ip in ("127.0.0.1", "::1", "localhost", "testclient")

    async def geolocate(self, ip: str) -> GeoLocation:
        """Resolve an IP address to geographic coordinates.

        Returns a default location for local/private IPs or on failure.
        """
        if self._is_local_ip(ip):
            return self._default_location()

        # Check cache
        now = time.monotonic()
        if ip in self._cache:
            cached, ts = self._cache[ip]
            if now - ts < self._cache_ttl:
                return cached

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{IP_API_URL}/{ip}")
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "success":
                logger.warning(
                    "ip-api returned status=%s for %s", data.get("status"), ip
                )
                return self._default_location()

            location = GeoLocation(
                lat=float(data.get("lat", DEFAULT_LAT)),
                lon=float(data.get("lon", DEFAULT_LON)),
                city=data.get("city", DEFAULT_CITY),
                region=data.get("regionName", DEFAULT_REGION),
                country=data.get("countryCode", DEFAULT_COUNTRY),
                timezone=data.get("timezone", DEFAULT_TIMEZONE),
            )
            self._cache[ip] = (location, now)
            return location
        except Exception:
            logger.warning("Geolocation failed for %s", ip)
            return self._default_location()


geolocation_service = GeoLocationService()
