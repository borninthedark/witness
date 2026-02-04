"""
FastAPI Application - Resume & Certification Platform
"""

from __future__ import annotations

import hashlib
import io
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import qrcode
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from fitness.auth import auth_backend, fastapi_users
from fitness.config import settings
from fitness.constants import CERT_METADATA, get_cert_metadata
from fitness.database import Base, engine, get_db

# Collision-free imports
from fitness.middleware.security import SecurityHeadersMiddleware
from fitness.models.certification import Certification
from fitness.models.user import User  # noqa: F401 - needed for metadata
from fitness.observability.logging import configure_logging
from fitness.observability.metrics import MetricsMiddleware, metrics_response
from fitness.observability.tracing import configure_tracing
from fitness.routers.admin import router as admin_router
from fitness.routers.api import router as api_router
from fitness.routers.blog import router as blog_router
from fitness.routers.contact import router as contact_router
from fitness.routers.reports import router as reports_router
from fitness.routers.security_dashboard import router as security_router
from fitness.routers.status import router as status_router
from fitness.routers.ui import router as ui_router
from fitness.schemas.user import UserCreate, UserRead, UserUpdate
from fitness.security import limiter
from fitness.staticfiles import CachedStaticFiles


# ==========================================
# Database Initialization & Seeding
# ==========================================
def init_database() -> None:
    Base.metadata.create_all(bind=engine)


def _slug_variants(slug: str) -> set[str]:
    return {slug, slug.lower(), slug.upper()}


def seed_certifications_from_pdfs(db: Session) -> int:
    cert_dir = Path("fitness/static/certs")
    if not cert_dir.exists():
        return 0
    added_count = 0
    for pdf_path in cert_dir.glob("*.pdf"):
        slug = pdf_path.stem
        slug_candidates = list(_slug_variants(slug))
        existing = (
            db.query(Certification)
            .filter(Certification.slug.in_(slug_candidates))
            .first()
        )
        if existing:
            continue
        try:
            metadata = get_cert_metadata(slug)
            sha256_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
            dns_name = f"_cert.{slug}.princetonstrong.online"
            title = metadata.get("title", slug.replace("-", " ").title())
            issuer = metadata.get("issuer", "Uploaded PDF")
            verification_url = metadata.get("verification_url", "")
            assertion_url = metadata.get("assertion_url", "")
            certification = Certification(
                slug=slug,
                title=title,
                issuer=issuer,
                pdf_url=f"/static/certs/{pdf_path.name}",
                sha256=sha256_hash,
                dns_name=dns_name,
                verification_url=verification_url,
                assertion_url=assertion_url,
            )
            db.add(certification)
            added_count += 1
        except Exception as exc:
            print(f"Error processing {pdf_path.name}: {exc}")
            continue
    if added_count > 0:
        db.commit()
    return added_count


def sync_certification_metadata(db: Session) -> dict[str, int]:
    updated_titles = updated_issuers = updated_urls = updated_assertions = 0
    for slug, metadata in CERT_METADATA.items():
        slug_candidates = list(_slug_variants(slug))
        cert = (
            db.query(Certification)
            .filter(Certification.slug.in_(slug_candidates))
            .first()
        )
        if not cert:
            continue
        if "title" in metadata and cert.title != metadata["title"]:
            cert.title = metadata["title"]
            updated_titles += 1
        if "issuer" in metadata and cert.issuer != metadata["issuer"]:
            cert.issuer = metadata["issuer"]
            updated_issuers += 1
        if (
            "verification_url" in metadata
            and cert.verification_url != metadata["verification_url"]
        ):
            cert.verification_url = metadata["verification_url"]
            updated_urls += 1
        if (
            "assertion_url" in metadata
            and cert.assertion_url != metadata["assertion_url"]
        ):
            cert.assertion_url = metadata["assertion_url"]
            updated_assertions += 1
    if any((updated_titles, updated_issuers, updated_urls, updated_assertions)):
        db.commit()
    return {
        "titles_updated": updated_titles,
        "issuers_updated": updated_issuers,
        "verification_urls_updated": updated_urls,
        "assertion_urls_updated": updated_assertions,
    }


