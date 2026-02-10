"""Captain's Log router — AI-generated project status entries."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc
from sqlalchemy.orm import Session

from fitness.auth import current_active_user
from fitness.config import settings
from fitness.database import get_db
from fitness.models.blog import BlogEntry
from fitness.schemas.blog import Category, LogStatus
from fitness.security import issue_csrf_token, set_csrf_cookie, validate_csrf
from fitness.services.blog_service import blog_service
from fitness.services.captains_log import captains_log_service
from fitness.utils.assets import asset_url

router = APIRouter(
    prefix="/admin/log",
    tags=["captains-log"],
    dependencies=[Depends(current_active_user)],
)
templates = Jinja2Templates(directory="fitness/templates")
templates.env.globals["asset_url"] = asset_url


@router.get("", response_class=HTMLResponse)
async def log_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(current_active_user),
):
    """Captain's Log dashboard — list entries with generate button."""
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
    has_api_key = bool(settings.anthropic_api_key)

    response = templates.TemplateResponse(
        "captains_log/dashboard.html",
        {
            "request": request,
            "entries": entries,
            "user": user,
            "csrf_token": csrf_token,
            "admin_page": "log",
            "has_api_key": has_api_key,
        },
    )
    set_csrf_cookie(response, csrf_token)
    return response


@router.post("/generate", response_class=HTMLResponse)
async def generate_log_entry(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(current_active_user),
):
    """Collect telemetry, call AI, save a new BlogEntry, redirect."""
    # Read CSRF from form body
    form = await request.form()
    csrf_token = form.get("csrf_token", "")
    validate_csrf(request, csrf_token)

    if not settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not configured")

    # Collect telemetry (no aggregator dependency for now)
    telemetry = await captains_log_service.collect_telemetry(db)

    # Generate entry via AI
    data = await captains_log_service.generate_entry(telemetry)
    if data is None:
        raise HTTPException(status_code=502, detail="AI generation failed")

    # Persist as BlogEntry
    slug = blog_service.generate_slug(data["title"])
    # Ensure unique slug
    existing = db.query(BlogEntry).filter(BlogEntry.slug == slug).first()
    if existing:
        slug = f"{slug}-{int(datetime.now(UTC).timestamp())}"

    entry = BlogEntry(
        title=data["title"],
        slug=slug,
        summary=data.get("summary", "")[:500],
        content=data.get("content", ""),
        category=Category.CAPTAINS_LOG.value,
        tags=json.dumps(data.get("tags", [])),
        stardate=data.get("stardate"),
        status=LogStatus.PUBLISHED.value,
        reading_time_minutes=blog_service.calculate_reading_time(
            data.get("content", "")
        ),
        published_at=datetime.now(UTC),
    )
    db.add(entry)
    db.commit()

    # Redirect back to dashboard
    return HTMLResponse("", status_code=303, headers={"Location": "/admin/log"})


@router.get("/entry/{slug}", response_class=HTMLResponse)
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
