"""Aggregate security advisories from multiple sources."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fitness.models.security import (
    AdvisorySource,
    AdvisoryStats,
    SecurityAdvisory,
    SeverityLevel,
)
from fitness.services.nist_client import NISTClient


class CVEAggregator:
    """Aggregate security advisories from multiple sources."""

    def __init__(self, nist_api_key: str | None = None):
        """Initialize CVE aggregator.

        Args:
            nist_api_key: NIST NVD API key (optional)
        """
        self.nist_client = NISTClient(api_key=nist_api_key)

    async def fetch_all_advisories(
        self,
        days: int = 30,
        severity: SeverityLevel | None = None,
        source: AdvisorySource | None = None,
    ) -> list[SecurityAdvisory]:
        """Fetch advisories from all sources.

        Args:
            days: Number of days to look back
            severity: Filter by severity level (optional)
            source: Filter by source (optional)

        Returns:
            List of SecurityAdvisory objects
        """
        tasks = []

        # Fetch from NIST only
        if source is None or source == AdvisorySource.NIST:
            tasks.append(self.nist_client.fetch_recent_cves(days, severity))

        # Execute all fetches concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results and filter out errors
        all_advisories = []
        for result in results:
            if isinstance(result, list):
                all_advisories.extend(result)

        # Filter by severity if specified
        if severity:
            all_advisories = [a for a in all_advisories if a.severity == severity]

        # Sort by published date (newest first)
        all_advisories.sort(key=lambda x: x.published_date, reverse=True)

        # Remove duplicates based on CVE ID
        seen_cves = set()
        unique_advisories = []
        for advisory in all_advisories:
            if advisory.cve_id not in seen_cves:
                seen_cves.add(advisory.cve_id)
                unique_advisories.append(advisory)

        return unique_advisories

    async def get_advisory_by_id(self, cve_id: str) -> SecurityAdvisory | None:
        """Get a specific advisory by CVE ID.

        Args:
            cve_id: CVE identifier (e.g., CVE-2024-1234)

        Returns:
            SecurityAdvisory object or None if not found
        """
        # Try NIST first
        advisory = await self.nist_client.fetch_cve_by_id(cve_id)

        if advisory:
            return advisory

        return None

    async def get_stats(self, days: int = 30) -> AdvisoryStats:
        """Get statistics about recent advisories.

        Args:
            days: Number of days to look back

        Returns:
            AdvisoryStats object with aggregated statistics
        """
        advisories = await self.fetch_all_advisories(days=days)

        stats = AdvisoryStats(
            total_advisories=len(advisories),
            critical_count=sum(
                1 for a in advisories if a.severity == SeverityLevel.CRITICAL
            ),
            high_count=sum(1 for a in advisories if a.severity == SeverityLevel.HIGH),
            medium_count=sum(
                1 for a in advisories if a.severity == SeverityLevel.MEDIUM
            ),
            low_count=sum(1 for a in advisories if a.severity == SeverityLevel.LOW),
            by_source={
                "NIST": sum(1 for a in advisories if a.source == AdvisorySource.NIST),
            },
            latest_critical=next(
                (a for a in advisories if a.severity == SeverityLevel.CRITICAL),
                None,
            ),
        )

        return stats

    async def get_top_advisories(
        self,
        severity: SeverityLevel,
        limit: int = 5,
        days: int = 30,
    ) -> list[SecurityAdvisory]:
        """Get top N most recent advisories for a specific severity level.

        Args:
            severity: The severity level to filter by
            limit: Maximum number of advisories to return
            days: Number of days to look back

        Returns:
            List of SecurityAdvisory objects, sorted by date (newest first)
        """
        # Fetch all advisories for this severity
        advisories = await self.fetch_all_advisories(days=days, severity=severity)

        # Sort by CVSS score (highest first), then by date (newest first)
        advisories.sort(
            key=lambda x: (-(x.cvss_score if x.cvss_score else 0), x.published_date),
            reverse=True,
        )

        # Return top N
        return advisories[:limit]

    async def get_time_series_data(
        self, days: int = 30
    ) -> dict[str, list[tuple[datetime, int]]]:
        """Get time-series data for charting CVE trends.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary mapping severity levels to list of (date, count) tuples
        """
        advisories = await self.fetch_all_advisories(days=days)

        # Group advisories by date and severity
        data_by_severity: dict[str, dict[str, int]] = {
            "CRITICAL": defaultdict(int),
            "HIGH": defaultdict(int),
            "MEDIUM": defaultdict(int),
            "LOW": defaultdict(int),
        }

        for advisory in advisories:
            date_key = advisory.published_date.strftime("%Y-%m-%d")
            severity_key = advisory.severity.value
            if severity_key in data_by_severity:
                data_by_severity[severity_key][date_key] += 1

        # Convert to sorted list of (datetime, count) tuples
        result: dict[str, list[tuple[datetime, int]]] = {}

        for severity, date_counts in data_by_severity.items():
            # Create a complete date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)

            # Fill in all dates (including zeros)
            date_series = []
            current_date = start_date

            while current_date <= end_date:
                date_key = current_date.strftime("%Y-%m-%d")
                count = date_counts.get(date_key, 0)
                date_series.append((current_date, count))
                current_date += timedelta(days=1)

            result[severity] = date_series

        return result

    async def close(self):
        """Close all HTTP clients."""
        await self.nist_client.close()
