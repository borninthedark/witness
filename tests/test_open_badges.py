"""Tests for the Open Badges assertion fetcher and SSRF-safe URL validation."""

from __future__ import annotations

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fitness.services.open_badges import (
    BadgePreview,
    OpenBadgesError,
    _fetch_json,
    _looks_like_assertion,
    _maybe_follow,
    _slugify,
    _validate_url_safe,
    fetch_open_badges_assertion,
)

# ── _validate_url_safe ───────────────────────────────────────────


class TestValidateUrlSafe:
    """SSRF-safe URL validation rejects private IPs and non-HTTPS."""

    def test_rejects_http(self):
        """Non-HTTPS scheme raises OpenBadgesError."""
        with pytest.raises(OpenBadgesError, match="Only HTTPS"):
            _validate_url_safe("http://example.com/badge.json")

    def test_rejects_no_hostname(self):
        """URL with no hostname raises OpenBadgesError."""
        with pytest.raises(OpenBadgesError, match="Invalid assertion URL"):
            _validate_url_safe("https:///path-only")

    @patch("fitness.services.open_badges.socket.getaddrinfo")
    def test_rejects_private_ip(self, mock_getaddrinfo):
        """Private IP in DNS resolution raises OpenBadgesError."""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
        ]
        with pytest.raises(OpenBadgesError, match="private address"):
            _validate_url_safe("https://evil.internal/badge.json")

    @patch("fitness.services.open_badges.socket.getaddrinfo")
    def test_rejects_dns_failure(self, mock_getaddrinfo):
        """DNS resolution failure raises OpenBadgesError."""
        mock_getaddrinfo.side_effect = socket.gaierror("Name or service not known")
        with pytest.raises(OpenBadgesError, match="Cannot resolve hostname"):
            _validate_url_safe("https://nonexistent.example/badge.json")

    @patch("fitness.services.open_badges.socket.getaddrinfo")
    def test_accepts_public_url(self, mock_getaddrinfo):
        """Public IP passes validation without error."""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
        ]
        _validate_url_safe("https://example.com/badge.json")


# ── BadgePreview.suggestions ─────────────────────────────────────


class TestBadgePreview:
    """BadgePreview.suggestions produces slug with hash prefix."""

    def test_suggestions_generates_slug(self):
        """Slug is derived from badge_name plus sha256 prefix."""
        preview = BadgePreview(
            assertion_id="https://example.com/assertions/123",
            badge_name="Cloud Practitioner",
            badge_description="AWS Cloud",
            issuer_name="AWS",
            issuer_url="https://aws.amazon.com",
            issued_on="2026-01-15",
            evidence=[],
            raw_assertion={},
        )
        suggestions = preview.suggestions
        assert suggestions["slug"].startswith("cloud-practitioner-")
        assert len(suggestions["slug"].split("-")[-1]) == 8

    def test_suggestions_empty_name(self):
        """badge_name=None falls back to 'badge' in slug."""
        preview = BadgePreview(
            assertion_id="https://example.com/assertions/456",
            badge_name=None,
            badge_description=None,
            issuer_name=None,
            issuer_url=None,
            issued_on=None,
            evidence=[],
            raw_assertion={},
        )
        suggestions = preview.suggestions
        assert suggestions["slug"].startswith("badge-")


# ── _looks_like_assertion ────────────────────────────────────────


class TestLooksLikeAssertion:
    """Detects Open Badges assertion type from payload."""

    def test_assertion_type_list(self):
        """List containing 'Assertion' returns True."""
        assert _looks_like_assertion({"type": ["Assertion"]}) is True

    def test_assertion_type_string(self):
        """String 'Assertion' returns True."""
        assert _looks_like_assertion({"type": "Assertion"}) is True

    def test_not_assertion(self):
        """Non-assertion type returns False."""
        assert _looks_like_assertion({"type": "BadgeClass"}) is False

    def test_no_type(self):
        """Missing type key returns False."""
        assert _looks_like_assertion({}) is False


# ── _slugify ─────────────────────────────────────────────────────


class TestSlugify:
    """Converts human-readable badge names to URL slugs."""

    def test_basic(self):
        """Standard space-separated words become lowercase dashes."""
        assert _slugify("My Badge Name") == "my-badge-name"

    def test_empty(self):
        """Empty string falls back to 'badge'."""
        assert _slugify("") == "badge"

    def test_special_chars(self):
        """Non-alphanumeric characters are collapsed into dashes."""
        assert _slugify("C++ Expert!") == "c-expert"


# ── _fetch_json (async) ─────────────────────────────────────────


