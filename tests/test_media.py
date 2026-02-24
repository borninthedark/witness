"""TDD tests for media CDN: S3 storage, upload routes, CSP, asset_url CDN."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from fitness.auth import current_active_user
from fitness.main import app

CSRF_TOKEN = "test-csrf-token"


@pytest.fixture
def auth_client(client):
    """Authenticated test client with CSRF token."""
    mock_user = MagicMock(email="test@test.com", id=uuid4(), is_active=True)
    app.dependency_overrides[current_active_user] = lambda: mock_user
    client.cookies.set("wtf_csrf", CSRF_TOKEN)
    yield client
    app.dependency_overrides.pop(current_active_user, None)
    client.cookies.delete("wtf_csrf")


# ── S3MediaStorage ────────────────────────────────────────────────


class TestS3MediaStorage:
    """Unit tests for S3MediaStorage backend."""

    def _make_storage(self):
        from fitness.services.storage import S3MediaStorage

        mock_client = MagicMock()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_client
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            storage = S3MediaStorage(
                bucket_name="witness-dev-media",
                cdn_base_url="https://media.princetonstrong.com",
                region="us-east-1",
            )
        return storage, mock_client

    @pytest.mark.asyncio
    async def test_save_calls_put_object_with_correct_params(self):
        storage, mock_client = self._make_storage()
        fake_file = BytesIO(b"fake-video-content")

        await storage.save(fake_file, "tutorial.mp4")

        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "witness-dev-media"
        assert call_kwargs["Key"] == "media/tutorial.mp4"
        assert call_kwargs["ContentType"] == "video/mp4"

    @pytest.mark.asyncio
    async def test_save_returns_cdn_url(self):
        storage, mock_client = self._make_storage()
        fake_file = BytesIO(b"content")

        url = await storage.save(fake_file, "demo.mp4")

        assert url == "https://media.princetonstrong.com/media/demo.mp4"

    @pytest.mark.asyncio
    async def test_delete_calls_delete_object(self):
        storage, mock_client = self._make_storage()

        result = await storage.delete("old-video.mp4")

        mock_client.delete_object.assert_called_once_with(
            Bucket="witness-dev-media",
            Key="media/old-video.mp4",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_on_error(self):
        storage, mock_client = self._make_storage()
        mock_client.delete_object.side_effect = Exception("S3 error")

        result = await storage.delete("bad.mp4")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_url_returns_cdn_path(self):
        storage, _ = self._make_storage()

        url = await storage.get_url("video.mp4")

        assert url == "https://media.princetonstrong.com/media/video.mp4"

    def test_guess_content_type_mp4(self):
        from fitness.services.storage import S3MediaStorage

        assert S3MediaStorage._guess_content_type("video.mp4") == "video/mp4"

    def test_guess_content_type_webm(self):
        from fitness.services.storage import S3MediaStorage

        assert S3MediaStorage._guess_content_type("video.webm") == "video/webm"

    def test_guess_content_type_jpg(self):
        from fitness.services.storage import S3MediaStorage

        assert S3MediaStorage._guess_content_type("photo.jpg") == "image/jpeg"

    def test_guess_content_type_png(self):
        from fitness.services.storage import S3MediaStorage

        assert S3MediaStorage._guess_content_type("img.png") == "image/png"

    def test_guess_content_type_unknown(self):
        from fitness.services.storage import S3MediaStorage

        assert (
            S3MediaStorage._guess_content_type("file.xyz") == "application/octet-stream"
        )


# ── Media Upload Route ────────────────────────────────────────────


class TestMediaUploadRoute:
    """Admin media upload endpoint tests."""

    def test_upload_requires_auth(self, client):
        """Unauthenticated upload returns redirect to login."""
        resp = client.post(
            "/admin/media",
            data={"slug": "test", "csrf_token": "tok"},
            files={"file": ("test.mp4", BytesIO(b"data"), "video/mp4")},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 401, 403)

    def test_upload_requires_csrf(self, auth_client):
        """Upload without valid CSRF token fails."""
        auth_client.cookies.delete("wtf_csrf")
        with patch("fitness.config.settings.media_bucket_name", "test-bucket"):
            resp = auth_client.post(
                "/admin/media",
                data={"slug": "test", "csrf_token": "wrong-token"},
                files={"file": ("test.mp4", BytesIO(b"data"), "video/mp4")},
            )
        assert resp.status_code in (400, 403)

    def test_upload_rejects_unconfigured(self, auth_client):
        """Upload returns 503 when media_bucket_name is empty."""
        with patch("fitness.routers.admin.settings") as mock_settings:
            mock_settings.media_bucket_name = ""
            resp = auth_client.post(
                "/admin/media",
                data={"slug": "test", "csrf_token": CSRF_TOKEN},
                files={"file": ("test.mp4", BytesIO(b"data"), "video/mp4")},
            )
        assert resp.status_code == 503

    def test_upload_rejects_bad_mime_type(self, auth_client):
        """Upload rejects non-media MIME types."""
        with patch("fitness.routers.admin.settings") as mock_settings:
            mock_settings.media_bucket_name = "test-bucket"
            mock_settings.media_upload_max_mb = 200
            resp = auth_client.post(
                "/admin/media",
                data={"slug": "test", "csrf_token": CSRF_TOKEN},
                files={"file": ("test.txt", BytesIO(b"data"), "text/plain")},
            )
        assert resp.status_code == 400

    def test_upload_rejects_oversized_file(self, auth_client):
        """Upload rejects files over max size."""
        oversized = b"x" * (200 * 1024 * 1024 + 1)
        with patch("fitness.routers.admin.settings") as mock_settings:
            mock_settings.media_bucket_name = "test-bucket"
            mock_settings.media_upload_max_mb = 200
            resp = auth_client.post(
                "/admin/media",
                data={"slug": "test", "csrf_token": CSRF_TOKEN},
                files={"file": ("big.mp4", BytesIO(oversized), "video/mp4")},
            )
        assert resp.status_code == 400

    def test_upload_rejects_bad_slug(self, auth_client):
        """Upload rejects path traversal slugs."""
        with patch("fitness.routers.admin.settings") as mock_settings:
            mock_settings.media_bucket_name = "test-bucket"
            mock_settings.media_upload_max_mb = 200
            resp = auth_client.post(
                "/admin/media",
                data={"slug": "../etc/passwd", "csrf_token": CSRF_TOKEN},
                files={"file": ("test.mp4", BytesIO(b"data"), "video/mp4")},
            )
        assert resp.status_code == 400

    def test_upload_succeeds(self, auth_client):
        """Valid upload returns 200 with CDN URL."""
        with (
            patch("fitness.routers.admin.settings") as mock_settings,
            patch("fitness.routers.admin.S3MediaStorage") as MockStorage,
        ):
            mock_settings.media_bucket_name = "test-bucket"
            mock_settings.media_cdn_domain = "media.princetonstrong.com"
            mock_settings.media_upload_max_mb = 200
            mock_settings.aws_region = "us-east-1"

            mock_instance = MagicMock()
            mock_instance.save = AsyncMock(
                return_value="https://media.princetonstrong.com/media/test.mp4"
            )
            MockStorage.return_value = mock_instance

            resp = auth_client.post(
                "/admin/media",
                data={"slug": "test-video", "csrf_token": CSRF_TOKEN},
                files={"file": ("test.mp4", BytesIO(b"video-data"), "video/mp4")},
            )

        assert resp.status_code == 200
        assert "media.princetonstrong.com" in resp.text
        assert "Upload saved" in resp.text

    def test_media_dashboard_requires_auth(self, client):
        """Media dashboard requires authentication."""
        resp = client.get("/admin/media", follow_redirects=False)
        assert resp.status_code in (302, 401, 403)

    def test_media_dashboard_renders(self, auth_client):
        """Media dashboard renders for authenticated users."""
        resp = auth_client.get("/admin/media")
        assert resp.status_code == 200


# ── CDN-aware asset_url ───────────────────────────────────────────


class TestAssetUrlCdn:
    """asset_url transparently routes through CDN when configured."""

    def test_asset_url_local_when_no_cdn(self, tmp_path):
        """Without CDN, returns local /static/ path."""
        from fitness.utils.assets import asset_url

        css = tmp_path / "blog.css"
        css.write_text("body {}")

        with (
            patch("fitness.utils.assets.STATIC_ROOT", tmp_path),
            patch("fitness.utils.assets._cdn_domain", ""),
        ):
            asset_url.cache_clear()
            result = asset_url("blog.css")

        assert result.startswith("/static/blog.css?v=")

    def test_asset_url_cdn_when_configured(self, tmp_path):
        """With CDN configured, returns CDN URL."""
        from fitness.utils.assets import asset_url

        css = tmp_path / "blog.css"
        css.write_text("body {}")

        with (
            patch("fitness.utils.assets.STATIC_ROOT", tmp_path),
            patch("fitness.utils.assets._cdn_domain", "media.princetonstrong.com"),
        ):
            asset_url.cache_clear()
            result = asset_url("blog.css")

        assert result.startswith("https://media.princetonstrong.com/static/blog.css?v=")


# ── CSP media directives ──────────────────────────────────────────


class TestCspMediaDirectives:
    """CSP headers include CDN domain when configured."""

    def test_csp_has_media_src_when_cdn_configured(self, client):
        """media-src directive present when CDN is configured."""
        with patch("fitness.main.settings") as mock_settings:
            mock_settings.media_cdn_domain = "media.princetonstrong.com"
            # This tests the general mechanism; the actual CSP is built at module load
            # so we verify the builder function directly
            from fitness.main import _build_cdn_csp_extensions

            extensions = _build_cdn_csp_extensions("media.princetonstrong.com")
            assert "media-src" in extensions

    def test_csp_no_media_src_when_no_cdn(self):
        """No media-src without CDN domain."""
        from fitness.main import _build_cdn_csp_extensions

        extensions = _build_cdn_csp_extensions("")
        assert extensions == {}

    def test_csp_img_src_includes_cdn_when_configured(self):
        """img-src extended with CDN domain."""
        from fitness.main import _build_cdn_csp_extensions

        extensions = _build_cdn_csp_extensions("media.princetonstrong.com")
        assert "img-src" in extensions
        assert "media.princetonstrong.com" in extensions["img-src"]
