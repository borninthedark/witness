"""Astrometrics — NASA APOD + NEO data with AI briefing."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import BaseModel

from fitness.config import settings
from fitness.services.captains_log import compute_stardate

logger = logging.getLogger(__name__)

CACHE_PATH = Path(settings.data_dir) / "astrometrics-cache.json"
CACHE_MAX_AGE_SECONDS = 86400  # 24 hours

NASA_APOD_URL = "https://api.nasa.gov/planetary/apod"
NASA_NEO_URL = "https://api.nasa.gov/neo/rest/v1/feed"

ASTROMETRICS_SYSTEM_PROMPT = """\
You are the Astrometrics officer aboard the USS Enterprise-D, presenting a \
daily science briefing to the senior staff. Synthesize the provided NASA data \
into a concise, engaging briefing in the style of a TNG crew report.

Rules:
- Write 2-3 paragraphs, professional yet accessible
- Reference the APOD subject and any notable near-Earth objects
- Use TNG-flavored language naturally (don't overdo it)
- End with a one-sentence "recommendation" for the captain
"""


class AstrometricsBriefing(BaseModel):
    """Astrometrics briefing data model."""

    apod_title: str = ""
    apod_url: str = ""
    apod_media_type: str = "image"
    apod_explanation: str = ""
    neo_count: int = 0
    neo_closest: str = ""
    briefing_narrative: str = ""
    stardate: str = ""
    generated_at: str = ""


class AstrometricsService:
    """Fetch NASA data and generate AI-powered science briefings."""

    def __init__(self) -> None:
        self._anthropic_client = None

    @property
    def _nasa_api_key(self) -> str:
        return settings.nasa_api_key or "DEMO_KEY"

    def _get_anthropic_client(self):
        if self._anthropic_client is None:
            if not settings.anthropic_api_key:
                return None
            from anthropic import AsyncAnthropic

            self._anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._anthropic_client

    def _read_cache(self) -> AstrometricsBriefing | None:
        """Read cached briefing if fresh enough."""
        if not CACHE_PATH.exists():
            return None
        try:
            raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            generated_at = datetime.fromisoformat(raw["generated_at"])
            age = (datetime.now(UTC) - generated_at).total_seconds()
            if age < CACHE_MAX_AGE_SECONDS:
                return AstrometricsBriefing(**raw)
        except Exception:
            logger.debug("Cache read failed, will regenerate")
        return None

    def _write_cache(self, briefing: AstrometricsBriefing) -> None:
        """Persist briefing to disk cache."""
        try:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PATH.write_text(briefing.model_dump_json(indent=2), encoding="utf-8")
        except Exception:
            logger.debug("Could not write astrometrics cache")

    async def _fetch_apod(self) -> dict:
        """Fetch NASA Astronomy Picture of the Day."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                NASA_APOD_URL, params={"api_key": self._nasa_api_key}
            )
            resp.raise_for_status()
            return resp.json()

    async def _fetch_neo(self) -> dict:
        """Fetch NASA Near Earth Objects for today."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                NASA_NEO_URL,
                params={
                    "start_date": today,
                    "end_date": today,
                    "api_key": self._nasa_api_key,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def _generate_narrative(
        self, apod: dict, neo_count: int, neo_closest: str
    ) -> str:
        """Generate AI briefing narrative from NASA data."""
        client = self._get_anthropic_client()
        if client is None:
            return "AI briefing unavailable — Anthropic API key not configured."

        user_prompt = (
            f"Today's APOD: \"{apod.get('title', 'N/A')}\" — "
            f"{apod.get('explanation', 'No description available.')}\n\n"
            f"Near-Earth Objects today: {neo_count} tracked.\n"
            f"Closest approach: {neo_closest}\n\n"
            "Generate the astrometrics briefing."
        )

        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=ASTROMETRICS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except Exception:
            logger.exception("Failed to generate astrometrics narrative")
            return "AI briefing generation failed. Raw data is displayed above."

    @staticmethod
    def _parse_closest_neo(neo_data: dict) -> tuple[int, str]:
        """Extract NEO count and closest approach from NASA feed data."""
        neo_count = neo_data.get("element_count", 0)
        closest_name = "None detected"
        closest_distance = float("inf")

        for _date_key, objects in neo_data.get("near_earth_objects", {}).items():
            for obj in objects:
                for approach in obj.get("close_approach_data", []):
                    dist_km = float(
                        approach.get("miss_distance", {}).get("kilometers", "inf")
                    )
                    if dist_km < closest_distance:
                        closest_distance = dist_km
                        closest_name = (
                            f"{obj.get('name', 'Unknown')} "
                            f"({closest_distance:,.0f} km)"
                        )
        return neo_count, closest_name

    async def get_briefing(self, force_refresh: bool = False) -> AstrometricsBriefing:
        """Get astrometrics briefing, using cache when available."""
        if not force_refresh:
            cached = self._read_cache()
            if cached:
                return cached

        # Fetch NASA data with graceful fallbacks
        apod = {}
        neo_count = 0
        neo_closest = "Data unavailable"

        try:
            apod = await self._fetch_apod()
        except Exception:
            logger.warning("APOD fetch failed")

        try:
            neo_data = await self._fetch_neo()
            neo_count, neo_closest = self._parse_closest_neo(neo_data)
        except Exception:
            logger.warning("NEO fetch failed")

        narrative = await self._generate_narrative(apod, neo_count, neo_closest)

        briefing = AstrometricsBriefing(
            apod_title=apod.get("title", "Unavailable"),
            apod_url=apod.get("url", ""),
            apod_media_type=apod.get("media_type", "image"),
            apod_explanation=apod.get("explanation", ""),
            neo_count=neo_count,
            neo_closest=neo_closest,
            briefing_narrative=narrative,
            stardate=compute_stardate(),
            generated_at=datetime.now(UTC).isoformat(),
        )

        self._write_cache(briefing)
        return briefing


astrometrics_service = AstrometricsService()
