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


# ── Secrets rotation ────────────────────────────────────────────


def _make_rotation_event(step: str = "createSecret") -> dict:
    return {
        "SecretId": "arn:aws:secretsmanager:us-east-1:123:secret:test",
        "ClientRequestToken": "token-123",
        "Step": step,
    }


def _make_sm_client(
    *,
    rotation_enabled: bool = True,
    versions: dict | None = None,
) -> MagicMock:
    """Build a mock Secrets Manager client with describe_secret pre-set."""
    client = MagicMock()
    if versions is None:
        versions = {"token-123": ["AWSPENDING"]}
    client.describe_secret.return_value = {
        "RotationEnabled": rotation_enabled,
        "VersionIdsToStages": versions,
    }
    # ResourceNotFoundException as a nested exception class
    exc_cls = type("ResourceNotFoundException", (Exception,), {})
    client.exceptions = MagicMock()
    client.exceptions.ResourceNotFoundException = exc_cls
    return client


class TestRotateSecretHandler:
    """Tests for the secrets rotation Lambda handler."""

    def _load(self):
        return _load_handler("functions/rotate_secret/handler.py", "_lh_rotate_secret")

    def test_rotation_not_enabled_raises(self):
        mod = self._load()
        client = _make_sm_client(rotation_enabled=False)
        with patch.object(mod, "boto3") as mock_boto:
            mock_boto.client.return_value = client
            import pytest

            with pytest.raises(ValueError, match="not enabled for rotation"):
                mod.lambda_handler(_make_rotation_event(), None)

    def test_unknown_token_raises(self):
        mod = self._load()
        client = _make_sm_client(versions={"other-token": ["AWSCURRENT"]})
        with patch.object(mod, "boto3") as mock_boto:
            mock_boto.client.return_value = client
            import pytest

            with pytest.raises(ValueError, match="has no stage"):
                mod.lambda_handler(_make_rotation_event(), None)

    def test_already_current_returns_early(self):
        mod = self._load()
        client = _make_sm_client(versions={"token-123": ["AWSCURRENT", "AWSPENDING"]})
        with patch.object(mod, "boto3") as mock_boto:
            mock_boto.client.return_value = client
            mod.lambda_handler(_make_rotation_event(), None)
        # No step function should be called
        client.get_secret_value.assert_not_called()

    def test_not_awspending_raises(self):
        mod = self._load()
        client = _make_sm_client(versions={"token-123": ["AWSPREVIOUS"]})
        with patch.object(mod, "boto3") as mock_boto:
            mock_boto.client.return_value = client
            import pytest

            with pytest.raises(ValueError, match="not set as AWSPENDING"):
                mod.lambda_handler(_make_rotation_event(), None)

    def test_invalid_step_raises(self):
        mod = self._load()
        client = _make_sm_client()
        with patch.object(mod, "boto3") as mock_boto:
            mock_boto.client.return_value = client
            import pytest

            with pytest.raises(ValueError, match="Invalid step"):
                mod.lambda_handler(_make_rotation_event(step="badStep"), None)

    def test_set_secret_is_noop(self):
        mod = self._load()
        client = _make_sm_client()
        with patch.object(mod, "boto3") as mock_boto:
            mock_boto.client.return_value = client
            mod.lambda_handler(_make_rotation_event(step="setSecret"), None)
        client.put_secret_value.assert_not_called()

    def test_create_secret_generates_new_key(self):
        mod = self._load()
        client = _make_sm_client()
        exc_cls = client.exceptions.ResourceNotFoundException
        client.get_secret_value.side_effect = [
            exc_cls("not found"),
            {
                "SecretString": json.dumps(
                    {
                        "SECRET_KEY": "old-key",
                        "DATABASE_URL": "sqlite:///test.db",
                    }
                )
            },
        ]
        with patch.object(mod, "boto3") as mock_boto:
            mock_boto.client.return_value = client
            mod.lambda_handler(_make_rotation_event(step="createSecret"), None)
        client.put_secret_value.assert_called_once()
        put_args = client.put_secret_value.call_args
        new_secret = json.loads(put_args.kwargs["SecretString"])
        assert "SECRET_KEY" in new_secret
        assert new_secret["SECRET_KEY"] != "old-key"
        assert new_secret["DATABASE_URL"] == "sqlite:///test.db"

    def test_create_secret_skips_if_already_exists(self):
        mod = self._load()
        client = _make_sm_client()
        client.get_secret_value.return_value = {
            "SecretString": json.dumps({"SECRET_KEY": "pending"})
        }
        with patch.object(mod, "boto3") as mock_boto:
            mock_boto.client.return_value = client
            mod.lambda_handler(_make_rotation_event(step="createSecret"), None)
        client.put_secret_value.assert_not_called()

    def test_test_secret_validates_keys(self):
        mod = self._load()
        client = _make_sm_client()
        client.get_secret_value.return_value = {
            "SecretString": json.dumps(
                {"SECRET_KEY": "k", "DATABASE_URL": "sqlite:///x.db"}
            )
        }
        with patch.object(mod, "boto3") as mock_boto:
            mock_boto.client.return_value = client
            mod.lambda_handler(_make_rotation_event(step="testSecret"), None)

    def test_test_secret_missing_key_raises(self):
        mod = self._load()
        client = _make_sm_client()
        client.get_secret_value.return_value = {
            "SecretString": json.dumps({"DATABASE_URL": "x"})
        }
        with patch.object(mod, "boto3") as mock_boto:
            mock_boto.client.return_value = client
            import pytest

            with pytest.raises(ValueError, match="missing SECRET_KEY"):
                mod.lambda_handler(_make_rotation_event(step="testSecret"), None)

    def test_test_secret_missing_db_url_raises(self):
        mod = self._load()
        client = _make_sm_client()
        client.get_secret_value.return_value = {
            "SecretString": json.dumps({"SECRET_KEY": "k"})
        }
        with patch.object(mod, "boto3") as mock_boto:
            mock_boto.client.return_value = client
            import pytest

            with pytest.raises(ValueError, match="missing DATABASE_URL"):
                mod.lambda_handler(_make_rotation_event(step="testSecret"), None)

    def test_finish_secret_promotes_pending(self):
        mod = self._load()
        versions = {
            "old-token": ["AWSCURRENT"],
            "token-123": ["AWSPENDING"],
        }
        client = _make_sm_client(versions=versions)
        with patch.object(mod, "boto3") as mock_boto:
            mock_boto.client.return_value = client
            mod.lambda_handler(_make_rotation_event(step="finishSecret"), None)
        assert client.update_secret_version_stage.call_count == 2

    def test_finish_secret_already_current_noop(self):
        mod = self._load()
        versions = {
            "token-123": ["AWSCURRENT", "AWSPENDING"],
        }
        client = _make_sm_client(versions=versions)
        # Already-current exits at the top of lambda_handler
        with patch.object(mod, "boto3") as mock_boto:
            mock_boto.client.return_value = client
            mod.lambda_handler(_make_rotation_event(step="finishSecret"), None)
        client.update_secret_version_stage.assert_not_called()

    def test_finish_secret_internal_already_current_returns(self):
        """Cover the early return inside _finish_secret when token is AWSCURRENT."""
        mod = self._load()
        client = MagicMock()
        versions = {"token-123": ["AWSCURRENT"]}
        mod._finish_secret(client, "arn:test", "token-123", versions)
        client.update_secret_version_stage.assert_not_called()
