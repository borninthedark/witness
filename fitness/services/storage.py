from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, file: BinaryIO, filename: str) -> str: ...

    @abstractmethod
    async def delete(self, filename: str) -> bool: ...

    @abstractmethod
    async def get_url(self, filename: str) -> str: ...


class LocalStorage(StorageBackend):
    def __init__(self, base_path: Path, base_url: str):
        self.base_path = base_path
        self.base_url = base_url
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, file: BinaryIO, filename: str) -> str:
        path = self.base_path / filename
        path.write_bytes(file.read())
        return f"{self.base_url}/static/certs/{filename}"

    async def delete(self, filename: str) -> bool:
        p = self.base_path / filename
        if p.exists():
            p.unlink()
            return True
        return False

    async def get_url(self, filename: str) -> str:
        return f"{self.base_url}/static/certs/{filename}"


_CONTENT_TYPES: dict[str, str] = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


class S3MediaStorage(StorageBackend):
    """S3 storage backend for media files served via CloudFront CDN."""

    def __init__(self, bucket_name: str, cdn_base_url: str, region: str = "us-east-1"):
        import boto3

        self.bucket_name = bucket_name
        self.cdn_base_url = cdn_base_url.rstrip("/")
        self.client = boto3.client("s3", region_name=region)

    @staticmethod
    def _guess_content_type(filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        return _CONTENT_TYPES.get(suffix, "application/octet-stream")

    async def save(self, file: BinaryIO, filename: str) -> str:
        content_type = self._guess_content_type(filename)
        key = f"media/{filename}"
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=file.read(),
            ContentType=content_type,
        )
        return f"{self.cdn_base_url}/media/{filename}"

    async def delete(self, filename: str) -> bool:
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=f"media/{filename}",
            )
            return True
        except Exception:
            logger.exception("Failed to delete media/%s", filename)
            return False

    async def get_url(self, filename: str) -> str:
        return f"{self.cdn_base_url}/media/{filename}"
