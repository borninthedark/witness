from __future__ import annotations

import hashlib
import html
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from fitness.auth import current_active_user
from fitness.config import settings
from fitness.database import get_db
from fitness.models.certification import Certification
from fitness.security import issue_csrf_token, set_csrf_cookie, validate_csrf
from fitness.services.open_badges import OpenBadgesError, fetch_open_badges_assertion
from fitness.services.storage import LocalStorage
from fitness.staticfiles import templates

router = APIRouter(prefix="/admin", tags=["admin"])


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


@router.get("/", include_in_schema=False)
def admin_root() -> RedirectResponse:
    """Redirect from admin root to certifications management page."""
    return RedirectResponse(url="/admin/certs", status_code=302)


@router.get("/login", response_class=HTMLResponse)
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
        },
    )
    set_csrf_cookie(response, csrf_token)
    return response


@router.post("/certs", response_class=HTMLResponse)
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
