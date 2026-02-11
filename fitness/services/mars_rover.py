"""NASA Mars Rover Photos data service."""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from fitness.config import settings

logger = logging.getLogger(__name__)

MARS_ROVER_URL = (
    "https://api.nasa.gov/mars-photos/api/v1/rovers/curiosity/latest_photos"
)


class MarsRoverPhoto(BaseModel):
    """Mars Rover photo metadata."""

    rover_name: str
    camera_name: str
    camera_full_name: str = ""
    img_src: str
    earth_date: str = ""
    sol: int = 0
    photo_id: int = 0


class MarsRoverService:
    """Fetch Mars Rover photo data from NASA."""

    @property
    def _api_key(self) -> str:
        return settings.nasa_api_key or "DEMO_KEY"

    @staticmethod
    def _read_from_dynamo(limit: int = 20) -> list[MarsRoverPhoto] | None:
        from fitness.services.data_store import read_latest_from_dynamo

        return read_latest_from_dynamo("NASA_MARS_ROVER", MarsRoverPhoto, limit, logger)

    async def get_latest_photos(self, limit: int = 20) -> list[MarsRoverPhoto]:
        """Get latest Mars Rover photos."""
        if settings.use_data_store:
            result = self._read_from_dynamo(limit)
            if result is not None:
                return result

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    MARS_ROVER_URL,
                    params={"api_key": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            logger.warning("NASA Mars Rover API fetch failed")
            return []

        photos = []
        for photo in data.get("latest_photos", [])[:limit]:
            photos.append(
                MarsRoverPhoto(
                    rover_name=photo.get("rover", {}).get("name", ""),
                    camera_name=photo.get("camera", {}).get("name", ""),
                    camera_full_name=photo.get("camera", {}).get("full_name", ""),
                    img_src=photo.get("img_src", ""),
                    earth_date=photo.get("earth_date", ""),
                    sol=photo.get("sol", 0),
                    photo_id=photo.get("id", 0),
                )
            )
        return photos


mars_rover_service = MarsRoverService()
