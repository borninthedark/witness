from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from fitness.auth import current_active_user
from fitness.config import settings
from fitness.database import get_db
from fitness.models.certification import Certification
from fitness.security import issue_csrf_token, limiter, set_csrf_cookie, validate_csrf
from fitness.services.open_badges import OpenBadgesError, fetch_open_badges_assertion
from fitness.services.storage import LocalStorage, S3MediaStorage
from fitness.staticfiles import templates

router = APIRouter(prefix="/admin", tags=["admin"])

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _validate_slug(slug: str) -> str:
    """Validate slug is safe for use in file paths (no traversal)."""
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            status_code=400,
            detail="Slug must be 1-64 lowercase alphanumeric characters or hyphens.",
        )
    return slug


def hash_file(path: Path) -> str:
    """Generate SHA-256 hash of a file.

    Args:
        path: Path to the file to hash

    Returns:
        64-character hexadecimal SHA-256 digest
    """
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _admin_page(request: Request, template: str, user, admin_page: str, **extra):
    """Render an admin page with CSRF token and cookie."""
    csrf_token = issue_csrf_token(request)
    ctx = {
        "request": request,
        "user": user,
        "csrf_token": csrf_token,
        "admin_page": admin_page,
        **extra,
    }
    response = templates.TemplateResponse(template, ctx)
    set_csrf_cookie(response, csrf_token)
    return response


@router.get("/", response_class=HTMLResponse)
@limiter.limit("30/minute")
def admin_dashboard(
    request: Request,
    user=Depends(current_active_user),
):
    """Admin dashboard landing page with navigation to sub-panels."""
    return _admin_page(request, "admin_dashboard.html", user, "dashboard")


@router.get("/login", response_class=HTMLResponse)
@limiter.limit("30/minute")
def login_page(request: Request):
    """Display admin login page.

    Args:
        request: FastAPI request object

    Returns:
        HTML response with login form and CSRF token
    """
    csrf_token = issue_csrf_token(request)
    # Get the 'next' parameter to redirect after login
    next_url = request.query_params.get("next", "/admin")
    response = templates.TemplateResponse(
        "admin_login.html",
        {
            "request": request,
            "csrf_token": csrf_token,
            "next_url": next_url,
        },
    )
    set_csrf_cookie(response, csrf_token)
    return response


@router.get("/certs", response_class=HTMLResponse)
@limiter.limit("30/minute")
def admin_certs(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(current_active_user),
):
    """Display certification management dashboard.

    Shows all certifications (active and deprecated) with options to:
    - Add new certifications
    - Deprecate existing certifications
    - Permanently delete certifications

    Args:
        request: FastAPI request object
        db: Database session
        user: Currently authenticated admin user

    Returns:
        HTML response with certification management interface
    """
    certs = db.query(Certification).order_by(Certification.created_at.desc()).all()
    csrf_token = issue_csrf_token(request)
    response = templates.TemplateResponse(
        "admin_certs.html",
        {
            "request": request,
            "certs": certs,
            "user": user,
            "enable_open_badges": settings.enable_open_badges,
            "csrf_token": csrf_token,
            "admin_page": "certs",
        },
    )
    set_csrf_cookie(response, csrf_token)
    return response


