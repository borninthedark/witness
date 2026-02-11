from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from fitness.security import limiter
from fitness.services.report_status import (
    SUMMARY_DIR,
    collect_precommit_statuses,
    load_security_summary,
)
from fitness.utils.assets import asset_url

templates = Jinja2Templates(directory="fitness/templates")
templates.env.globals["asset_url"] = asset_url

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def reports_index(
    request: Request, section: str = Query("operations", alias="section")
) -> HTMLResponse:
    active_section = section.lower()
    if active_section not in {"operations", "security"}:
        active_section = "operations"

    try:
        hook_statuses = collect_precommit_statuses()
    except Exception as e:
        print(f"Warning: Failed to collect precommit statuses: {e}")
        hook_statuses = []

    try:
        security_summary = load_security_summary()
    except Exception as e:
        print(f"Warning: Failed to load security summary: {e}")
        security_summary = {"entries": []}

    return templates.TemplateResponse(
        "reports/index.html",
        {
            "request": request,
            "hook_statuses": hook_statuses,
            "security_summary": security_summary,
            "active_section": active_section,
        },
    )


@router.get("/operations", include_in_schema=False)
@limiter.limit("30/minute")
async def reports_operations(request: Request) -> RedirectResponse:
    return RedirectResponse(url="/reports/?section=operations", status_code=307)


@router.get("/security", include_in_schema=False)
@limiter.limit("30/minute")
async def reports_security(request: Request) -> RedirectResponse:
    return RedirectResponse(url="/reports/?section=security", status_code=307)


@router.get("/files/{path:path}", response_class=FileResponse)
@limiter.limit("30/minute")
async def reports_file(request: Request, path: str):
    summary_root = SUMMARY_DIR.resolve()
    target = (SUMMARY_DIR / path).resolve()
    try:
        target.relative_to(summary_root)
    except ValueError:
        return RedirectResponse(url="/reports/?section=operations", status_code=307)
    if not target.exists():
        return RedirectResponse(url="/reports/?section=operations", status_code=307)
    return FileResponse(target, media_type="text/markdown", filename=target.name)
