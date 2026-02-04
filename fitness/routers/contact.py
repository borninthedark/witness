from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from fitness.security import limiter

router = APIRouter(prefix="", tags=["contact"])
templates = Jinja2Templates(directory="fitness/templates")


@router.get("/contact", response_class=HTMLResponse)
@limiter.limit("10/minute")
def contact_page(request: Request):
    """Render contact form - submissions handled by Formspree"""
    return templates.TemplateResponse(
        "contact_lcars.html",
        {"request": request},
    )
