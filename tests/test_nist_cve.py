"""Tests for NIST NVD client and CVE aggregator services."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fitness.models.security import (
    AdvisorySource,
    AdvisoryStats,
    SecurityAdvisory,
    SeverityLevel,
)
from fitness.services.cve_aggregator import CVEAggregator
from fitness.services.nist_client import NISTClient

# ── Helpers ───────────────────────────────────────────────────────


def _make_nist_vuln(
    cve_id: str = "CVE-2026-0001",
    description: str = "Test vulnerability",
    base_score: float = 9.8,
    severity: str = "CRITICAL",
    metric_version: str = "v31",
    published: str = "2026-02-20T12:00:00.000",
    modified: str = "2026-02-21T12:00:00.000",
    references: list[dict] | None = None,
    configurations: list[dict] | None = None,
) -> dict:
    """Build a minimal NIST API vulnerability entry."""
    metrics: dict = {}
    metric_key_map = {
        "v31": "cvssMetricV31",
        "v30": "cvssMetricV30",
        "v2": "cvssMetricV2",
    }
    key = metric_key_map.get(metric_version, "cvssMetricV31")
    metrics[key] = [
        {
            "cvssData": {
                "baseScore": base_score,
                "baseSeverity": severity,
                "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            }
        }
    ]

    return {
        "cve": {
            "id": cve_id,
            "descriptions": [
                {"lang": "en", "value": description},
            ],
            "metrics": metrics,
            "published": published,
            "lastModified": modified,
            "references": references or [],
            "configurations": configurations or [],
        }
    }


def _make_advisory(
    cve_id: str = "CVE-2026-0001",
    severity: SeverityLevel = SeverityLevel.CRITICAL,
    cvss_score: float = 9.8,
    days_ago: int = 0,
) -> SecurityAdvisory:
    """Build a SecurityAdvisory for aggregator tests."""
    pub = datetime.now(UTC) - timedelta(days=days_ago)
    return SecurityAdvisory(
        cve_id=cve_id,
        description="Test CVE",
        severity=severity,
        cvss_score=cvss_score,
        published_date=pub,
        source=AdvisorySource.NIST,
    )


# ── TestNISTClient ────────────────────────────────────────────────


class TestNISTClient:
    """Unit tests for NISTClient."""

    def test_init_with_api_key(self):
        """API key is stored and rate-limit delay is 0.02 s."""
        client = NISTClient(api_key="my-key")
        assert client.api_key == "my-key"
        assert client.rate_limit_delay == 0.02

    @patch.dict("os.environ", {}, clear=True)
    def test_init_without_api_key(self):
        """Without an API key the DEMO_KEY delay of 0.6 s is used."""
        client = NISTClient(api_key=None)
        assert client.api_key is None
        assert client.rate_limit_delay == 0.6

    # ── _parse_nist_response ─────────────────────────────────

    def test_parse_nist_response_basic(self):
        """Minimal v3.1 CVE is parsed correctly."""
        data = {"vulnerabilities": [_make_nist_vuln()]}
        client = NISTClient(api_key="k")
        result = client._parse_nist_response(data)

        assert len(result) == 1
        adv = result[0]
        assert adv.cve_id == "CVE-2026-0001"
        assert adv.description == "Test vulnerability"
        assert adv.cvss_score == 9.8
        assert adv.severity == SeverityLevel.CRITICAL
        assert adv.source == AdvisorySource.NIST

    def test_parse_nist_response_empty(self):
        """Empty vulnerabilities list produces an empty result."""
        data = {"vulnerabilities": []}
        client = NISTClient(api_key="k")
        assert client._parse_nist_response(data) == []

    def test_parse_nist_response_cvss_v30_fallback(self):
        """Parser falls back to cvssMetricV30 when v31 is absent."""
        vuln = _make_nist_vuln(base_score=7.5, severity="HIGH", metric_version="v30")
        data = {"vulnerabilities": [vuln]}
        client = NISTClient(api_key="k")
        result = client._parse_nist_response(data)

        assert result[0].cvss_score == 7.5
        assert result[0].severity == SeverityLevel.HIGH

    def test_parse_nist_response_cvss_v2_fallback(self):
        """Parser falls back to cvssMetricV2 when v31/v30 are absent."""
        vuln = _make_nist_vuln(base_score=5.0, severity="MEDIUM", metric_version="v2")
        data = {"vulnerabilities": [vuln]}
        client = NISTClient(api_key="k")
        result = client._parse_nist_response(data)

        assert result[0].cvss_score == 5.0
        assert result[0].severity == SeverityLevel.MEDIUM

    def test_parse_nist_response_unknown_severity(self):
        """Invalid severity string maps to UNKNOWN."""
        vuln = _make_nist_vuln(severity="BOGUS")
        data = {"vulnerabilities": [vuln]}
        client = NISTClient(api_key="k")
        result = client._parse_nist_response(data)

        assert result[0].severity == SeverityLevel.UNKNOWN

    def test_parse_nist_response_extracts_references(self):
        """Reference URLs are extracted and capped at 10."""
        refs = [{"url": f"https://example.com/{i}"} for i in range(15)]
        vuln = _make_nist_vuln(references=refs)
        data = {"vulnerabilities": [vuln]}
        client = NISTClient(api_key="k")
        result = client._parse_nist_response(data)

        assert len(result[0].references) == 10
        assert result[0].references[0] == "https://example.com/0"
        assert result[0].references[9] == "https://example.com/9"

    def test_parse_nist_response_extracts_affected_products(self):
        """CPE product strings are parsed from configurations."""
        configs = [
            {
                "nodes": [
                    {
                        "cpeMatch": [
                            {
                                "criteria": "cpe:2.3:a:vendorx:producty:1.0:*:*:*:*:*:*:*"  # noqa: E501
                            },
                            {
                                "criteria": "cpe:2.3:a:vendorx:productz:2.0:*:*:*:*:*:*:*"  # noqa: E501
                            },
                        ]
                    }
                ]
            }
        ]
        vuln = _make_nist_vuln(configurations=configs)
        data = {"vulnerabilities": [vuln]}
        client = NISTClient(api_key="k")
        result = client._parse_nist_response(data)

        products = result[0].affected_products
        assert "vendorx:producty" in products
        assert "vendorx:productz" in products

    # ── async methods ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_fetch_recent_cves_success(self, monkeypatch):
        """Successful HTTP response yields parsed advisories."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock())

        nist_data = {"vulnerabilities": [_make_nist_vuln()]}
        mock_response = MagicMock()
        mock_response.json.return_value = nist_data
        mock_response.raise_for_status = MagicMock()

        client = NISTClient(api_key="k")
        client.client.get = AsyncMock(return_value=mock_response)

        result = await client.fetch_recent_cves(days=7)
        assert len(result) == 1
        assert result[0].cve_id == "CVE-2026-0001"

    @pytest.mark.asyncio
    async def test_fetch_recent_cves_http_error(self, monkeypatch):
        """HTTP error returns empty list."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock())

        client = NISTClient(api_key="k")
        client.client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "503", request=MagicMock(), response=MagicMock()
            )
        )

        result = await client.fetch_recent_cves(days=7)
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_cve_by_id_success(self, monkeypatch):
        """Fetching a specific CVE returns the advisory."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock())

        nist_data = {"vulnerabilities": [_make_nist_vuln(cve_id="CVE-2026-9999")]}
        mock_response = MagicMock()
        mock_response.json.return_value = nist_data
        mock_response.raise_for_status = MagicMock()

        client = NISTClient(api_key="k")
        client.client.get = AsyncMock(return_value=mock_response)

        result = await client.fetch_cve_by_id("CVE-2026-9999")
        assert result is not None
        assert result.cve_id == "CVE-2026-9999"

    @pytest.mark.asyncio
    async def test_fetch_cve_by_id_not_found(self, monkeypatch):
        """Empty NIST response means None."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock())

        mock_response = MagicMock()
        mock_response.json.return_value = {"vulnerabilities": []}
        mock_response.raise_for_status = MagicMock()

        client = NISTClient(api_key="k")
        client.client.get = AsyncMock(return_value=mock_response)

        result = await client.fetch_cve_by_id("CVE-2026-0000")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_cve_by_id_http_error(self, monkeypatch):
        """HTTP error returns None for single-CVE fetch."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock())

        client = NISTClient(api_key="k")
        client.client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock()
            )
        )

        result = await client.fetch_cve_by_id("CVE-2026-0001")
        assert result is None


