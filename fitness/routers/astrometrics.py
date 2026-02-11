"""Astrometrics router — NASA data + AI science briefing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from fitness.auth import current_active_user
from fitness.security import issue_csrf_token, limiter, set_csrf_cookie, validate_csrf
from fitness.services.astrometrics import astrometrics_service
from fitness.services.celestrak import celestrak_service
from fitness.services.noaa_space_weather import space_weather_service
from fitness.utils.assets import asset_url

router = APIRouter(
    prefix="/admin/astrometrics",
    tags=["astrometrics"],
    dependencies=[Depends(current_active_user)],
)
templates = Jinja2Templates(directory="fitness/templates")
templates.env.globals["asset_url"] = asset_url


@router.get("", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def astrometrics_dashboard(
    request: Request,
    user=Depends(current_active_user),
):
    """Astrometrics dashboard — APOD image, NEO table, space weather."""
    briefing = await astrometrics_service.get_briefing()
    csrf_token = issue_csrf_token(request)
    space_weather = await space_weather_service.get_current_conditions()
    satellites = await celestrak_service.get_active_satellites(limit=50)

    response = templates.TemplateResponse(
        "astrometrics/dashboard.html",
        {
            "request": request,
            "briefing": briefing,
            "user": user,
            "csrf_token": csrf_token,
            "admin_page": "astrometrics",
            "space_weather": space_weather,
            "satellite_count": len(satellites),
        },
    )
    set_csrf_cookie(response, csrf_token)
    return response


@router.post("/refresh", response_class=HTMLResponse)
@limiter.limit("5/minute")
async def refresh_astrometrics(
    request: Request,
    user=Depends(current_active_user),
):
    """Force-refresh the astrometrics cache."""
    form = await request.form()
    csrf_token = form.get("csrf_token", "")
    validate_csrf(request, csrf_token)

    await astrometrics_service.get_briefing(force_refresh=True)
    return HTMLResponse(
        "", status_code=303, headers={"Location": "/admin/astrometrics"}
    )
