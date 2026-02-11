"""Tests for Lambda handler functions.

Since ``lambda`` is a Python reserved keyword, we use
``importlib.util.spec_from_file_location`` to load handler modules
directly by file path.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_LAMBDA_DIR = Path(__file__).resolve().parent.parent / "lambda"


def _load_handler(rel_path: str, module_name: str):
    """Load a handler module from the lambda directory by file path.

    ``rel_path`` is relative to ``lambda/``, e.g. "functions/ingest_nasa/handler.py".
    ``module_name`` is an arbitrary module name used for registration.
    """
    os.environ.setdefault("DYNAMODB_TABLE", "test-table")
    file_path = _LAMBDA_DIR / rel_path
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── NASA ingest ──────────────────────────────────────────────────


class TestIngestNasaHandler:
    """Tests for the NASA ingest Lambda handler."""

    def test_ingest_apod_parses_response(self):
        mod = _load_handler("functions/ingest_nasa/handler.py", "_lh_ingest_nasa")

        mock_data = {
            "title": "Test Galaxy",
            "url": "https://apod.nasa.gov/test.jpg",
            "media_type": "image",
            "explanation": "A beautiful galaxy.",
            "date": "2026-02-10",
        }

        with patch.object(mod, "urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_data).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            items = mod._ingest_apod()
            assert len(items) == 1
            assert items[0]["source"] == "NASA_APOD"
            assert items[0]["payload"]["title"] == "Test Galaxy"
            assert items[0]["data_type"] == "apod"

    def test_ingest_neo_parses_response(self):
        mod = _load_handler("functions/ingest_nasa/handler.py", "_lh_ingest_nasa")

        mock_data = {
            "element_count": 1,
            "near_earth_objects": {
                "2026-02-10": [
                    {
                        "id": "54321",
                        "name": "TestRock",
                        "is_potentially_hazardous_asteroid": True,
                        "absolute_magnitude_h": 22.0,
                        "estimated_diameter": {
                            "kilometers": {
                                "estimated_diameter_min": 0.05,
                                "estimated_diameter_max": 0.12,
                            }
                        },
                        "close_approach_data": [
                            {
                                "close_approach_date": "2026-02-10",
                                "miss_distance": {
                                    "kilometers": "500000",
                                    "lunar": "1.3",
                                },
                                "relative_velocity": {"kilometers_per_second": "15.2"},
                            }
                        ],
                    }
                ]
            },
        }

        with patch.object(mod, "urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_data).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            items = mod._ingest_neo()
            assert len(items) == 1
            assert items[0]["source"] == "NASA_NEO"
            assert items[0]["payload"]["is_potentially_hazardous"] is True
            assert items[0]["payload"]["miss_distance_km"] == 500000.0


# ── NIST ingest ──────────────────────────────────────────────────


class TestIngestNistHandler:
    """Tests for the NIST CVE ingest Lambda handler."""

    def test_fetch_cves_parses_nvd_response(self):
        mod = _load_handler("functions/ingest_nist/handler.py", "_lh_ingest_nist")

        mock_data = {
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-2026-0001",
                        "descriptions": [{"lang": "en", "value": "Test vulnerability"}],
                        "published": "2026-02-08T00:00:00.000",
                        "lastModified": "2026-02-09T00:00:00.000",
                        "metrics": {
                            "cvssMetricV31": [
                                {
                                    "cvssData": {
                                        "baseScore": 9.8,
                                        "baseSeverity": "CRITICAL",
                                    }
                                }
                            ]
                        },
                        "references": [{"url": "https://example.com/advisory"}],
                    }
                }
            ]
        }

        with patch.object(mod, "urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_data).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            items = mod._fetch_cves(days=7)
            assert len(items) == 1
            assert items[0]["source"] == "NIST_CVE"
            assert items[0]["payload"]["cve_id"] == "CVE-2026-0001"
            assert items[0]["payload"]["cvss_score"] == 9.8
            assert items[0]["payload"]["severity"] == "CRITICAL"


# ── Space ingest ─────────────────────────────────────────────────


class TestIngestSpaceHandler:
    """Tests for the space data ingest Lambda handler."""

    def test_ingest_celestrak_parses_gp_json(self):
        mod = _load_handler("functions/ingest_space/handler.py", "_lh_ingest_space")

        mock_data = [
            {
                "NORAD_CAT_ID": 25544,
                "OBJECT_NAME": "ISS (ZARYA)",
                "TLE_LINE1": "1 25544U ...",
                "TLE_LINE2": "2 25544 ...",
                "EPOCH": "2026-02-10T12:00:00",
                "INCLINATION": 51.6,
                "ECCENTRICITY": 0.0001,
                "OBJECT_TYPE": "PAYLOAD",
            }
        ]

        with patch.object(mod, "urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_data).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            items = mod._ingest_celestrak()
            assert len(items) == 1
            assert items[0]["source"] == "CELESTRAK"
            assert items[0]["payload"]["name"] == "ISS (ZARYA)"

    def test_ingest_solar_wind_parses_swpc(self):
        mod = _load_handler("functions/ingest_space/handler.py", "_lh_ingest_space")

        # NOAA format: [header, data_rows...]
        mock_data = [
            ["time_tag", "speed"],
            ["2026-02-10 00:00:00.000", "450.0"],
            ["2026-02-10 01:00:00.000", "460.0"],
        ]

        with patch.object(mod, "urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_data).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            items = mod._ingest_solar_wind()
            assert len(items) == 2
            assert items[0]["source"] == "NOAA_SPACE"
            assert items[0]["payload"]["report_type"] == "solar_wind"
            assert items[0]["payload"]["solar_wind_speed"] == 450.0


# ── Embed sync ───────────────────────────────────────────────────


class TestEmbedSyncHandler:
    """Tests for the embed sync Lambda handler."""

    def test_build_text_for_embedding(self):
        mod = _load_handler("functions/embed_sync/handler.py", "_lh_embed_sync")

        item = {
            "source": "NASA_APOD",
            "data_type": "apod",
            "payload": {
                "title": "Orion Nebula",
                "explanation": "A beautiful nebula in the constellation Orion.",
            },
        }
        text = mod._build_text_for_embedding(item)
        assert "NASA_APOD" in text
        assert "Orion Nebula" in text
        assert "beautiful nebula" in text

    def test_handler_skips_without_azure_config(self):
        mod = _load_handler("functions/embed_sync/handler.py", "_lh_embed_sync")

        with patch.object(mod, "AZURE_OPENAI_ENDPOINT", ""):
            result = mod.lambda_handler({"Records": []}, None)
            assert result["statusCode"] == 200
            assert result["body"] == "skipped"
