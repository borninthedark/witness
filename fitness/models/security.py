"""Pydantic models for security advisories."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    """CVE severity levels based on CVSS scoring."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class AdvisorySource(str, Enum):
    """Security advisory data sources."""

    NIST = "NIST"
    CVE = "CVE"


class SecurityAdvisory(BaseModel):
    """Security advisory with CVE details."""

    cve_id: str
    title: str | None = None
    description: str
    severity: SeverityLevel
    cvss_score: float | None = None
    cvss_vector: str | None = None
    published_date: datetime
    modified_date: datetime | None = None
    source: AdvisorySource
    references: list[str] = Field(default_factory=list)
    affected_products: list[str] = Field(default_factory=list)

    class Config:
        """Pydantic config."""

        use_enum_values = True


class AdvisoryStats(BaseModel):
    """Statistics about security advisories."""

    total_advisories: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    by_source: dict[str, int]
    latest_critical: SecurityAdvisory | None = None
