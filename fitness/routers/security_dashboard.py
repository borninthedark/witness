"""Security advisory dashboard router with HTMX endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from fitness.auth import current_active_user
from fitness.config import settings
from fitness.models.security import AdvisorySource, SeverityLevel
from fitness.services.cve_aggregator import CVEAggregator
from fitness.utils.assets import asset_url

router = APIRouter(
    prefix="/admin/tactical",
    tags=["tactical"],
    dependencies=[Depends(current_active_user)],
)
templates = Jinja2Templates(directory="fitness/templates")
templates.env.globals["asset_url"] = asset_url

# Initialize aggregator with NIST API key from settings
aggregator = CVEAggregator(nist_api_key=settings.nist_api_key)


@router.get("/dashboard", response_class=HTMLResponse)
async def security_dashboard(request: Request):
    """Main security dashboard page.

    Returns:
        HTML page with security advisory dashboard
    """
    # Get initial stats
    stats = await aggregator.get_stats(days=30)

    return templates.TemplateResponse(
        "security/dashboard.html",
        {"request": request, "stats": stats, "current_page": "security"},
    )


@router.get("/advisories", response_class=HTMLResponse)
async def get_advisories(
    request: Request,
    severity: str | None = Query(None),
    source: str | None = Query(None),
    days: int = Query(30, ge=1, le=365),
):
    """HTMX endpoint - returns HTML fragment of filtered advisories.

    Query params:
    - severity: CRITICAL, HIGH, MEDIUM, LOW
    - source: NIST, CVE
    - days: Number of days to look back (1-365)

    Returns:
        HTML fragment with filtered advisories
    """
    # Convert string filters to enums
    severity_filter = None
    if severity:
        try:
            severity_filter = SeverityLevel(severity.upper())
        except ValueError:
            pass

    source_filter = None
    if source:
        try:
            source_filter = AdvisorySource(source.upper())
        except ValueError:
            pass

    # Fetch advisories
    advisories = await aggregator.fetch_all_advisories(
        days=days, severity=severity_filter, source=source_filter
    )

    return templates.TemplateResponse(
        "security/advisories_list.html",
        {"request": request, "advisories": advisories, "total": len(advisories)},
    )


@router.get("/advisory/{cve_id}", response_class=HTMLResponse)
async def get_advisory_detail(request: Request, cve_id: str):
    """Get detailed view of a single CVE (for modal display).

    Args:
        cve_id: CVE identifier (e.g., CVE-2024-1234)

    Returns:
        HTML fragment with advisory details

    Raises:
        HTTPException: If advisory not found
    """
    advisory = await aggregator.get_advisory_by_id(cve_id)

    if not advisory:
        raise HTTPException(status_code=404, detail="Advisory not found")

    return templates.TemplateResponse(
        "security/advisory_detail.html", {"request": request, "advisory": advisory}
    )


@router.get("/stats", response_class=HTMLResponse)
async def get_stats_widget(request: Request, days: int = Query(30, ge=1, le=365)):
    """HTMX endpoint - returns stats widget HTML.

    Args:
        days: Number of days to look back (1-365)

    Returns:
        HTML fragment with statistics widget
    """
    stats = await aggregator.get_stats(days=days)

    return templates.TemplateResponse(
        "security/stats_widget.html", {"request": request, "stats": stats}
    )


@router.get("/top-advisories", response_class=HTMLResponse)
async def get_top_advisories(
    request: Request,
    severity: str = Query(...),
    limit: int = Query(5, ge=1, le=20),
    days: int = Query(30, ge=1, le=365),
):
    """HTMX endpoint - returns top N advisories for a severity level.

    Args:
        severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
        limit: Number of advisories to return (1-20)
        days: Number of days to look back (1-365)

    Returns:
        HTML fragment with top advisories
    """
    # Convert string to enum
    try:
        severity_level = SeverityLevel(severity.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid severity level")

    # Fetch top advisories
    advisories = await aggregator.get_top_advisories(
        severity=severity_level, limit=limit, days=days
    )

    return templates.TemplateResponse(
        "security/top_advisories.html",
        {
            "request": request,
            "advisories": advisories,
            "severity": severity_level.value,
            "total": len(advisories),
            "limit": limit,
        },
    )


@router.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    try:
        await aggregator.close()
    except RuntimeError:
        pass
