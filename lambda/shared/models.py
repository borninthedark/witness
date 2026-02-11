"""Pydantic models for DynamoDB data store items."""

from __future__ import annotations

import time

from pydantic import BaseModel, Field


class DataStoreItem(BaseModel):
    """Base model for all DynamoDB items in the witness data store."""

    source: str  # PK: NASA_APOD, NASA_NEO, NIST_CVE, CELESTRAK, NOAA_SPACE, etc.
    sort_key: str  # SK: date#2026-02-10#id#apod-latest
    data_type: str  # GSI1 PK: apod, neo, cve, tle, space_weather, exoplanet, mars
    timestamp: str  # GSI1 SK: ISO-8601 datetime
    expiry_epoch: int = 0  # TTL attribute (epoch seconds)
    payload: dict = Field(default_factory=dict)

    @classmethod
    def with_ttl(cls, ttl_days: int = 90, **kwargs) -> DataStoreItem:
        """Create item with TTL set to ttl_days from now."""
        epoch = int(time.time()) + (ttl_days * 86400)
        return cls(expiry_epoch=epoch, **kwargs)


class ApodItem(BaseModel):
    """NASA Astronomy Picture of the Day."""

    title: str
    url: str
    media_type: str = "image"
    explanation: str = ""
    date: str = ""
    hdurl: str = ""


class NeoItem(BaseModel):
    """Near-Earth Object approach data."""

    name: str
    estimated_diameter_km_min: float = 0.0
    estimated_diameter_km_max: float = 0.0
    is_potentially_hazardous: bool = False
    miss_distance_km: float = 0.0
    miss_distance_lunar: float = 0.0
    relative_velocity_km_s: float = 0.0
    close_approach_date: str = ""
    absolute_magnitude: float = 0.0


class CveItem(BaseModel):
    """NIST NVD CVE record."""

    cve_id: str
    description: str = ""
    severity: str = ""
    cvss_score: float = 0.0
    published_date: str = ""
    modified_date: str = ""
    references: list[str] = Field(default_factory=list)


class TleItem(BaseModel):
    """CelesTrak Two-Line Element set for satellite tracking."""

    norad_id: str
    name: str
    line1: str = ""
    line2: str = ""
    epoch: str = ""
    inclination: float = 0.0
    eccentricity: float = 0.0
    object_type: str = ""


class SpaceWeatherItem(BaseModel):
    """NOAA Space Weather data."""

    report_type: str  # solar_wind, geomagnetic, solar_flare
    kp_index: float = 0.0
    solar_wind_speed: float = 0.0
    bt: float = 0.0
    bz: float = 0.0
    observed_at: str = ""
    summary: str = ""


class ExoplanetItem(BaseModel):
    """NASA Exoplanet Archive record."""

    planet_name: str
    host_star: str = ""
    discovery_method: str = ""
    discovery_year: int = 0
    orbital_period_days: float = 0.0
    planet_radius_earth: float = 0.0
    planet_mass_earth: float = 0.0
    distance_parsec: float = 0.0
    equilibrium_temp_k: float = 0.0


class MarsRoverPhotoItem(BaseModel):
    """NASA Mars Rover photo metadata."""

    rover_name: str
    camera_name: str
    camera_full_name: str = ""
    img_src: str
    earth_date: str = ""
    sol: int = 0
    photo_id: int = 0
