from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from pathlib import Path

STATIC_ROOT = Path("fitness/static")


@lru_cache(maxsize=128)
def asset_url(relative_path: str) -> str:
    """Return a cache-busted URL for app-bundled static files.

    Always serves from the local /static/ mount. The media CDN
    (media_cdn_domain) only handles user-uploaded S3 content,
    not container-bundled assets like CSS, JS, and fonts.
    """
    file_path = STATIC_ROOT / relative_path
    if file_path.exists():
        digest = sha256(file_path.read_bytes()).hexdigest()[:12]
        return f"/static/{relative_path}?v={digest}"
    return f"/static/{relative_path}"
