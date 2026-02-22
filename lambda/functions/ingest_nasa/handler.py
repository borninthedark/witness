"""Lambda handler — Ingest NASA APOD, NEO, Exoplanet, and Mars Rover data."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from urllib.request import Request, urlopen

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ["DYNAMODB_TABLE"]
NASA_API_KEY = os.environ.get("NASA_API_KEY", "DEMO_KEY")
TTL_DAYS = 90


def _api_get(url: str, params: dict | None = None) -> dict | list:
    """Simple HTTP GET returning parsed JSON."""
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"
    req = Request(url, headers={"User-Agent": "witness-ingest/1.0"})  # noqa: S310
    with urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read())


def _ttl_epoch() -> int:
    return int(time.time()) + (TTL_DAYS * 86400)


def _ingest_apod() -> list[dict]:
    """Fetch Astronomy Picture of the Day."""
    data = _api_get("https://api.nasa.gov/planetary/apod", {"api_key": NASA_API_KEY})
    now = datetime.now(UTC).isoformat()
    date = data.get("date", now[:10])
    return [
        {
            "source": "NASA_APOD",
            "sort_key": f"date#{date}#id#apod-latest",
            "data_type": "apod",
            "timestamp": now,
            "expiry_epoch": _ttl_epoch(),
            "payload": {
                "title": data.get("title", ""),
                "url": data.get("url", ""),
                "hdurl": data.get("hdurl", ""),
                "media_type": data.get("media_type", "image"),
                "explanation": data.get("explanation", ""),
                "date": date,
            },
        }
    ]


def _ingest_neo() -> list[dict]:
    """Fetch Near-Earth Objects for today."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    data = _api_get(
        "https://api.nasa.gov/neo/rest/v1/feed",
        {"start_date": today, "end_date": today, "api_key": NASA_API_KEY},
    )
    now = datetime.now(UTC).isoformat()
    items = []
    for _date_key, objects in data.get("near_earth_objects", {}).items():
        for obj in objects:
            approach = (
                obj.get("close_approach_data", [{}])[0]
                if obj.get("close_approach_data")
                else {}
            )
            diameter = obj.get("estimated_diameter", {}).get("kilometers", {})
            miss = approach.get("miss_distance", {})
            vel = approach.get("relative_velocity", {})
            neo_id = obj.get("id", "unknown")
            items.append(
                {
                    "source": "NASA_NEO",
                    "sort_key": f"date#{today}#id#{neo_id}",
                    "data_type": "neo",
                    "timestamp": now,
                    "expiry_epoch": _ttl_epoch(),
                    "payload": {
                        "name": obj.get("name", "Unknown"),
                        "estimated_diameter_km_min": float(
                            diameter.get("estimated_diameter_min", 0)
                        ),
                        "estimated_diameter_km_max": float(
                            diameter.get("estimated_diameter_max", 0)
                        ),
                        "is_potentially_hazardous": obj.get(
                            "is_potentially_hazardous_asteroid", False
                        ),
                        "miss_distance_km": float(miss.get("kilometers", 0)),
                        "miss_distance_lunar": float(miss.get("lunar", 0)),
                        "relative_velocity_km_s": float(
                            vel.get("kilometers_per_second", 0)
                        ),
                        "close_approach_date": approach.get("close_approach_date", ""),
                        "absolute_magnitude": float(obj.get("absolute_magnitude_h", 0)),
                    },
                }
            )
    return items


def _ingest_exoplanets() -> list[dict]:
    """Fetch recently confirmed exoplanets from NASA Exoplanet Archive."""
    query = (
        "select+pl_name,hostname,discoverymethod,disc_year,pl_orbper,"
        "pl_rade,pl_bmasse,sy_dist,pl_eqt"
        "+from+ps+where+disc_year>=2025+and+default_flag=1"
        "+order+by+disc_year+desc"
    )
    url = (
        f"https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query={query}&format=json"
    )
    data = _api_get(url)
    now = datetime.now(UTC).isoformat()
    items = []
    for row in data[:50]:  # Limit to 50 recent
        name = row.get("pl_name", "Unknown")
        items.append(
            {
                "source": "NASA_EXOPLANET",
                "sort_key": f"name#{name}",
                "data_type": "exoplanet",
                "timestamp": now,
                "expiry_epoch": _ttl_epoch(),
                "payload": {
                    "planet_name": name,
                    "host_star": row.get("hostname", ""),
                    "discovery_method": row.get("discoverymethod", ""),
                    "discovery_year": row.get("disc_year", 0),
                    "orbital_period_days": float(row.get("pl_orbper") or 0),
                    "planet_radius_earth": float(row.get("pl_rade") or 0),
                    "planet_mass_earth": float(row.get("pl_bmasse") or 0),
                    "distance_parsec": float(row.get("sy_dist") or 0),
                    "equilibrium_temp_k": float(row.get("pl_eqt") or 0),
                },
            }
        )
    return items


def _ingest_mars_rover() -> list[dict]:
    """Fetch latest Mars Rover photos (Curiosity)."""
    data = _api_get(
        "https://api.nasa.gov/mars-photos/api/v1/rovers/curiosity/latest_photos",
        {"api_key": NASA_API_KEY},
    )
    now = datetime.now(UTC).isoformat()
    items = []
    for photo in data.get("latest_photos", [])[:20]:  # Limit to 20
        photo_id = photo.get("id", 0)
        items.append(
            {
                "source": "NASA_MARS_ROVER",
                "sort_key": f"id#{photo_id}",
                "data_type": "mars",
                "timestamp": now,
                "expiry_epoch": _ttl_epoch(),
                "payload": {
                    "rover_name": photo.get("rover", {}).get("name", ""),
                    "camera_name": photo.get("camera", {}).get("name", ""),
                    "camera_full_name": photo.get("camera", {}).get("full_name", ""),
                    "img_src": photo.get("img_src", ""),
                    "earth_date": photo.get("earth_date", ""),
                    "sol": photo.get("sol", 0),
                    "photo_id": photo_id,
                },
            }
        )
    return items


def lambda_handler(event, context):
    """Lambda entry point — ingest all NASA sources."""
    # Import here to allow layer resolution at runtime
    import sys

    sys.path.insert(0, "/opt")
    from dynamo_writer import batch_write_items

    results = {}
    for name, fetcher in [
        ("apod", _ingest_apod),
        ("neo", _ingest_neo),
        ("exoplanet", _ingest_exoplanets),
        ("mars_rover", _ingest_mars_rover),
    ]:
        try:
            items = fetcher()
            written = batch_write_items(TABLE_NAME, items)
            results[name] = {"fetched": len(items), "written": written}
            logger.info("%s: fetched=%d written=%d", name, len(items), written)
        except Exception:
            logger.exception("Failed to ingest %s", name)
            results[name] = {"error": True}

    return {"statusCode": 200, "body": results}
