"""Blog router for Captain's Personal Log."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, desc, func, or_
from sqlalchemy.orm import Session

from fitness.auth import current_active_user
from fitness.database import get_db
from fitness.models.blog import BlogEntry
from fitness.schemas.blog import Category, LogStatus
from fitness.security import limiter
from fitness.services.blog_service import blog_service
from fitness.utils.assets import asset_url

router = APIRouter(prefix="/log", tags=["blog"])
templates = Jinja2Templates(directory="fitness/templates")
templates.env.globals["current_year"] = datetime.now(timezone.utc).year
templates.env.globals["asset_url"] = asset_url


@router.get("/", response_class=HTMLResponse, name="log_index")
@limiter.limit("30/minute")
async def log_index(
    request: Request,
    category: str | None = Query(None),
    tag: str | None = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user=Depends(current_active_user),
):
    """Captain's Log index page with optional category/tag filtering."""
    entries_per_page = 10
    offset = (page - 1) * entries_per_page

    # Build query for published entries
    query = db.query(BlogEntry).filter(BlogEntry.status == LogStatus.PUBLISHED.value)

    # Apply category filter
    if category:
        try:
            category_enum = Category(category.lower())
            query = query.filter(BlogEntry.category == category_enum.value)
        except ValueError:
            pass  # Invalid category, ignore filter

    # Apply tag filter
    if tag:
        query = query.filter(BlogEntry.tags.like(f'%"{tag}"%'))

    # Get entries ordered by published date
    entries = (
        query.order_by(desc(BlogEntry.published_at))
        .limit(entries_per_page)
        .offset(offset)
        .all()
    )

    # Convert to public schema with rendered HTML
    public_entries = [blog_service.get_public_entry(entry) for entry in entries]

    # Get all unique tags for sidebar
    all_tags = _get_all_tags(db)

    # Get stats
    stats = _get_blog_stats(db)

    return templates.TemplateResponse(
        "blog/log_index.html",
        {
            "request": request,
            "entries": public_entries,
            "current_category": category,
            "current_tag": tag,
            "categories": [c.value for c in Category],
            "all_tags": all_tags,
            "stats": stats,
            "page": page,
            "has_more": len(entries) == entries_per_page,
        },
    )


@router.get("/entry/{slug}", response_class=HTMLResponse, name="log_entry")
@limiter.limit("30/minute")
async def log_entry(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
    user=Depends(current_active_user),
):
    """Single log entry view."""
    # Get entry
    entry = (
        db.query(BlogEntry)
        .filter(BlogEntry.slug == slug, BlogEntry.status == LogStatus.PUBLISHED.value)
        .first()
    )

    if not entry:
        raise HTTPException(status_code=404, detail="Log entry not found")

    # Increment view count
    entry.view_count += 1
    db.commit()

    # Convert to public schema
    public_entry = blog_service.get_public_entry(entry)

    # Get related entries (same category, excluding current)
    related_entries = (
        db.query(BlogEntry)
        .filter(
            BlogEntry.category == entry.category,
            BlogEntry.status == LogStatus.PUBLISHED.value,
            BlogEntry.slug != slug,
        )
        .order_by(desc(BlogEntry.published_at))
        .limit(3)
        .all()
    )

    related_public = [blog_service.get_public_entry(e) for e in related_entries]

    return templates.TemplateResponse(
        "blog/log_entry.html",
        {
            "request": request,
            "entry": public_entry,
            "related_entries": related_public,
        },
    )


@router.get("/search", response_class=HTMLResponse, name="log_search")
@limiter.limit("20/minute")
async def log_search(
    request: Request,
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user=Depends(current_active_user),
):
    """Search log entries (HTMX endpoint)."""
    # Simple search across title, summary, and content
    search_term = f"%{q}%"
    results = (
        db.query(BlogEntry)
        .filter(
            BlogEntry.status == LogStatus.PUBLISHED.value,
            or_(
                BlogEntry.title.like(search_term),
                BlogEntry.summary.like(search_term),
                BlogEntry.content.like(search_term),
                BlogEntry.tags.like(search_term),
            ),
        )
        .order_by(desc(BlogEntry.published_at))
        .limit(20)
        .all()
    )

    public_results = [blog_service.get_public_entry(e) for e in results]

    return templates.TemplateResponse(
        "blog/search_results.html",
        {
            "request": request,
            "results": public_results,
            "query": q,
            "total": len(public_results),
        },
    )


@router.get("/category/{category}", response_class=HTMLResponse, name="log_by_category")
@limiter.limit("30/minute")
async def log_by_category(
    request: Request,
    category: str,
    db: Session = Depends(get_db),
    user=Depends(current_active_user),
):
    """HTMX endpoint - filter entries by category."""
    try:
        category_enum = Category(category.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid category")

    entries = (
        db.query(BlogEntry)
        .filter(
            BlogEntry.status == LogStatus.PUBLISHED.value,
            BlogEntry.category == category_enum.value,
        )
        .order_by(desc(BlogEntry.published_at))
        .limit(20)
        .all()
    )

    public_entries = [blog_service.get_public_entry(e) for e in entries]

    return templates.TemplateResponse(
        "blog/log_entry_card.html",
        {
            "request": request,
            "entries": public_entries,
        },
    )


def _get_all_tags(db: Session) -> list[str]:
    """Get all unique tags from published entries."""
    entries = (
        db.query(BlogEntry).filter(BlogEntry.status == LogStatus.PUBLISHED.value).all()
    )

    all_tags = set()
    for entry in entries:
        if entry.tags:
            try:
                tags = json.loads(entry.tags)
                all_tags.update(tags)
            except json.JSONDecodeError:
                pass

    return sorted(list(all_tags))


def _get_blog_stats(db: Session) -> dict:
    """Get blog statistics."""
    stats = db.query(
        func.count(BlogEntry.id).label("total_entries"),
        func.sum(
            case((BlogEntry.status == LogStatus.PUBLISHED.value, 1), else_=0)
        ).label("published"),
        func.sum(BlogEntry.view_count).label("total_views"),
    ).first()

    return {
        "total_entries": stats.total_entries or 0,
        "published": stats.published or 0,
        "total_views": stats.total_views or 0,
    }
