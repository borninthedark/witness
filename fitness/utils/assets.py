from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from pathlib import Path

STATIC_ROOT = Path("fitness/static")

# Populated from settings at import time; empty = local-only
try:
    from fitness.config import settings

    _cdn_domain: str = getattr(settings, "media_cdn_domain", "")
except Exception:  # pragma: no cover — settings may not load in tests
    _cdn_domain = ""


@lru_cache(maxsize=128)
def asset_url(relative_path: str) -> str:
    file_path = STATIC_ROOT / relative_path
    if file_path.exists():
        digest = sha256(file_path.read_bytes()).hexdigest()[:12]
        if _cdn_domain:
            return f"https://{_cdn_domain}/static/{relative_path}?v={digest}"
        return f"/static/{relative_path}?v={digest}"
    if _cdn_domain:
        return f"https://{_cdn_domain}/static/{relative_path}"
    return f"/static/{relative_path}"