@router.post("/certs", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def admin_add_cert(
    request: Request,
    file: UploadFile,
    slug: str = Form(...),
    title: str = Form(...),
    issuer: str = Form(...),
    verification_url: str = Form(""),
    assertion_url: str = Form(""),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(current_active_user),
):
    """Add a new certification to the database.

    This endpoint:
    1. Validates CSRF token
    2. Validates Open Badges assertion URL (if provided and enabled)
    3. Saves PDF file to static/certs/
    4. Calculates SHA-256 hash of the PDF
    5. Creates database entry
    6. Returns HTMX-compatible table row HTML

    Args:
        request: FastAPI request object
        file: Uploaded PDF file
        slug: URL-friendly identifier (e.g., "ckad")
        title: Human-readable certification name
        issuer: Organization that issued the certification
        verification_url: Optional external verification link
        assertion_url: Optional Open Badges assertion URL
        csrf_token: CSRF protection token
        db: Database session
        user: Currently authenticated admin user

    Returns:
        HTML table row for HTMX insertion

    Raises:
        HTTPException: 400 if Open Badges validation fails
    """
    validate_csrf(request, csrf_token)
    _validate_slug(slug)

    # Enforce 10 MB upload limit
    _MAX_UPLOAD_BYTES = 10 * 1024 * 1024
    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="PDF must be under 10 MB.")
    await file.seek(0)

    if assertion_url and settings.enable_open_badges:
        try:
            await fetch_open_badges_assertion(assertion_url)
        except OpenBadgesError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    storage = LocalStorage(Path("fitness/static/certs"), settings.base_url)
    filename = f"{slug}.pdf"
    url = await storage.save(file.file, filename)
    sha = hash_file(Path("fitness/static/certs") / filename)
    cert = Certification(
        slug=slug,
        title=title,
        issuer=issuer,
        pdf_url=url,
        sha256=sha,
        assertion_url=assertion_url,
        verification_url=verification_url,
    )
    db.add(cert)
    db.commit()

    links = [f"<a href='{html.escape(url)}' target='_blank'>PDF</a>"]
    if verification_url:
        links.append(
            f"<a href='{html.escape(verification_url)}' target='_blank'>Verify</a>"
        )
    if assertion_url:
        links.append(
            f"<a href='{html.escape(assertion_url)}' target='_blank'>Open Badges</a>"
        )

    row = (
        f"<tr><td><span class='badge'>{html.escape(issuer)}</span></td>"
        f"<td>{html.escape(title)}</td>"
        f"<td><code>{html.escape(slug)}</code></td>"
        f"<td class='actions'>{' | '.join(links)}</td></tr>"
    )
    return HTMLResponse(row)


