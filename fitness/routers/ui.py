import json
import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.templating import Jinja2Templates
from pydantic import EmailStr, ValidationError
from sqlalchemy.orm import Session

from fitness.config import settings
from fitness.constants import (
    INACTIVE_CERT_SLUGS,
    get_cert_metadata,
    verification_label_for_slug,
)
from fitness.database import get_db
from fitness.models.certification import Certification
from fitness.schemas.contact import ContactForm
from fitness.security import issue_csrf_token, limiter, set_csrf_cookie, validate_csrf
from fitness.utils.assets import asset_url

# Local and remote paths for the resume PDF
RESUME_STORAGE_DIR = Path("fitness/data")  # Local path to the resume
REMOTE_RESUME_URL = (
    "https://princetonstrong.com/PAS-Resume.pdf"  # URL of the remote resume PDF
)

CERT_STORAGE_DIR = Path("fitness/static/certs")

router = APIRouter()
templates = Jinja2Templates(directory="fitness/templates")
templates.env.globals["current_year"] = datetime.now(UTC).year
templates.env.globals["asset_url"] = asset_url


def _render_with_csrf(
    template_name: str,
    request: Request,
    context: dict,
    status_code: int = 200,
) -> HTMLResponse:
    token = issue_csrf_token(request)
    ctx = {"request": request, **context, "csrf_token": token}
    response = templates.TemplateResponse(template_name, ctx, status_code=status_code)
    set_csrf_cookie(response, token)
    return response


@router.get("/", response_class=HTMLResponse)
@limiter.limit("60/minute")
def home(request: Request, db: Session = Depends(get_db)):
    try:
        # Count only visible certifications for public display
        cert_count = (
            db.query(Certification).filter(Certification.is_visible.is_(True)).count()
        )
    except Exception as e:
        print(f"Warning: Failed to query certifications: {e}")
        cert_count = 0

    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header.lower():
        return templates.TemplateResponse(
            "home.html", {"request": request, "cert_count": cert_count}
        )
    return JSONResponse(
        {
            "message": "Captain's Fitness Log API",
            "docs": "/docs",
            "certifications": cert_count,
        }
    )


@router.get("/certs", response_class=HTMLResponse)
@limiter.limit("30/minute")
def certs(request: Request, db: Session = Depends(get_db)):
    try:
        # Only query visible certifications for public display
        all_certs = (
            db.query(Certification)
            .filter(Certification.is_visible.is_(True))
            .order_by(Certification.id.desc())
            .all()
        )
        seen_hashes: set[str] = set()
        unique_certs: list[Certification] = []
        for cert in all_certs:
            if cert.sha256 in seen_hashes:
                continue
            seen_hashes.add(cert.sha256)
            unique_certs.append(cert)
        active_certs: list[Certification] = []
        inactive_certs: list[Certification] = []
        for cert in unique_certs:
            # Use status field instead of hardcoded slug lists
            if cert.status == "active":
                active_certs.append(cert)
            else:  # deprecated or expired
                inactive_certs.append(cert)
        active_certs.sort(
            key=lambda c: getattr(c, "created_at", None) or c.id, reverse=True
        )
        inactive_certs.sort(
            key=lambda c: getattr(c, "created_at", None) or c.id, reverse=True
        )
    except Exception as e:
        print(f"Warning: Failed to query certifications: {e}")
        active_certs = []
        inactive_certs = []

    return templates.TemplateResponse(
        "certifications.html",
        {
            "request": request,
            "active_certs": active_certs,
            "inactive_certs": inactive_certs,
        },
    )


# Replace your existing cert_pdf and cert_pdf_inline functions in routers/ui.py


@router.get("/certs/{slug}/pdf", name="cert_pdf_view")
@limiter.limit("30/minute")
def cert_pdf(slug: str, request: Request, db: Session = Depends(get_db)):
    """
    Serve PDF directly with proper headers for inline viewing.
    Use ?download=1 to force download instead.
    """
    try:
        cert = db.query(Certification).filter(Certification.slug == slug).first()
    except Exception as e:
        print(f"Warning: Database query failed for cert {slug}: {e}")
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable"
        ) from e

    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    # Check if download is requested
    download = request.query_params.get("download", "0") == "1"

    # Try local file first
    candidate = CERT_STORAGE_DIR / f"{cert.slug}.pdf"

    if candidate.exists():
        disposition = "attachment" if download else "inline"
        headers = {
            "Content-Disposition": f'{disposition}; filename="{cert.slug}.pdf"',
            "X-Frame-Options": "SAMEORIGIN",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=3600, immutable",
            "Accept-Ranges": "bytes",
            # Minimal CSP to allow PDF viewing
            "Content-Security-Policy": (
                "default-src 'none'; object-src 'self'; frame-ancestors 'self'"
            ),
        }
        return FileResponse(
            candidate,
            media_type="application/pdf",
            filename=f"{cert.slug}.pdf",
            headers=headers,
        )

    # Fallback to remote URL if pdf_url exists
    if cert.pdf_url:
        try:
            resp = httpx.get(cert.pdf_url, timeout=10, follow_redirects=True)
            resp.raise_for_status()

            disposition = "attachment" if download else "inline"
            headers = {
                "Content-Disposition": f'{disposition}; filename="{cert.slug}.pdf"',
                "X-Frame-Options": "SAMEORIGIN",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "public, max-age=3600",
                "Content-Security-Policy": (
                    "default-src 'none'; object-src 'self'; frame-ancestors 'self'"
                ),
            }
            return Response(
                content=resp.content,
                media_type="application/pdf",
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=404, detail="Certificate PDF not available"
            ) from exc

    raise HTTPException(status_code=404, detail="Certificate PDF not found")


