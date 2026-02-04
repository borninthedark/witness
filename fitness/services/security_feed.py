"""Client helpers for retrieving external security advisories."""

from __future__ import annotations

import html
import os
import textwrap
from pathlib import Path
from typing import Final

import httpx
from defusedxml import ElementTree as ET  # noqa: S410

GENTOO_FEED = "https://security.gentoo.org/glsa/feed.rss"

try:
    GENTOO_TIMEOUT: Final[float] = float(os.getenv("GENTOO_FEED_TIMEOUT", "5"))
except ValueError:  # pragma: no cover - defensive parsing
    GENTOO_TIMEOUT = 5.0


def _load_fallback_feed() -> str | None:
    """Load a local RSS snapshot, used during tests/offline runs."""
    fallback_path = os.getenv("GENTOO_FEED_FALLBACK")
    if not fallback_path:
        return None
    path = Path(fallback_path)
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


async def fetch_gentoo_advisories(limit: int = 8) -> list[dict[str, str]]:
    """Fetch the Gentoo Linux Security Advisory feed."""
    feed_text: str | None = None
    disable_http = os.getenv("GENTOO_FEED_DISABLE_HTTP") == "1"

    if not disable_http:
        try:
            async with httpx.AsyncClient(timeout=GENTOO_TIMEOUT) as client:
                response = await client.get(GENTOO_FEED)
                response.raise_for_status()
                feed_text = response.text
        except httpx.HTTPError:
            feed_text = _load_fallback_feed()
    else:
        feed_text = _load_fallback_feed()

    if not feed_text:
        return []

    items: list[dict[str, str]] = []
    try:
        root = ET.fromstring(feed_text)
    except ET.ParseError:
        return []

    max_items = max(limit, 0)
    for item in root.findall(".//item")[:max_items]:
        title = item.findtext("title", default="Advisory")
        link = item.findtext("link", default=GENTOO_FEED)
        pub_date = item.findtext("pubDate", default="")
        description = html.unescape(item.findtext("description", default="")).strip()
        summary = textwrap.shorten(description, width=220, placeholder="…")
        items.append(
            {
                "title": title,
                "link": link,
                "published": pub_date,
                "summary": summary,
            }
        )
    return items
