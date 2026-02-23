from __future__ import annotations

from datetime import UTC, datetime

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from fitness.utils.assets import asset_url

# Shared Jinja2 templates instance
templates = Jinja2Templates(directory="fitness/templates")
templates.env.globals["current_year"] = datetime.now(UTC).year
templates.env.globals["asset_url"] = asset_url


class CachedStaticFiles(StaticFiles):
    def __init__(self, *args, cache_control: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_control = cache_control or "public, max-age=31536000, immutable"

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if self.cache_control and response.status_code == 200:
            response.headers.setdefault("Cache-Control", self.cache_control)
        return response