@router.get("/certs/{slug}/viewer", response_class=HTMLResponse)
@limiter.limit("30/minute")
def cert_pdf_viewer(slug: str, request: Request, db: Session = Depends(get_db)):
    """
    Optional: HTML page with embedded PDF viewer.
    Most users will use /certs/{slug}/pdf directly.
    """
    try:
        cert = db.query(Certification).filter(Certification.slug == slug).first()
    except Exception as e:
        print(f"Warning: Database query failed for cert viewer {slug}: {e}")
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable"
        ) from e

    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    # Check if file exists
    candidate = CERT_STORAGE_DIR / f"{cert.slug}.pdf"
    if not candidate.exists() and not cert.pdf_url:
        raise HTTPException(status_code=404, detail="Certificate PDF not available")

    pdf_url = request.url_for("cert_pdf_view", slug=slug)

    return templates.TemplateResponse(
        "certificate_pdf.html",
        {
            "request": request,
            "cert": cert,
            "pdf_url": str(pdf_url),
            "pdf_inline_url": str(pdf_url),  # Same URL now
        },
    )


@router.get("/resume/pdf", name="resume_pdf_view")
@limiter.limit("30/minute")
def resume_pdf(request: Request, db: Session = Depends(get_db)):
    """
    Serve the resume PDF directly with proper headers for inline viewing.
    Use ?download=1 to force download instead.
    """
    # Check if resume file exists locally
    candidate = RESUME_STORAGE_DIR / "PAS-Resume.pdf"

    if candidate.exists():
        # Check if download is requested
        download = request.query_params.get("download", "0") == "1"
        disposition = "attachment" if download else "inline"
        headers = {
            "Content-Disposition": f'{disposition}; filename="PAS-Resume.pdf"',
            "X-Frame-Options": "SAMEORIGIN",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "public, max-age=3600, immutable",
            "Accept-Ranges": "bytes",
        }
        return FileResponse(
            candidate,
            media_type="application/pdf",
            filename="PAS-Resume.pdf",
            headers=headers,
        )

    # Fallback to remote URL if the local file does not exist
    if REMOTE_RESUME_URL:
        try:
            resp = httpx.get(REMOTE_RESUME_URL, timeout=10, follow_redirects=True)
            resp.raise_for_status()

            # Check if download is requested
            download = request.query_params.get("download", "0") == "1"
            disposition = "attachment" if download else "inline"
            headers = {
                "Content-Disposition": f'{disposition}; filename="PAS-Resume.pdf"',
                "X-Frame-Options": "SAMEORIGIN",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "public, max-age=3600",
            }
            return Response(
                content=resp.content,
                media_type="application/pdf",
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=404, detail="Resume PDF not available"
            ) from exc

    raise HTTPException(status_code=404, detail="Resume PDF not found")


@router.get("/resume", response_class=HTMLResponse)
@limiter.limit("30/minute")
def resume_page(request: Request):
    """
    Serve a page with a PDF viewer for the resume, or offer the resume for download.
    """
    # Direct URL to the resume PDF view (same as the 'cert_pdf_view' page)
    pdf_url = request.url_for("resume_pdf_view")

    return templates.TemplateResponse(
        "resume.html",
        {
            "request": request,
            "pdf_download_url": f"{pdf_url}?download=1",  # Link to download
            "pdf_inline_url": pdf_url,  # Inline is the default (no param needed)
        },
    )


@router.get("/resume/go", include_in_schema=False)
@limiter.limit("30/minute")
def resume_shortcut_redirect(request: Request):
    """
    Human- and QR-friendly shortcut to the inline resume PDF.
    """
    return RedirectResponse(
        url="/resume/pdf?download=0",
        status_code=status.HTTP_302_FOUND,
    )


def _persist_contact_submission(payload: dict) -> None:
    try:
        store_dir = Path(settings.data_dir)
        store_dir.mkdir(parents=True, exist_ok=True)
        log_path = store_dir / "contact-messages.jsonl"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
    except Exception as e:
        print(f"Warning: Failed to persist contact submission: {e}")