class TestFetchJson:
    """Async JSON fetcher with proper error mapping."""

    @pytest.mark.asyncio
    async def test_success(self):
        """Valid JSON dict response is returned."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "type": "Assertion",
            "id": "https://ex.com/1",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "fitness.services.open_badges.httpx.AsyncClient", return_value=mock_client
        ):
            result = await _fetch_json("https://example.com/assertion.json")

        assert result == {"type": "Assertion", "id": "https://ex.com/1"}

    @pytest.mark.asyncio
    async def test_http_status_error(self):
        """HTTP 404 raises OpenBadgesError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "fitness.services.open_badges.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(OpenBadgesError, match="returned 404"),
        ):
            await _fetch_json("https://example.com/missing.json")

    @pytest.mark.asyncio
    async def test_http_error(self):
        """Connection error raises OpenBadgesError."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "fitness.services.open_badges.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(OpenBadgesError, match="Unable to reach"),
        ):
            await _fetch_json("https://down.example.com/badge.json")

    @pytest.mark.asyncio
    async def test_non_dict_response(self):
        """Response returning a list raises OpenBadgesError."""
        mock_response = MagicMock()
        mock_response.json.return_value = [1, 2, 3]
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "fitness.services.open_badges.httpx.AsyncClient",
                return_value=mock_client,
            ),
            pytest.raises(OpenBadgesError, match="Unexpected payload"),
        ):
            await _fetch_json("https://example.com/list.json")


# ── _maybe_follow (async) ───────────────────────────────────────


class TestMaybeFollow:
    """Resolves inline dicts or follows URL strings."""

    @pytest.mark.asyncio
    async def test_dict_value(self):
        """Dict value is returned directly without fetching."""
        payload = {"badge": {"name": "Test Badge"}}
        result = await _maybe_follow(payload, "badge")
        assert result == {"name": "Test Badge"}

    @pytest.mark.asyncio
    @patch("fitness.services.open_badges._fetch_json", new_callable=AsyncMock)
    @patch("fitness.services.open_badges._validate_url_safe")
    async def test_string_url(self, mock_validate, mock_fetch):
        """String starting with http triggers a fetch."""
        mock_fetch.return_value = {"name": "Remote Badge"}
        payload = {"badge": "https://example.com/badge/42"}

        result = await _maybe_follow(payload, "badge")

        mock_validate.assert_called_once_with("https://example.com/badge/42")
        mock_fetch.assert_awaited_once_with("https://example.com/badge/42")
        assert result == {"name": "Remote Badge"}

    @pytest.mark.asyncio
    async def test_non_url_string(self):
        """Non-URL string is returned as-is."""
        payload = {"badge": "some-inline-value"}
        result = await _maybe_follow(payload, "badge")
        assert result == "some-inline-value"

    @pytest.mark.asyncio
    async def test_none_value(self):
        """Missing key returns None."""
        payload = {}
        result = await _maybe_follow(payload, "badge")
        assert result is None


# ── fetch_open_badges_assertion (async) ──────────────────────────


class TestFetchOpenBadgesAssertion:
    """End-to-end assertion fetch and BadgePreview assembly."""

    @pytest.mark.asyncio
    async def test_empty_url(self):
        """Empty URL raises OpenBadgesError."""
        with pytest.raises(OpenBadgesError, match="assertion URL is required"):
            await fetch_open_badges_assertion("")

    @pytest.mark.asyncio
    @patch("fitness.services.open_badges._validate_url_safe")
    @patch("fitness.services.open_badges._fetch_json", new_callable=AsyncMock)
    async def test_not_an_assertion(self, mock_fetch, mock_validate):
        """Non-assertion payload raises OpenBadgesError."""
        mock_fetch.return_value = {"type": "BadgeClass", "name": "Not Assertion"}

        with pytest.raises(OpenBadgesError, match="does not appear to be"):
            await fetch_open_badges_assertion("https://example.com/badge-class.json")

    @pytest.mark.asyncio
    @patch("fitness.services.open_badges._validate_url_safe")
    @patch("fitness.services.open_badges._fetch_json", new_callable=AsyncMock)
    async def test_success(self, mock_fetch, mock_validate):
        """Full assertion chain resolves into a BadgePreview with correct fields."""
        assertion = {
            "type": "Assertion",
            "id": "https://example.com/assertions/99",
            "badge": "https://example.com/badges/42",
            "issuedOn": "2026-01-15T00:00:00Z",
        }
        badge = {
            "name": "Cloud Practitioner",
            "description": "Foundational cloud skills",
            "issuer": "https://example.com/issuers/1",
        }
        issuer = {
            "name": "AWS Training",
            "url": "https://aws.amazon.com/training",
        }

        mock_fetch.side_effect = [assertion, badge, issuer]

        result = await fetch_open_badges_assertion("https://example.com/assertions/99")

        assert isinstance(result, BadgePreview)
        assert result.assertion_id == "https://example.com/assertions/99"
        assert result.badge_name == "Cloud Practitioner"
        assert result.badge_description == "Foundational cloud skills"
        assert result.issuer_name == "AWS Training"
        assert result.issuer_url == "https://aws.amazon.com/training"
        assert result.issued_on == "2026-01-15T00:00:00Z"
        assert result.evidence == []

    @pytest.mark.asyncio
    @patch("fitness.services.open_badges._validate_url_safe")
    @patch("fitness.services.open_badges._fetch_json", new_callable=AsyncMock)
    async def test_evidence_list(self, mock_fetch, mock_validate):
        """Evidence list entries are extracted into URL strings."""
        assertion = {
            "type": "Assertion",
            "id": "https://example.com/assertions/100",
            "badge": {"name": "Tester", "issuer": {"name": "Org"}},
            "evidence": [
                {"id": "https://example.com/evidence/1"},
                {"id": "https://example.com/evidence/2"},
            ],
        }
        mock_fetch.return_value = assertion

        result = await fetch_open_badges_assertion("https://example.com/assertions/100")

        assert result.evidence == [
            "https://example.com/evidence/1",
            "https://example.com/evidence/2",
        ]

    @pytest.mark.asyncio
    @patch("fitness.services.open_badges._validate_url_safe")
    @patch("fitness.services.open_badges._fetch_json", new_callable=AsyncMock)
    async def test_evidence_string(self, mock_fetch, mock_validate):
        """Single evidence string is wrapped in a list."""
        assertion = {
            "type": "Assertion",
            "id": "https://example.com/assertions/101",
            "badge": {"name": "Tester", "issuer": {"name": "Org"}},
            "evidence": "https://example.com/evidence/solo",
        }
        mock_fetch.return_value = assertion

        result = await fetch_open_badges_assertion("https://example.com/assertions/101")

        assert result.evidence == ["https://example.com/evidence/solo"]