# ==========================================
# Application Lifespan
# ==========================================
async def create_admin_user_on_startup():
    """Create admin user from environment variables."""
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    from fitness.auth import UserManager
    from fitness.database_async import AsyncSessionLocal
    from fitness.models.user import User
    from fitness.schemas.user import UserCreate

    async with AsyncSessionLocal() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        user_manager = UserManager(user_db)

        # Check if admin user already exists
        try:
            existing = await user_manager.get_by_email(settings.admin_username)
            if existing:
                print(f"✅ Admin user '{settings.admin_username}' exists")
                return
        except Exception:
            pass

        # Create admin user
        try:
            user = await user_manager.create(
                UserCreate(
                    email=settings.admin_username,
                    password=settings.admin_password,
                    is_superuser=True,
                    is_verified=True,
                )
            )
            print(f"✅ Created admin user: {user.email}")
        except Exception as e:
            print(f"⚠️  Could not create admin user: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting application...")
    init_database()
    with next(get_db()) as db:
        added = seed_certifications_from_pdfs(db)
        if added > 0:
            print(f"✅ Seeded {added} new certification(s)")
        updates = sync_certification_metadata(db)
        if sum(updates.values()) > 0:
            print(f"✅ Synced certification metadata: {updates}")

    # Create admin user if it doesn't exist
    await create_admin_user_on_startup()

    print("✨ Application ready!")
    yield
    print("👋 Shutting down application...")


# ==========================================
# Environment & CSP (list-based, matches middleware API)
# ==========================================
configure_logging(settings.log_level.upper())
IS_PROD = getattr(settings, "environment", "").lower() in {"prod", "production"}
# Strict (self-hosted, no inline) vs Transitional (CDNs/inline allowed)
CSP_DIRECTIVES_STRICT = [
    "default-src 'self'",
    "base-uri 'none'",
    "frame-ancestors 'self'",
    "object-src 'self'",  # CRITICAL: Allow PDFs to be embedded/downloaded
    "img-src 'self' data: https://www.credly.com https://cdn.credly.com",
    "font-src 'self' https://fonts.gstatic.com",
    "style-src 'self' https://fonts.googleapis.com",
    (
        "script-src 'self' https://www.google.com/recaptcha/ "
        "https://www.gstatic.com/recaptcha/"
    ),
    (
        "frame-src 'self' https://www.google.com/recaptcha/ "
        "https://recaptcha.google.com/recaptcha/ "
        "https://www.credly.com https://formspree.io"
    ),
    "connect-src 'self' https://formspree.io",
    "form-action 'self'",
    "upgrade-insecure-requests",
]
CSP_DIRECTIVES_TRANSITIONAL = [
    "default-src 'self'",
    "base-uri 'none'",
    "frame-ancestors 'self'",
    "object-src 'self'",  # CRITICAL: Allow PDFs to be embedded/downloaded
    "img-src 'self' data: https://www.credly.com https://cdn.credly.com",
    ("font-src 'self' data: https://fonts.gstatic.com " "https://cdn.credly.com"),
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    (
        "script-src 'self' 'unsafe-inline' "
        "https://www.google.com/recaptcha/ "
        "https://www.gstatic.com/recaptcha/ https://unpkg.com "
        "https://cdn.tailwindcss.com https://cdn.credly.com "
        "https://cdn.bokeh.org "
        "https://formspree.io"
    ),
    (
        "frame-src 'self' https://www.google.com/recaptcha/ "
        "https://recaptcha.google.com/recaptcha/ "
        "https://www.credly.com"
    ),
    "connect-src 'self' https://formspree.io",
    "form-action 'self'",
    "upgrade-insecure-requests",
]
CSP_DIRECTIVES = CSP_DIRECTIVES_STRICT if IS_PROD else CSP_DIRECTIVES_TRANSITIONAL


# ==========================================
# Exception handlers (define BEFORE registration)
# ==========================================
# Import templates from staticfiles (already configured with asset_url)
from fitness.staticfiles import templates  # noqa: E402