@router.post("/badges/preview", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def badge_preview(
    request: Request,
    assertion_url: str = Form(...),
    csrf_token: str = Form(...),
    user=Depends(current_active_user),
):
    """Validate and preview an Open Badges assertion URL.

    Fetches badge metadata from the assertion URL and returns HTML preview
    for display in the admin interface.

    Args:
        request: FastAPI request object
        assertion_url: Open Badges assertion URL to validate
        csrf_token: CSRF protection token
        user: Currently authenticated admin user

    Returns:
        HTML partial with badge preview or error message

    Raises:
        HTTPException: 400 if Open Badges is disabled
    """
    validate_csrf(request, csrf_token)
    if not settings.enable_open_badges:
        raise HTTPException(
            status_code=400, detail="Open Badges validation is disabled."
        )
    try:
        preview = await fetch_open_badges_assertion(assertion_url)
        context = {"request": request, "preview": preview, "error": None}
        status_code = 200
    except OpenBadgesError as exc:
        context = {"request": request, "preview": None, "error": str(exc)}
        status_code = 400
    return templates.TemplateResponse(
        "partials/badge_preview.html", context, status_code=status_code
    )


@router.post("/certs/{cert_id}/status", response_class=HTMLResponse)
@limiter.limit("20/minute")
def update_cert_status(
    cert_id: int,
    request: Request,
    status: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(current_active_user),
):
    """Update certification status (active/deprecated/expired).

    Args:
        cert_id: Database ID of the certification
        request: FastAPI request object
        status: New status value (active, deprecated, or expired)
        csrf_token: CSRF protection token
        db: Database session
        user: Currently authenticated admin user

    Returns:
        Empty HTML response to trigger page reload

    Raises:
        HTTPException: 404 if certification not found
        HTTPException: 400 if invalid status value
    """
    validate_csrf(request, csrf_token)

    if status not in ("active", "deprecated", "expired"):
        raise HTTPException(status_code=400, detail="Invalid status value")

    cert = db.query(Certification).filter(Certification.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")

    cert.status = status
    # Update legacy field for backward compatibility
    cert.is_active = status == "active"
    db.commit()

    # Return empty response to trigger full page reload
    return HTMLResponse("", headers={"HX-Refresh": "true"})


@router.post("/certs/{cert_id}/visibility", response_class=HTMLResponse)
@limiter.limit("20/minute")
def toggle_cert_visibility(
    cert_id: int,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(current_active_user),
):
    """Toggle certification visibility in public listings.

    Args:
        cert_id: Database ID of the certification
        request: FastAPI request object
        csrf_token: CSRF protection token
        db: Database session
        user: Currently authenticated admin user

    Returns:
        Empty HTML response to trigger page reload

    Raises:
        HTTPException: 404 if certification not found
    """
    validate_csrf(request, csrf_token)

    cert = db.query(Certification).filter(Certification.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")

    cert.is_visible = not cert.is_visible
    db.commit()

    # Return empty response to trigger full page reload
    return HTMLResponse("", headers={"HX-Refresh": "true"})


@router.delete("/certs/{cert_id}", response_class=HTMLResponse)
@limiter.limit("10/minute")
def delete_cert(
    cert_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(current_active_user),
):
    """Permanently delete a certification.

    This action:
    1. Removes the database entry
    2. Deletes the PDF file from static/certs/

    WARNING: This action cannot be undone. Consider deprecating instead
    to preserve historical records.

    Args:
        cert_id: Database ID of the certification to delete
        request: FastAPI request object
        db: Database session
        user: Currently authenticated admin user

    Returns:
        Empty HTML response (row removed via HTMX swap-oob)

    Raises:
        HTTPException: 404 if certification not found
    """
    cert = db.query(Certification).filter(Certification.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")

    # Delete PDF file
    pdf_path = Path("fitness/static/certs") / f"{cert.slug}.pdf"
    if pdf_path.exists():
        pdf_path.unlink()

    # Delete from database
    db.delete(cert)
    db.commit()

    # Return empty response - HTMX will remove the row
    return HTMLResponse("")


# ================================================================
# Media Management (CDN upload)
# ================================================================

_MEDIA_MIME_ALLOWLIST = {
    "video/mp4",
    "video/webm",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


@router.get("/media", response_class=HTMLResponse)
@limiter.limit("30/minute")
def media_dashboard(
    request: Request,
    user=Depends(current_active_user),
):
    """Media management dashboard."""
    return _admin_page(
        request,
        "admin_media.html",
        user,
        "media",
        media_configured=bool(settings.media_bucket_name),
    )


@router.post("/media", response_class=HTMLResponse)
@limiter.limit("5/minute")
async def upload_media(
    request: Request,
    file: UploadFile,
    slug: str = Form(...),
    csrf_token: str = Form(...),
    user=Depends(current_active_user),
):
    """Upload media file to S3 via CDN."""
    validate_csrf(request, csrf_token)
    _validate_slug(slug)

    if not settings.media_bucket_name:
        raise HTTPException(status_code=503, detail="Media storage not configured.")

    # MIME type check
    content_type = file.content_type or ""
    if content_type not in _MEDIA_MIME_ALLOWLIST:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. "
            f"Allowed: {', '.join(sorted(_MEDIA_MIME_ALLOWLIST))}",
        )

    # Size check
    max_bytes = settings.media_upload_max_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File must be under {settings.media_upload_max_mb} MB.",
        )
    await file.seek(0)

    # Determine extension from original filename
    ext = Path(file.filename or "file").suffix.lower() or ".bin"
    media_filename = f"{slug}{ext}"

    storage = S3MediaStorage(
        bucket_name=settings.media_bucket_name,
        cdn_base_url=f"https://{settings.media_cdn_domain}",
        region=settings.aws_region,
    )
    url = await storage.save(file.file, media_filename)

    return HTMLResponse(
        f"<div class='upload-result'>"
        f"<p>Uploaded: <a href='{html.escape(url)}' target='_blank'>"
        f"{html.escape(media_filename)}</a></p>"
        f"<code>{html.escape(url)}</code>"
        f"</div>"
    )
