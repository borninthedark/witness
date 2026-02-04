"""NIST National Vulnerability Database API client."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta

import httpx

from fitness.models.security import AdvisorySource, SecurityAdvisory, SeverityLevel


class NISTClient:
    """Client for NIST National Vulnerability Database API 2.0."""

    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    RATE_LIMIT_DELAY = 0.6  # 6 seconds per 10 requests without API key

    def __init__(self, api_key: str | None = None):
        """Initialize NIST client.

        Args:
            api_key: NIST NVD API key (optional, increases rate limits)
        """
        self.api_key = api_key or os.getenv("NIST_API_KEY")
        self.rate_limit_delay = 0.6 if not self.api_key else 0.02  # 50/30s with key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def fetch_recent_cves(
        self,
        days: int = 30,
        severity: SeverityLevel | None = None,
        results_per_page: int = 100,
    ) -> list[SecurityAdvisory]:
        """Fetch CVEs published in the last N days.

        Args:
            days: Number of days to look back
            severity: Filter by severity level (optional)
            results_per_page: Number of results per page (max 2000)

        Returns:
            List of SecurityAdvisory objects
        """
        from datetime import timezone

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        params = {
            "pubStartDate": start_date.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "pubEndDate": end_date.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "resultsPerPage": min(results_per_page, 2000),
        }

        headers = {}
        if self.api_key:
            headers["apiKey"] = self.api_key

        try:
            # Rate limiting
            await asyncio.sleep(self.rate_limit_delay)

            response = await self.client.get(
                self.BASE_URL, params=params, headers=headers
            )
            response.raise_for_status()

            data = response.json()
            advisories = self._parse_nist_response(data)

            # Filter by severity if specified
            if severity:
                advisories = [a for a in advisories if a.severity == severity]

            return advisories

        except httpx.HTTPError as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error fetching NIST data: {e}", exc_info=True)
            return []

    async def fetch_cve_by_id(self, cve_id: str) -> SecurityAdvisory | None:
        """Fetch a specific CVE by ID.

        Args:
            cve_id: CVE identifier (e.g., CVE-2024-1234)

        Returns:
            SecurityAdvisory object or None if not found
        """
        params = {"cveId": cve_id}

        headers = {}
        if self.api_key:
            headers["apiKey"] = self.api_key

        try:
            await asyncio.sleep(self.rate_limit_delay)

            response = await self.client.get(
                self.BASE_URL, params=params, headers=headers
            )
            response.raise_for_status()

            data = response.json()
            advisories = self._parse_nist_response(data)

            return advisories[0] if advisories else None

        except httpx.HTTPError as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error fetching CVE {cve_id}: {e}", exc_info=True)
            return None

    def _parse_nist_response(self, data: dict) -> list[SecurityAdvisory]:  # noqa: C901
        """Parse NIST API response into SecurityAdvisory objects.

        Args:
            data: JSON response from NIST API

        Returns:
            List of SecurityAdvisory objects
        """
        advisories = []

        for vuln in data.get("vulnerabilities", []):
            cve = vuln.get("cve", {})

            # Extract CVE ID
            cve_id = cve.get("id", "")

            # Extract description
            descriptions = cve.get("descriptions", [])
            description = ""
            for desc in descriptions:
                if desc.get("lang") == "en":
                    description = desc.get("value", "")
                    break

            # Extract CVSS metrics (prefer v3.1, fallback to v3.0, v2.0)
            metrics = cve.get("metrics", {})
            cvss_data = None
            cvss_score = None
            cvss_severity = SeverityLevel.UNKNOWN
            cvss_vector = None

            if "cvssMetricV31" in metrics and metrics["cvssMetricV31"]:
                cvss_data = metrics["cvssMetricV31"][0].get("cvssData", {})
            elif "cvssMetricV30" in metrics and metrics["cvssMetricV30"]:
                cvss_data = metrics["cvssMetricV30"][0].get("cvssData", {})
            elif "cvssMetricV2" in metrics and metrics["cvssMetricV2"]:
                cvss_data = metrics["cvssMetricV2"][0].get("cvssData", {})

            if cvss_data:
                cvss_score = cvss_data.get("baseScore")
                severity_str = cvss_data.get("baseSeverity", "UNKNOWN").upper()
                cvss_vector = cvss_data.get("vectorString", "")

                try:
                    cvss_severity = SeverityLevel(severity_str)
                except ValueError:
                    cvss_severity = SeverityLevel.UNKNOWN

            # Extract references
            references = []
            for ref in cve.get("references", []):
                url = ref.get("url")
                if url:
                    references.append(url)

            # Extract affected products (CPE configurations)
            affected_products = []
            configurations = cve.get("configurations", [])
            for config in configurations:
                for node in config.get("nodes", []):
                    for cpe_match in node.get("cpeMatch", []):
                        criteria = cpe_match.get("criteria", "")
                        if criteria:
                            # Parse CPE string to get product name
                            parts = criteria.split(":")
                            if len(parts) >= 5:
                                vendor = parts[3]
                                product = parts[4]
                                affected_products.append(f"{vendor}:{product}")

            # Remove duplicates
            affected_products = list(set(affected_products))

            # Extract dates
            published_date = datetime.fromisoformat(
                cve.get("published", "").replace("Z", "+00:00")
            )

            modified_str = cve.get("lastModified")
            modified_date = None
            if modified_str:
                modified_date = datetime.fromisoformat(
                    modified_str.replace("Z", "+00:00")
                )

            advisory = SecurityAdvisory(
                cve_id=cve_id,
                description=description,
                severity=cvss_severity,
                cvss_score=cvss_score,
                cvss_vector=cvss_vector,
                published_date=published_date,
                modified_date=modified_date,
                source=AdvisorySource.NIST,
                references=references[:10],  # Limit to 10 references
                affected_products=affected_products[:20],  # Limit to 20 products
            )

            advisories.append(advisory)

        return advisories

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
