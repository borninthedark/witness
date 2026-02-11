"""Stargazing router — sky meteorology dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from fitness.auth import current_active_user
from fitness.security import issue_csrf_token, limiter, set_csrf_cookie
from fitness.services.geolocation import geolocation_service
from fitness.services.sky_service import sky_service
from fitness.utils.assets import asset_url

router = APIRouter(
    prefix="/admin/stargazing",
    tags=["stargazing"],
    dependencies=[Depends(current_active_user)],
)
templates = Jinja2Templates(directory="fitness/templates")
templates.env.globals["asset_url"] = asset_url


@router.get("", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def stargazing_dashboard(
    request: Request,
    user=Depends(current_active_user),
):
    """Sky meteorology dashboard — satellites, aurora, weather, stargazing score."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    location = await geolocation_service.geolocate(client_ip)
    conditions = await sky_service.get_conditions(location)
    csrf_token = issue_csrf_token(request)

    response = templates.TemplateResponse(
        "stargazing/dashboard.html",
        {
            "request": request,
            "user": user,
            "csrf_token": csrf_token,
            "admin_page": "stargazing",
            "conditions": conditions,
        },
    )
    set_csrf_cookie(response, csrf_token)
    return response
