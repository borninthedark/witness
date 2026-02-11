"""Sky meteorology service — unified stargazing conditions report."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime

import ephem
import httpx
from pydantic import BaseModel
from sgp4.api import Satrec, jday

from fitness.config import settings
from fitness.services.celestrak import celestrak_service
from fitness.services.geolocation import GeoLocation
from fitness.services.noaa_space_weather import space_weather_service

logger = logging.getLogger(__name__)

OWM_BASE = "https://api.openweathermap.org/data/2.5"

# WHO AQI labels (1–5 scale used by OWM)
AQI_LABELS = {
    1: "Good",
    2: "Fair",
    3: "Moderate",
    4: "Poor",
    5: "Very Poor",
}

MOON_PHASES = [
    "new",
    "waxing_crescent",
    "first_quarter",
    "waxing_gibbous",
    "full",
    "waning_gibbous",
    "last_quarter",
    "waning_crescent",
]


class SatellitePass(BaseModel):
    """A visible satellite pass over the observer."""

    name: str
    rise_time: str
    set_time: str
    max_elevation_deg: float


class SkyConditions(BaseModel):
    """Unified sky conditions report for a location."""

    location: GeoLocation
    visible_satellites: list[SatellitePass]
    aurora_probability: float  # 0.0–1.0
    aurora_visible: bool
    cloud_cover_pct: int  # 0–100
    visibility_km: float
    humidity_pct: int
    temperature_c: float
    wind_speed_mps: float
    moon_phase: str
    moon_illumination_pct: float
    air_quality_index: int  # 1–5 (WHO scale)
    air_quality_label: str
    pm25: float
    pm10: float
    bortle_class: int  # 1–9
    stargazing_score: float  # 0–100 composite
    summary: str


class SkyService:
    """Combine satellite, aurora, weather, moon, and air quality data."""

    async def get_conditions(self, location: GeoLocation) -> SkyConditions:
        """Build a full sky conditions report for the given location."""
        satellites = await self._compute_satellite_passes(location)
        aurora_prob, aurora_vis = await self._compute_aurora(location)
        weather = await self._fetch_weather(location)
        air = await self._fetch_air_quality(location)
        moon_phase, moon_illum = self._compute_moon_phase()
        bortle = self._estimate_bortle(location)

        cloud_pct = weather.get("cloud_cover_pct", 50)
        score = self._compute_stargazing_score(
            cloud_pct, bortle, moon_illum, air.get("aqi", 3)
        )
        summary = self._build_summary(score, cloud_pct, moon_phase, aurora_vis)

        return SkyConditions(
            location=location,
            visible_satellites=satellites,
            aurora_probability=aurora_prob,
            aurora_visible=aurora_vis,
            cloud_cover_pct=cloud_pct,
            visibility_km=weather.get("visibility_km", 10.0),
            humidity_pct=weather.get("humidity_pct", 50),
            temperature_c=weather.get("temperature_c", 15.0),
            wind_speed_mps=weather.get("wind_speed_mps", 0.0),
            moon_phase=moon_phase,
            moon_illumination_pct=moon_illum,
            air_quality_index=air.get("aqi", 3),
            air_quality_label=AQI_LABELS.get(air.get("aqi", 3), "Unknown"),
            pm25=air.get("pm25", 0.0),
            pm10=air.get("pm10", 0.0),
            bortle_class=bortle,
            stargazing_score=score,
            summary=summary,
        )

    # ── Satellite passes (SGP4) ───────────────────────────────────

    async def _compute_satellite_passes(
        self, location: GeoLocation, hours_ahead: int = 6
    ) -> list[SatellitePass]:
        """Compute visible satellite passes using SGP4 propagation."""
        tles = await celestrak_service.get_active_satellites(limit=30)
        if not tles:
            return []

        now = datetime.now(UTC)
        passes: list[SatellitePass] = []

        for tle in tles:
            result = self._propagate_single_pass(tle, location, now, hours_ahead)
            if result:
                passes.append(result)
                if len(passes) >= 10:
                    break

        return passes

    def _propagate_single_pass(
        self,
        tle: object,
        location: GeoLocation,
        now: datetime,
        hours_ahead: int,
    ) -> SatellitePass | None:
        """Propagate a single TLE and return a pass if visible."""
        if not tle.line1 or not tle.line2:
            return None
        try:
            sat = Satrec.twoline2rv(tle.line1, tle.line2)
        except Exception:  # noqa: S112
            return None

        rise_time, set_time, max_elev = self._scan_pass_window(
            sat,
            location,
            now,
            hours_ahead,
        )
        if not (rise_time and set_time):
            return None
        return SatellitePass(
            name=tle.name,
            rise_time=rise_time.strftime("%H:%M UTC"),
            set_time=set_time.strftime("%H:%M UTC"),
            max_elevation_deg=round(max_elev, 1),
        )

    def _scan_pass_window(
        self,
        sat: Satrec,
        location: GeoLocation,
        now: datetime,
        hours_ahead: int,
    ) -> tuple[datetime | None, datetime | None, float]:
        """Step through time samples and find rise/set/max elevation."""
        visible = False
        max_elev = 0.0
        rise_time: datetime | None = None
        set_time: datetime | None = None

        for minutes in range(0, hours_ahead * 60, 1):
            t = now.timestamp() + minutes * 60
            dt = datetime.fromtimestamp(t, tz=UTC)
            jd, fr = jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
            e, r, v = sat.sgp4(jd, fr)
            if e != 0:
                continue

            elev = self._elevation_angle(r, location.lat, location.lon, jd + fr)
            if elev > 10:
                if not visible:
                    visible = True
                    rise_time = dt
                if elev > max_elev:
                    max_elev = elev
                set_time = dt
            elif visible:
                break

        return rise_time, set_time, max_elev

    @staticmethod
    def _elevation_angle(
        r_eci: tuple[float, float, float],
        lat: float,
        lon: float,
        jd_total: float,
    ) -> float:
        """Approximate elevation angle from ECI position to observer.

        Uses a simplified geodetic conversion (spherical Earth).
        """
        # Observer position in ECEF (spherical Earth, R=6371 km)
        earth_r = 6371.0
        lat_rad = math.radians(lat)
        # Greenwich sidereal time approximation
        d = jd_total - 2451545.0
        gmst = math.radians((280.46061837 + 360.98564736629 * d) % 360)
        lon_rad = gmst + math.radians(lon)

        obs_x = earth_r * math.cos(lat_rad) * math.cos(lon_rad)
        obs_y = earth_r * math.cos(lat_rad) * math.sin(lon_rad)
        obs_z = earth_r * math.sin(lat_rad)

        # Vector from observer to satellite
        dx = r_eci[0] - obs_x
        dy = r_eci[1] - obs_y
        dz = r_eci[2] - obs_z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist == 0:
            return 0.0

        # Up vector at observer (radial)
        up_x, up_y, up_z = obs_x / earth_r, obs_y / earth_r, obs_z / earth_r

        # Dot product gives cos(zenith angle)
        cos_zenith = (dx * up_x + dy * up_y + dz * up_z) / dist
        return math.degrees(math.asin(max(-1.0, min(1.0, cos_zenith))))

    # ── Aurora probability ────────────────────────────────────────

    async def _compute_aurora(self, location: GeoLocation) -> tuple[float, bool]:
        """Estimate aurora visibility from Kp index and latitude."""
        reports = await space_weather_service.get_current_conditions()
        kp_values = [r.kp_index for r in reports if r.report_type == "geomagnetic"]
        if not kp_values:
            return 0.0, False

        kp = max(kp_values)
        abs_lat = abs(location.lat)

        # Threshold: aurora visible when Kp >= (|lat| - 50) / 2.5
        threshold = max(0, (abs_lat - 50) / 2.5)
        if abs_lat < 30:
            # Very unlikely below 30 degrees latitude
            probability = min(0.05, kp / 90)
        elif kp >= threshold:
            probability = min(1.0, 0.5 + (kp - threshold) * 0.15)
        else:
            probability = max(0.0, 0.1 * kp / max(threshold, 0.1))

        return round(probability, 2), probability >= 0.4

    # ── Weather (OpenWeatherMap) ──────────────────────────────────

    async def _fetch_weather(self, location: GeoLocation) -> dict:
        """Fetch current weather from OpenWeatherMap."""
        if not settings.openweathermap_api_key:
            return {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{OWM_BASE}/weather",
                    params={
                        "lat": location.lat,
                        "lon": location.lon,
                        "appid": settings.openweathermap_api_key,
                        "units": "metric",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            return {
                "cloud_cover_pct": data.get("clouds", {}).get("all", 50),
                "visibility_km": data.get("visibility", 10000) / 1000,
                "humidity_pct": data.get("main", {}).get("humidity", 50),
                "temperature_c": data.get("main", {}).get("temp", 15.0),
                "wind_speed_mps": data.get("wind", {}).get("speed", 0.0),
            }
        except Exception:
            logger.warning("OpenWeatherMap weather fetch failed")
            return {}

    # ── Air quality (OpenWeatherMap) ──────────────────────────────

    async def _fetch_air_quality(self, location: GeoLocation) -> dict:
        """Fetch air quality from OpenWeatherMap Air Pollution API."""
        if not settings.openweathermap_api_key:
            return {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{OWM_BASE}/air_pollution",
                    params={
                        "lat": location.lat,
                        "lon": location.lon,
                        "appid": settings.openweathermap_api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            entry = data.get("list", [{}])[0]
            components = entry.get("components", {})
            return {
                "aqi": entry.get("main", {}).get("aqi", 3),
                "pm25": components.get("pm2_5", 0.0),
                "pm10": components.get("pm10", 0.0),
            }
        except Exception:
            logger.warning("OpenWeatherMap air quality fetch failed")
            return {}

    # ── Moon phase (ephem) ────────────────────────────────────────

    @staticmethod
    def _compute_moon_phase() -> tuple[str, float]:
        """Compute current moon phase and illumination using PyEphem."""
        moon = ephem.Moon()
        moon.compute()
        illumination = moon.phase  # 0–100

        # Phase angle from new moon (0–1 cycle)
        # ephem.Moon().phase is illumination %, not phase angle
        # Use the next/prev new moon to determine the phase name
        now = ephem.now()
        prev_new = ephem.previous_new_moon(now)
        cycle_length = 29.530588  # synodic month in days
        days_since_new = float(now - prev_new)
        phase_fraction = days_since_new / cycle_length

        # Map fraction to 8 phases
        idx = int(phase_fraction * 8) % 8
        phase_name = MOON_PHASES[idx]

        return phase_name, round(illumination, 1)

    # ── Light pollution estimate ──────────────────────────────────

    @staticmethod
    def _estimate_bortle(location: GeoLocation) -> int:
        """Estimate Bortle class from location (heuristic).

        Very rough estimate based on latitude distance from major metro areas.
        In production this would use a light pollution map API.
        """
        # Simple heuristic: cities at low latitudes tend to be larger
        abs_lat = abs(location.lat)
        if abs_lat > 60:
            return 3  # Rural, dark skies
        if abs_lat > 45:
            return 5  # Suburban
        return 6  # Urban/suburban fringe

    # ── Composite stargazing score ────────────────────────────────

    @staticmethod
    def _compute_stargazing_score(
        cloud_pct: int,
        bortle: int,
        moon_illum: float,
        aqi: int,
    ) -> float:
        """Weighted composite score (0–100).

        Weights: cloud cover 40%, light pollution 25%,
                 moon illumination 20%, air quality 15%.
        """
        cloud_score = max(0, 100 - cloud_pct)  # 0=overcast, 100=clear
        bortle_score = max(0, (9 - bortle) / 8 * 100)  # Bortle 1=100, 9=0
        moon_score = max(0, 100 - moon_illum)  # New=100, Full=0
        aqi_score = max(0, (5 - aqi) / 4 * 100)  # AQI 1=100, 5=0

        score = (
            cloud_score * 0.40
            + bortle_score * 0.25
            + moon_score * 0.20
            + aqi_score * 0.15
        )
        return round(max(0, min(100, score)), 1)

    # ── Summary text ──────────────────────────────────────────────

    @staticmethod
    def _build_summary(
        score: float,
        cloud_pct: int,
        moon_phase: str,
        aurora_visible: bool,
    ) -> str:
        """Generate a human-readable stargazing briefing."""
        if score >= 80:
            quality = "Excellent"
        elif score >= 60:
            quality = "Good"
        elif score >= 40:
            quality = "Fair"
        elif score >= 20:
            quality = "Poor"
        else:
            quality = "Very poor"

        parts = [f"{quality} stargazing conditions (score: {score}/100)."]

        if cloud_pct > 70:
            parts.append("Heavy cloud cover will obstruct viewing.")
        elif cloud_pct > 40:
            parts.append("Partial cloud cover may limit visibility.")
        else:
            parts.append("Skies are mostly clear.")

        moon_display = moon_phase.replace("_", " ")
        parts.append(f"Moon phase: {moon_display}.")

        if aurora_visible:
            parts.append("Aurora activity is possible tonight!")

        return " ".join(parts)


sky_service = SkyService()