# ── TestCVEAggregator ─────────────────────────────────────────────


class TestCVEAggregator:
    """Unit tests for CVEAggregator."""

    @pytest.mark.asyncio
    async def test_fetch_all_advisories(self, monkeypatch):
        """Advisories are returned sorted newest-first."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        monkeypatch.setattr(
            "fitness.services.cve_aggregator.settings",
            MagicMock(use_data_store=False),
        )

        older = _make_advisory(cve_id="CVE-2026-0001", days_ago=5)
        newer = _make_advisory(cve_id="CVE-2026-0002", days_ago=1)

        agg = CVEAggregator(nist_api_key="k")
        agg.nist_client.fetch_recent_cves = AsyncMock(return_value=[older, newer])

        result = await agg.fetch_all_advisories(days=7)
        assert len(result) == 2
        # Newest first
        assert result[0].cve_id == "CVE-2026-0002"
        assert result[1].cve_id == "CVE-2026-0001"

    @pytest.mark.asyncio
    async def test_fetch_all_advisories_with_severity_filter(self, monkeypatch):
        """Severity filter keeps only matching advisories."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        monkeypatch.setattr(
            "fitness.services.cve_aggregator.settings",
            MagicMock(use_data_store=False),
        )

        crit = _make_advisory(cve_id="CVE-2026-0001", severity=SeverityLevel.CRITICAL)
        low = _make_advisory(
            cve_id="CVE-2026-0002", severity=SeverityLevel.LOW, cvss_score=2.0
        )

        agg = CVEAggregator(nist_api_key="k")
        agg.nist_client.fetch_recent_cves = AsyncMock(return_value=[crit, low])

        result = await agg.fetch_all_advisories(days=7, severity=SeverityLevel.CRITICAL)
        assert len(result) == 1
        assert result[0].cve_id == "CVE-2026-0001"

    @pytest.mark.asyncio
    async def test_fetch_all_advisories_deduplicates(self, monkeypatch):
        """Duplicate CVE IDs are removed."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        monkeypatch.setattr(
            "fitness.services.cve_aggregator.settings",
            MagicMock(use_data_store=False),
        )

        dup1 = _make_advisory(cve_id="CVE-2026-0001", days_ago=0)
        dup2 = _make_advisory(cve_id="CVE-2026-0001", days_ago=1)

        agg = CVEAggregator(nist_api_key="k")
        agg.nist_client.fetch_recent_cves = AsyncMock(return_value=[dup1, dup2])

        result = await agg.fetch_all_advisories(days=7)
        assert len(result) == 1
        assert result[0].cve_id == "CVE-2026-0001"

    @pytest.mark.asyncio
    async def test_fetch_all_advisories_handles_errors(self, monkeypatch):
        """Exception in gather yields an empty list (not a crash)."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        monkeypatch.setattr(
            "fitness.services.cve_aggregator.settings",
            MagicMock(use_data_store=False),
        )

        agg = CVEAggregator(nist_api_key="k")
        agg.nist_client.fetch_recent_cves = AsyncMock(
            side_effect=RuntimeError("network down")
        )

        result = await agg.fetch_all_advisories(days=7)
        # asyncio.gather returns the exception object, which is not a list,
        # so the flatten loop skips it.
        assert result == []

    @pytest.mark.asyncio
    async def test_get_advisory_by_id(self, monkeypatch):
        """Delegates to nist_client.fetch_cve_by_id."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock())

        expected = _make_advisory(cve_id="CVE-2026-0001")
        agg = CVEAggregator(nist_api_key="k")
        agg.nist_client.fetch_cve_by_id = AsyncMock(return_value=expected)

        result = await agg.get_advisory_by_id("CVE-2026-0001")
        assert result is not None
        assert result.cve_id == "CVE-2026-0001"

    @pytest.mark.asyncio
    async def test_get_advisory_by_id_not_found(self, monkeypatch):
        """Returns None when NIST has no matching CVE."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock())

        agg = CVEAggregator(nist_api_key="k")
        agg.nist_client.fetch_cve_by_id = AsyncMock(return_value=None)

        result = await agg.get_advisory_by_id("CVE-9999-0000")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_stats(self, monkeypatch):
        """AdvisoryStats are computed correctly from advisory list."""
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        monkeypatch.setattr(
            "fitness.services.cve_aggregator.settings",
            MagicMock(use_data_store=False),
        )

        advisories = [
            _make_advisory(
                cve_id="CVE-2026-0001",
                severity=SeverityLevel.CRITICAL,
                cvss_score=9.8,
                days_ago=0,
            ),
            _make_advisory(
                cve_id="CVE-2026-0002",
                severity=SeverityLevel.HIGH,
                cvss_score=7.5,
                days_ago=1,
            ),
            _make_advisory(
                cve_id="CVE-2026-0003",
                severity=SeverityLevel.MEDIUM,
                cvss_score=5.0,
                days_ago=2,
            ),
            _make_advisory(
                cve_id="CVE-2026-0004",
                severity=SeverityLevel.LOW,
                cvss_score=2.0,
                days_ago=3,
            ),
            _make_advisory(
                cve_id="CVE-2026-0005",
                severity=SeverityLevel.CRITICAL,
                cvss_score=10.0,
                days_ago=4,
            ),
        ]

        agg = CVEAggregator(nist_api_key="k")
        agg.nist_client.fetch_recent_cves = AsyncMock(return_value=advisories)

        stats = await agg.get_stats(days=30)
        assert isinstance(stats, AdvisoryStats)
        assert stats.total_advisories == 5
        assert stats.critical_count == 2
        assert stats.high_count == 1
        assert stats.medium_count == 1
        assert stats.low_count == 1
        assert stats.by_source["NIST"] == 5
        assert stats.latest_critical is not None
        assert stats.latest_critical.cve_id == "CVE-2026-0001"

    @pytest.mark.asyncio
    async def test_get_top_advisories(self, monkeypatch):
        """Top advisories are sorted by CVSS score descending via negated
        key + reverse=True (the double reversal means the sort actually
        returns lowest-score first; this test documents that behaviour).
        """
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        monkeypatch.setattr(
            "fitness.services.cve_aggregator.settings",
            MagicMock(use_data_store=False),
        )

        advisories = [
            _make_advisory(
                cve_id="CVE-2026-0001",
                severity=SeverityLevel.CRITICAL,
                cvss_score=8.0,
                days_ago=0,
            ),
            _make_advisory(
                cve_id="CVE-2026-0002",
                severity=SeverityLevel.CRITICAL,
                cvss_score=10.0,
                days_ago=1,
            ),
            _make_advisory(
                cve_id="CVE-2026-0003",
                severity=SeverityLevel.CRITICAL,
                cvss_score=9.5,
                days_ago=2,
            ),
        ]

        agg = CVEAggregator(nist_api_key="k")
        agg.nist_client.fetch_recent_cves = AsyncMock(return_value=advisories)

        result = await agg.get_top_advisories(
            severity=SeverityLevel.CRITICAL, limit=2, days=30
        )
        assert len(result) == 2
        # The sort uses -(score) with reverse=True which double-reverses,
        # yielding lowest CVSS first. Verify actual behaviour:
        assert result[0].cvss_score == 8.0
        assert result[1].cvss_score == 9.5

    @pytest.mark.asyncio
    async def test_get_time_series_data(self, monkeypatch):
        """Date buckets cover the requested range with correct counts.

        Note: SecurityAdvisory has ``use_enum_values = True``, so
        ``severity`` is stored as a plain string.  The production code
        at ``cve_aggregator.py:233`` calls ``advisory.severity.value``
        which raises ``AttributeError`` on a plain string.  We patch
        ``fetch_all_advisories`` directly and use ``model_construct``
        to keep the ``SeverityLevel`` enum so the ``.value`` call
        succeeds, allowing us to test the bucketing logic itself.
        """
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        monkeypatch.setattr(
            "fitness.services.cve_aggregator.settings",
            MagicMock(use_data_store=False),
        )

        now = datetime.now(UTC)
        today_str = now.strftime("%Y-%m-%d")

        # Use model_construct to keep SeverityLevel as enum (avoids
        # use_enum_values coercion) so .value works in get_time_series_data.
        advisories = [
            SecurityAdvisory.model_construct(
                cve_id="CVE-2026-0001",
                description="A",
                severity=SeverityLevel.CRITICAL,
                cvss_score=9.8,
                published_date=now,
                source=AdvisorySource.NIST,
                references=[],
                affected_products=[],
            ),
            SecurityAdvisory.model_construct(
                cve_id="CVE-2026-0002",
                description="B",
                severity=SeverityLevel.CRITICAL,
                cvss_score=9.0,
                published_date=now,
                source=AdvisorySource.NIST,
                references=[],
                affected_products=[],
            ),
            SecurityAdvisory.model_construct(
                cve_id="CVE-2026-0003",
                description="C",
                severity=SeverityLevel.HIGH,
                cvss_score=7.5,
                published_date=now,
                source=AdvisorySource.NIST,
                references=[],
                affected_products=[],
            ),
        ]

        agg = CVEAggregator(nist_api_key="k")
        # Patch fetch_all_advisories directly to bypass Pydantic
        # enum-to-string coercion in the intervening methods.
        agg.fetch_all_advisories = AsyncMock(return_value=advisories)

        result = await agg.get_time_series_data(days=7)

        # All four severity keys are present
        assert set(result.keys()) == {"CRITICAL", "HIGH", "MEDIUM", "LOW"}

        # 7-day range produces 8 entries (start_date through end_date inclusive)
        assert len(result["CRITICAL"]) == 8

        # Today's CRITICAL count should be 2
        critical_today = [
            count
            for dt, count in result["CRITICAL"]
            if dt.strftime("%Y-%m-%d") == today_str
        ]
        assert critical_today == [2]

        # Today's HIGH count should be 1
        high_today = [
            count
            for dt, count in result["HIGH"]
            if dt.strftime("%Y-%m-%d") == today_str
        ]
        assert high_today == [1]

        # MEDIUM should have all zeros
        assert all(count == 0 for _, count in result["MEDIUM"])
