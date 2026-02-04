"""Enhanced Gentoo Linux Security Advisory parser."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import httpx
from defusedxml import ElementTree as ET

from fitness.models.security import AdvisorySource, SecurityAdvisory, SeverityLevel


class GLSAParser:
    """Parser for Gentoo Linux Security Advisories."""

    GLSA_RSS_URL = "https://security.gentoo.org/glsa/feed.rss"
    GLSA_BASE_URL = "https://security.gentoo.org/glsa"

    def __init__(self):
        """Initialize GLSA parser."""
        self.client = httpx.AsyncClient(timeout=30.0)

    async def fetch_recent_glsa(self, days: int = 30) -> list[SecurityAdvisory]:
        """Fetch recent GLSA advisories from RSS feed.

        Args:
            days: Number of days to look back

        Returns:
            List of SecurityAdvisory objects
        """
        try:
            response = await self.client.get(self.GLSA_RSS_URL)
            response.raise_for_status()

            root = ET.fromstring(response.content)

            advisories = []
            from datetime import timezone

            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Parse RSS items
            for item in root.findall(".//item"):
                advisory = self._parse_rss_item(item)

                if advisory and advisory.published_date >= cutoff_date:
                    advisories.append(advisory)

            return advisories

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Error fetching GLSA data from {self.GLSA_RSS_URL}: {e}", exc_info=True
            )
            return []

    def _parse_rss_item(self, item) -> SecurityAdvisory | None:
        """Parse a single RSS item into SecurityAdvisory.

        Args:
            item: XML element for RSS item

        Returns:
            SecurityAdvisory object or None if parsing fails
        """
        try:
            # Extract title (e.g., "GLSA 202311-01: Apache: Multiple Vulnerabilities")
            title = item.findtext("title") or ""

            # Extract GLSA ID from title
            glsa_id = ""
            if "GLSA" in title:
                parts = title.split(":")
                if parts:
                    glsa_id = parts[0].strip()

            # Extract description
            description = item.findtext("description") or title

            # Extract publication date
            pub_date_str = item.findtext("pubDate")
            if not pub_date_str:
                return None

            published_date = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")

            # Extract link
            link = item.findtext("link") or ""
            references = [link] if link else []

            # Extract CVE IDs from description if present
            cve_ids = self._extract_cve_ids(description)

            # Determine severity (estimate from title/description)
            severity = self._estimate_severity(title, description)

            # Extract affected packages from title
            affected_products = []
            if ":" in title:
                package_info = title.split(":")[1].strip()
                affected_products.append(package_info)

            # Use GLSA ID as CVE ID if no CVEs found, otherwise use first CVE
            cve_id = cve_ids[0] if cve_ids else glsa_id

            advisory = SecurityAdvisory(
                cve_id=cve_id,
                title=title,
                description=description[:500],  # Truncate long descriptions
                severity=severity,
                published_date=published_date,
                source=AdvisorySource.GLSA,
                references=references,
                affected_products=affected_products,
            )

            return advisory

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Error parsing GLSA item: {e}")
            return None

    def _extract_cve_ids(self, text: str) -> list[str]:
        """Extract CVE IDs from text.

        Args:
            text: Text to search for CVE IDs

        Returns:
            List of CVE IDs found
        """
        cve_pattern = r"CVE-\d{4}-\d{4,7}"
        return re.findall(cve_pattern, text)

    def _estimate_severity(self, title: str, description: str) -> SeverityLevel:
        """Estimate severity from text (GLSA doesn't provide CVSS).

        Args:
            title: Advisory title
            description: Advisory description

        Returns:
            Estimated SeverityLevel
        """
        text = (title + " " + description).lower()

        critical_keywords = [
            "remote code execution",
            "rce",
            "critical",
            "arbitrary code",
        ]
        high_keywords = ["privilege escalation", "authentication bypass", "injection"]
        medium_keywords = ["denial of service", "dos", "information disclosure"]

        for keyword in critical_keywords:
            if keyword in text:
                return SeverityLevel.CRITICAL

        for keyword in high_keywords:
            if keyword in text:
                return SeverityLevel.HIGH

        for keyword in medium_keywords:
            if keyword in text:
                return SeverityLevel.MEDIUM

        return SeverityLevel.UNKNOWN

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
