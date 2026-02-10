"""Captain's Log — TNG-styled project status entries."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from fitness.services.cve_aggregator import CVEAggregator

logger = logging.getLogger(__name__)


def compute_stardate() -> str:
    """Compute a TNG-style stardate from the current UTC time.

    TNG stardates loosely map: year 2323 = 0, each year ~ +1000.
    We anchor 2024-01-01 = 101000.0 and scale linearly within each year.
    """
    now = datetime.now(UTC)
    year_start = datetime(now.year, 1, 1, tzinfo=UTC)
    year_end = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    year_fraction = (now - year_start).total_seconds() / (
        year_end - year_start
    ).total_seconds()
    base = 101000.0 + (now.year - 2024) * 1000
    stardate = base + year_fraction * 1000
    return f"{stardate:.1f}"


class CaptainsLogService:
    """Captain's Log service — AI generation deprecated, telemetry only."""

    async def collect_telemetry(
        self,
        db: Session,
        aggregator: CVEAggregator | None = None,
    ) -> dict:
        """Gather project telemetry.

        Returns dict with cve_stats, cert_count, stardate, and timestamp.
        """
        from fitness.models.blog import BlogEntry
        from fitness.models.certification import Certification

        cert_count = db.query(Certification).count()
        entry_count = db.query(BlogEntry).count()

        cve_summary = "CVE data unavailable"
        if aggregator:
            try:
                stats = await aggregator.get_stats(days=7)
                cve_summary = (
                    f"{stats.total_advisories} advisories in 7d "
                    f"(critical={stats.critical_count}, high={stats.high_count})"
                )
            except Exception:
                logger.debug("Could not fetch CVE stats for telemetry")

        return {
            "stardate": compute_stardate(),
            "timestamp": datetime.now(UTC).isoformat(),
            "cert_count": cert_count,
            "log_entry_count": entry_count,
            "cve_summary": cve_summary,
        }


captains_log_service = CaptainsLogService()
