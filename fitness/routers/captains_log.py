"""Captain's Log router — project status entries."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from fitness.auth import current_active_user
from fitness.database import get_db
from fitness.models.blog import BlogEntry
from fitness.schemas.blog import Category
from fitness.security import issue_csrf_token, limiter, set_csrf_cookie
from fitness.services.blog_service import blog_service
from fitness.utils.assets import asset_url

router = APIRouter(
    prefix="/admin/log",
    tags=["captains-log"],
    dependencies=[Depends(current_active_user)],
)
templates = Jinja2Templates(directory="fitness/templates")
templates.env.globals["asset_url"] = asset_url


@router.get("", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def log_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(current_active_user),
):
    """Captain's Log dashboard — list existing entries."""
    entries = (
        db.query(BlogEntry)
        .filter(BlogEntry.category == Category.CAPTAINS_LOG.value)
        .order_by(desc(BlogEntry.created_at))
        .limit(50)
        .all()
    )

    # Parse tags JSON for template display
    for entry in entries:
        entry._parsed_tags = json.loads(entry.tags) if entry.tags else []

    csrf_token = issue_csrf_token(request)

    response = templates.TemplateResponse(
        "captains_log/dashboard.html",
        {
            "request": request,
            "entries": entries,
            "user": user,
            "csrf_token": csrf_token,
            "admin_page": "log",
        },
    )
    set_csrf_cookie(response, csrf_token)
    return response


@router.get("/entry/{slug}", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def log_entry_view(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
    user=Depends(current_active_user),
):
    """Single Captain's Log entry with rendered markdown."""
    entry = db.query(BlogEntry).filter(BlogEntry.slug == slug).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Log entry not found")

    content_html = blog_service.render_markdown(entry.content)
    tags = json.loads(entry.tags) if entry.tags else []

    return templates.TemplateResponse(
        "captains_log/entry.html",
        {
            "request": request,
            "entry": entry,
            "content_html": content_html,
            "tags": tags,
            "user": user,
            "admin_page": "log",
        },
    )
