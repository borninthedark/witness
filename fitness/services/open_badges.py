from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

import httpx


class OpenBadgesError(RuntimeError):
    """Raised when the supplied URL cannot be validated as an Open Badges assertion."""


@dataclass(slots=True)
class BadgePreview:
    assertion_id: str
    badge_name: str
    badge_description: str | None
    issuer_name: str | None
    issuer_url: str | None
    issued_on: str | None
    evidence: list[str]
    raw_assertion: dict[str, Any]

    @property
    def suggestions(self) -> dict[str, str]:
        slug_base = _slugify(self.badge_name or "badge")
        digest = hashlib.sha256(self.assertion_id.encode("utf-8")).hexdigest()[:8]
        slug = f"{slug_base}-{digest}"
        return {
            "slug": slug,
            "title": self.badge_name or "",
            "issuer": self.issuer_name or "",
        }


async def fetch_open_badges_assertion(url: str) -> BadgePreview:
    """Fetches an Open Badges assertion payload and resolves related resources."""
    if not url:
        raise OpenBadgesError("An assertion URL is required.")

    assertion = await _fetch_json(url)
    if not _looks_like_assertion(assertion):
        raise OpenBadgesError(
            "The provided URL does not appear to be an Open Badges assertion."
        )

    badge = await _maybe_follow(assertion, "badge")
    if not isinstance(badge, dict):
        raise OpenBadgesError("Unable to resolve badge metadata for this assertion.")

    issuer = await _maybe_follow(badge, "issuer")
    if isinstance(issuer, str):
        issuer_data: dict[str, Any] | None = {"name": issuer}
    else:
        issuer_data = issuer if isinstance(issuer, dict) else None

    evidence = assertion.get("evidence")
    if isinstance(evidence, list):
        # typing note: evidence entries can be dicts or strings
        evidence_urls = [
            str(item.get("id", item)) for item in evidence  # type: ignore[assignment]
        ]
    elif isinstance(evidence, str):
        evidence_urls = [evidence]
    else:
        evidence_urls = []

    return BadgePreview(
        assertion_id=str(assertion.get("id") or url),
        badge_name=str(badge.get("name") or badge.get("title") or ""),
        badge_description=str(badge.get("description") or ""),
        issuer_name=str((issuer_data or {}).get("name") or ""),
        issuer_url=str((issuer_data or {}).get("url") or ""),
        issued_on=str(assertion.get("issuedOn") or assertion.get("issuedon") or ""),
        evidence=evidence_urls,
        raw_assertion=assertion,
    )


async def _fetch_json(url: str) -> dict[str, Any]:
    headers = {"Accept": "application/ld+json, application/json;q=0.9"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise OpenBadgesError(
            f"Remote endpoint returned {exc.response.status_code}."
        ) from exc
    except httpx.HTTPError as exc:
        raise OpenBadgesError("Unable to reach the assertion endpoint.") from exc

    data = response.json()
    if not isinstance(data, dict):
        raise OpenBadgesError("Unexpected payload received from assertion endpoint.")
    return data


async def _maybe_follow(payload: dict[str, Any], key: str) -> Any:
    value = payload.get(key)
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.startswith("http"):
        return await _fetch_json(value)
    return value


def _looks_like_assertion(payload: dict[str, Any]) -> bool:
    type_val = payload.get("type")
    if isinstance(type_val, list):
        types = [t.lower() for t in type_val]
    elif isinstance(type_val, str):
        types = [type_val.lower()]
    else:
        types = []
    return any("assertion" in t for t in types)


_slugify_pattern = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    slug = _slugify_pattern.sub("-", value.lower()).strip("-")
    return slug or "badge"