@router.get("/contact", response_class=HTMLResponse)
@limiter.limit("10/minute")
def contact_page(request: Request, success: bool = False):
    return _render_with_csrf(
        "contact_lcars.html",
        request,
        {
            "success": success,
        },
    )


@router.post("/contact", response_class=HTMLResponse)
@limiter.limit("5/minute")
async def submit_contact(
    request: Request,
    background: BackgroundTasks,
    name: str = Form(...),
    email: EmailStr = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
    honeypot: str = Form(default=""),
    csrf_token: str = Form(...),
):
    template_name = "contact_lcars.html"
    validate_csrf(request, csrf_token)

    if honeypot:
        return _render_with_csrf(
            template_name,
            request,
            {
                "success": True,
            },
        )

    try:
        form_obj = ContactForm(
            name=name,
            email=email,
            subject=subject,
            message=message,
            honeypot=honeypot,
        )
    except ValidationError as exc:
        errors = "; ".join(error["msg"] for error in exc.errors())
        return _render_with_csrf(
            template_name,
            request,
            {
                "success": False,
                "error": errors,
            },
            status_code=422,
        )

    payload = {
        "name": form_obj.name,
        "email": str(form_obj.email),
        "subject": form_obj.subject,
        "message": form_obj.message,
        "received_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "ip": request.client.host if request.client else "",
    }
    _persist_contact_submission(payload)

    background.add_task(_deliver_contact_message, form_obj)

    # POST-Redirect-GET on success
    return RedirectResponse(
        url="/contact?success=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _deliver_contact_message(form_obj: ContactForm) -> None:
    if not (settings.smtp_host and settings.mail_from and settings.mail_to):
        print(f"[Contact] {form_obj.model_dump()}")
        return

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.mail_from
        msg["To"] = settings.mail_to
        msg["Subject"] = f"[Leeta Contact] {form_obj.subject}"
        body = f"From: {form_obj.name} <{form_obj.email}>\n\n{form_obj.message}"
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_starttls:
                server.starttls()
            if settings.smtp_user and settings.smtp_pass:
                server.login(settings.smtp_user, settings.smtp_pass)
            server.send_message(msg)
    except Exception as exc:  # pragma: no cover
        print(f"[Contact] delivery failed: {exc}")


@router.get("/v/{slug}", response_class=HTMLResponse)
@limiter.limit("30/minute")
def verify_cert(slug: str, request: Request, db: Session = Depends(get_db)):
    try:
        cert = db.query(Certification).filter(Certification.slug == slug).first()
    except Exception as e:
        print(f"Warning: Database query failed for verify cert {slug}: {e}")
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable"
        ) from e

    if not cert:
        return HTMLResponse("<h2>Not found</h2>", status_code=404)

    try:
        metadata = get_cert_metadata(slug)
        verification_label = verification_label_for_slug(slug, cert.issuer)
    except Exception as e:
        print(f"Warning: Failed to get cert metadata for {slug}: {e}")
        metadata = {}
        verification_label = "Certificate"
    return templates.TemplateResponse(
        "verification.html",
        {
            "request": request,
            "cert": cert,
            "verification_label": verification_label,
            "metadata": metadata,
            "is_inactive": slug in INACTIVE_CERT_SLUGS,
        },
    )


@router.get("/v/{slug}/go", include_in_schema=False)
@limiter.limit("30/minute")
def verify_cert_redirect(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Canonical redirect-style verification URL for QR codes / external systems.

    Priority:
    1. DB-driven verification_url
    2. Local PDF
    3. cert.pdf_url (remote)
    4. Fallback: HTML verification page
    """
    try:
        cert = db.query(Certification).filter(Certification.slug == slug).first()
    except Exception as e:
        print(f"Warning: Database query failed for verify redirect {slug}: {e}")
        raise HTTPException(
            status_code=503, detail="Service temporarily unavailable"
        ) from e

    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    # 1) DB verification_url if set
    if cert.verification_url:
        return RedirectResponse(
            url=cert.verification_url,
            status_code=status.HTTP_302_FOUND,
        )

    # 2) Local PDF
    local_pdf = CERT_STORAGE_DIR / f"{cert.slug}.pdf"
    if local_pdf.exists():
        return RedirectResponse(
            url=f"/certs/{cert.slug}/pdf",
            status_code=status.HTTP_302_FOUND,
        )

    # 3) Remote pdf_url if present
    if cert.pdf_url:
        return RedirectResponse(
            url=cert.pdf_url,
            status_code=status.HTTP_302_FOUND,
        )

    # 4) Fallback to your HTML verification page
    return RedirectResponse(
        url=f"/v/{slug}",
        status_code=status.HTTP_302_FOUND,
    )