async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    accepts_html = "text/html" in request.headers.get("accept", "").lower()
    payload = {"detail": "Rate limit exceeded. Please retry shortly."}
    if accepts_html:
        return HTMLResponse(
            "<h2>Too Many Requests</h2><p>Please retry shortly.</p>",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return JSONResponse(payload, status_code=status.HTTP_429_TOO_MANY_REQUESTS)


async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom handler for HTTPException to return LCARS-styled error pages."""
    accepts_html = "text/html" in request.headers.get("accept", "").lower()

    # Handle 401/403 Unauthorized/Forbidden errors
    if exc.status_code in (401, 403) and accepts_html:
        # For admin-protected pages, redirect to login instead of showing error
        admin_paths = ["/admin"]
        if any(request.url.path.startswith(path) for path in admin_paths):
            # Preserve the original URL to redirect back after login
            from urllib.parse import quote

            from fastapi.responses import RedirectResponse

            next_url = quote(str(request.url.path))
            login_url = f"/admin/login?next={next_url}"
            return RedirectResponse(url=login_url, status_code=302)

        # For other 401/403, show the error page
        return templates.TemplateResponse(
            "401.html",
            {"request": request},
            status_code=exc.status_code,
        )

    # Handle 404 errors with custom template
    if exc.status_code == 404 and accepts_html:
        return templates.TemplateResponse(
            "404.html",
            {"request": request},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Handle 503 Service Unavailable with custom template
    if exc.status_code == 503 and accepts_html:
        return templates.TemplateResponse(
            "503.html",
            {"request": request},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    # For non-HTML requests or other status codes, return JSON
    return JSONResponse(
        {"detail": exc.detail},
        status_code=exc.status_code,
    )


# ==========================================
# FastAPI Application
# ==========================================
app = FastAPI(
    title="Captain's Fitness Log",
    description="Resume & Certification Platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
    openapi_url=None if IS_PROD else "/openapi.json",
)
# Order: compression → rate-limit/metrics → security → correlation id
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(
    SecurityHeadersMiddleware,
    csp_directives=CSP_DIRECTIVES,  # aligns with middleware API
    use_nonce=False,  # keep False while 'unsafe-inline' is present
    referrer_policy="strict-origin-when-cross-origin",
    permissions_policy="geolocation=(), microphone=(), camera=()",
    frame_options="SAMEORIGIN",  # allow same-origin PDF iframes
)
app.add_middleware(CorrelationIdMiddleware, header_name="X-Request-ID")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
# CORS: strict allowlist
allowed_origins = getattr(settings, "cors_origins", []) or [
    "https://engage.princetonstrong.online"
]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type", "Authorization"],
    )
# Static files
app.mount("/static", CachedStaticFiles(directory="fitness/static"), name="static")
# Optional tracing
if settings.enable_tracing and settings.otlp_endpoint:
    configure_tracing(
        app, engine, "fitness-app", settings.otlp_endpoint, settings.otlp_headers
    )


# ==========================================
# Health & readiness (minimal in prod)
# ==========================================
@app.get("/healthz", tags=["system"], summary="Health check", response_model=dict)
async def health_check(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        if IS_PROD:
            return {"status": "healthy"}
        return {"status": "healthy", "database": "connected", "version": app.version}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="unhealthy"
        )


@app.get("/readyz", tags=["system"], summary="Readiness check", response_model=dict)
async def readiness_check(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        if IS_PROD:
            return {"status": "ready"}
        data_dir_ok = Path(settings.data_dir).exists()
        if not data_dir_ok:
            raise RuntimeError(f"Data dir missing: {settings.data_dir}")
        return {"status": "ready", "database": "connected", "data_dir": "available"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )


# ==========================================
# Metrics (Protected with HTTP Basic Auth)
# ==========================================
security = HTTPBasic()


def verify_metrics_auth(
    credentials: HTTPBasicCredentials = Depends(security),
) -> str:
    """Verify HTTP Basic Auth credentials for metrics endpoint."""
    if not settings.metrics_password:
        # If no password is set, allow access (backwards compatible)
        return credentials.username

    correct_username = secrets.compare_digest(
        credentials.username, settings.metrics_username
    )
    correct_password = secrets.compare_digest(
        credentials.password, settings.metrics_password
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/metrics", include_in_schema=False)
def metrics(_: str = Depends(verify_metrics_auth)):
    """
    Prometheus metrics endpoint (protected with HTTP Basic Auth).

    Set METRICS_USERNAME and METRICS_PASSWORD environment variables.
    """
    return metrics_response()


# ==========================================
# QR Codes
# ==========================================
@app.get(
    "/q/{slug}.png",
    tags=["qr"],
    summary="Generate QR code for certification",
    response_class=StreamingResponse,
)
async def generate_qr_code(
    slug: str, db: Session = Depends(get_db)
) -> StreamingResponse:
    url = f"{settings.base_url}/v/{slug}"

    try:
        cert = db.query(Certification).filter(Certification.slug == slug).first()
        if cert and cert.verification_url:
            url = cert.verification_url
        else:
            metadata = get_cert_metadata(slug)
            if metadata.get("verification_url"):
                url = metadata["verification_url"]
    except Exception as e:
        print(f"Warning: Failed to query cert for QR code {slug}: {e}")
        # Continue with default URL
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Disposition": f'inline; filename="{slug}.png"',
        },
    )


# ==========================================
# Routers
# ==========================================
app.include_router(ui_router)
app.include_router(reports_router)
app.include_router(api_router)
app.include_router(admin_router)
app.include_router(contact_router)
app.include_router(blog_router)
app.include_router(security_router)
app.include_router(status_router)
# Auth
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)
