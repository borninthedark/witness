"""Captain's Log — AI-generated TNG-voiced project status entries."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fitness.config import settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from fitness.services.cve_aggregator import CVEAggregator

logger = logging.getLogger(__name__)

PICARD_SYSTEM_PROMPT = """\
You are Captain Jean-Luc Picard recording a Captain's Log entry aboard the \
USS Enterprise. You speak with Picard's measured, thoughtful cadence — \
philosophical yet precise. You are reporting on the status of a software \
project (a personal portfolio & certification platform) as if it were a \
starship mission.

Rules:
- Write in first person as Picard
- Use TNG metaphors naturally (don't force them)
- Keep the tone dignified and reflective
- The entry should feel like a real Captain's Log: situation, reflection, \
  next steps
- Output valid JSON with keys: title, summary, content, tags
- "title" should be short (under 100 chars), like a log entry subject
- "summary" is 1-2 sentences (under 300 chars)
- "content" is the full markdown log entry (3-5 paragraphs)
- "tags" is a list of 2-5 relevant keyword strings
"""


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
    """Generate AI-powered Captain's Log entries from project telemetry."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        """Lazy-init the Anthropic client."""
        if self._client is None:
            if not settings.anthropic_api_key:
                return None
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def collect_telemetry(
        self,
        db: Session,
        aggregator: CVEAggregator | None = None,
    ) -> dict:
        """Gather project telemetry for the AI prompt.

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

    async def generate_entry(self, telemetry: dict) -> dict:
        """Call Claude Haiku to produce a Captain's Log entry.

        Returns dict with keys: title, summary, content, stardate, tags.
        Returns None if the API key is unset or the call fails.
        """
        client = self._get_client()
        if client is None:
            logger.warning("Anthropic API key not set — skipping log generation")
            return None

        user_prompt = (
            f"Stardate {telemetry['stardate']}. "
            f"Project telemetry:\n"
            f"- Certifications on file: {telemetry['cert_count']}\n"
            f"- Existing log entries: {telemetry['log_entry_count']}\n"
            f"- Security status: {telemetry['cve_summary']}\n"
            f"- Timestamp: {telemetry['timestamp']}\n\n"
            "Generate a Captain's Log entry based on this telemetry. "
            "Respond with ONLY valid JSON."
        )

        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=PICARD_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text
            data = json.loads(raw)
            data["stardate"] = telemetry["stardate"]
            return data
        except Exception:
            logger.exception("Failed to generate Captain's Log entry")
            return None


captains_log_service = CaptainsLogService()
