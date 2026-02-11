"""Lambda handler — Ingest CelesTrak TLE and NOAA Space Weather data."""

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
TTL_DAYS = 90

CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
NOAA_SWPC_URL = "https://services.swpc.noaa.gov/products"


def _ttl_epoch() -> int:
    return int(time.time()) + (TTL_DAYS * 86400)


def _api_get(url: str) -> dict | list:
    req = Request(url, headers={"User-Agent": "witness-ingest/1.0"})  # noqa: S310
    with urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read())


def _ingest_celestrak() -> list[dict]:
    """Fetch active satellite TLE data from CelesTrak GP JSON API."""
    url = f"{CELESTRAK_GP_URL}?GROUP=active&FORMAT=json"
    data = _api_get(url)
    now = datetime.now(UTC).isoformat()
    items = []

    for sat in data[:100]:  # Limit to 100 most notable
        norad_id = str(sat.get("NORAD_CAT_ID", ""))
        items.append(
            {
                "source": "CELESTRAK",
                "sort_key": f"norad#{norad_id}",
                "data_type": "tle",
                "timestamp": now,
                "expiry_epoch": _ttl_epoch(),
                "payload": {
                    "norad_id": norad_id,
                    "name": sat.get("OBJECT_NAME", ""),
                    "line1": sat.get("TLE_LINE1", ""),
                    "line2": sat.get("TLE_LINE2", ""),
                    "epoch": sat.get("EPOCH", ""),
                    "inclination": float(sat.get("INCLINATION", 0)),
                    "eccentricity": float(sat.get("ECCENTRICITY", 0)),
                    "object_type": sat.get("OBJECT_TYPE", ""),
                },
            }
        )
    return items


def _ingest_solar_wind() -> list[dict]:
    """Fetch NOAA SWPC solar wind data."""
    data = _api_get(f"{NOAA_SWPC_URL}/solar-wind/plasma-7-day.json")
    now = datetime.now(UTC).isoformat()
    items = []

    # Data is [[header], [row1], ...] — skip header, take last 24 entries (~1 per hour)
    if len(data) > 1:
        for row in data[1:][-24:]:
            ts = row[0] if len(row) > 0 else ""
            speed = float(row[1]) if len(row) > 1 and row[1] else 0.0
            items.append(
                {
                    "source": "NOAA_SPACE",
                    "sort_key": f"type#solar_wind#ts#{ts}",
                    "data_type": "space_weather",
                    "timestamp": now,
                    "expiry_epoch": _ttl_epoch(),
                    "payload": {
                        "report_type": "solar_wind",
                        "solar_wind_speed": speed,
                        "observed_at": ts,
                    },
                }
            )
    return items


def _ingest_geomagnetic() -> list[dict]:
    """Fetch NOAA planetary K-index (Kp) data."""
    data = _api_get(f"{NOAA_SWPC_URL}/noaa-planetary-k-index.json")
    now = datetime.now(UTC).isoformat()
    items = []

    if len(data) > 1:
        for row in data[-8:]:  # Last 8 entries (3-hour Kp values = 24h)
            ts = row[0] if len(row) > 0 else ""
            kp = float(row[1]) if len(row) > 1 and row[1] else 0.0
            items.append(
                {
                    "source": "NOAA_SPACE",
                    "sort_key": f"type#geomagnetic#ts#{ts}",
                    "data_type": "space_weather",
                    "timestamp": now,
                    "expiry_epoch": _ttl_epoch(),
                    "payload": {
                        "report_type": "geomagnetic",
                        "kp_index": kp,
                        "observed_at": ts,
                    },
                }
            )
    return items


def _ingest_mag_field() -> list[dict]:
    """Fetch NOAA interplanetary magnetic field (Bt/Bz) data."""
    data = _api_get(f"{NOAA_SWPC_URL}/solar-wind/mag-7-day.json")
    now = datetime.now(UTC).isoformat()
    items = []

    if len(data) > 1:
        for row in data[-24:]:
            ts = row[0] if len(row) > 0 else ""
            bt = float(row[6]) if len(row) > 6 and row[6] else 0.0
            bz = float(row[3]) if len(row) > 3 and row[3] else 0.0
            items.append(
                {
                    "source": "NOAA_SPACE",
                    "sort_key": f"type#mag_field#ts#{ts}",
                    "data_type": "space_weather",
                    "timestamp": now,
                    "expiry_epoch": _ttl_epoch(),
                    "payload": {
                        "report_type": "mag_field",
                        "bt": bt,
                        "bz": bz,
                        "observed_at": ts,
                    },
                }
            )
    return items


def lambda_handler(event, context):
    """Lambda entry point — ingest space data sources."""
    import sys

    sys.path.insert(0, "/opt")
    from dynamo_writer import batch_write_items

    results = {}
    for name, fetcher in [
        ("celestrak", _ingest_celestrak),
        ("solar_wind", _ingest_solar_wind),
        ("geomagnetic", _ingest_geomagnetic),
        ("mag_field", _ingest_mag_field),
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
