# Admin User Setup

This document explains how the admin authentication system works and how to configure it.

## Overview

The application uses **FastAPI Users** for authentication, providing secure JWT-based login for admin access to protected routes under `/admin/*`.

## Configuration

### Environment Variables

Admin credentials are configured in `.env`:

```bash
# Security - Admin Credentials
ADMIN_USERNAME=admin@yourdomain.com
ADMIN_PASSWORD=your-secure-password-here
SECRET_KEY=your-secret-key-for-jwt-signing

# Database
DATABASE_URL=sqlite:///./data/fitness.db

# Astrometrics (optional — NASA DEMO_KEY used when unset)
NASA_API_KEY=
```

**Important Security Notes:**
- `ADMIN_USERNAME`: **Must be a valid email address** (e.g., `admin@yourdomain.com`)
- `ADMIN_PASSWORD`: Should be a strong password (min 8 chars recommended)
- `SECRET_KEY`: Used for JWT token signing (generate with `openssl rand -hex 32`)
- Never commit `.env` to version control (already in `.gitignore`)

### Auto-Creation on Startup

The admin user is **automatically created on first application startup** if it doesn't exist. This happens in `fitness/main.py:143-176` during the application lifespan initialization.

The startup process:
1. Database is initialized
2. Certifications are seeded from PDFs
3. **Admin user is created** from `ADMIN_USERNAME` and `ADMIN_PASSWORD` if not present
4. Application marks as ready

## Authentication Flow

### 1. Accessing Protected Routes

When an unauthenticated user tries to access `/admin/*`:

```text
GET /admin → 401 Unauthorized → Redirect to /admin/login?next=/admin
```

### 2. Login Process

1. User visits `/admin/login`
2. Enters username and password
3. Form submits to `/auth/jwt/login` (FastAPI Users endpoint)
4. On success: Redirects to the **Admin Dashboard** (`/admin`)
5. On failure: Shows error message on login form

### 3. Admin Dashboard

After login, users land on a centralized dashboard at `/admin` with navigation cards:

- **Operational Status** — System metrics, Bokeh charts, response times, error rates, and deployment info
- **Certification Management** — Add, update, deprecate, and manage professional certifications and PDF files
- **Tactical** — CVE advisories, severity breakdowns, and security intelligence from NIST NVD
- **Captain's Log** — TNG-styled project status entries with stardates, backed by the blog infrastructure
- **Media Management** — Upload videos and images to S3, served via CloudFront CDN with MIME type and file size validation
- **Astrometrics** — NASA Astronomy Picture of the Day (APOD) and Near-Earth Object (NEO) close-approach data

Every admin page includes:
- **Navigation bar** with links to Dashboard, Operational Status, Certifications, Media, Tactical, Captain's Log, and Astrometrics
- **Active page indicator** (highlighted nav link)
- **User badge** showing the logged-in user's email
- **Sign out button** on every page

### 3. Session Management

- Authentication uses **HTTP-only cookies** for security
- Cookie name: `fitness-auth` (configurable via `AUTH_COOKIE_NAME`)
- JWT lifetime: 1 hour (configurable via `JWT_LIFETIME_SECONDS`)
- Secure flag enabled in production (`ENVIRONMENT=production`)

## Manual User Creation

If needed, you can manually create users using the provided script:

```bash
# From project root
python tools/create_admin_user.py
```

This script reads from the same `.env` variables and creates the admin user.

## Database Schema

Users are stored in the `users` table with the following schema:

```python
class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"
    id: UUID                    # Auto-generated
    email: str                  # Used as username
    hashed_password: str        # Argon2id hashed (pwdlib)
    is_active: bool            # Account active status
    is_superuser: bool         # Admin privileges
    is_verified: bool          # Email verification status
    first_name: str | None     # Optional
    last_name: str | None      # Optional
```

Admin users created on startup have:
- `is_superuser=True`
- `is_verified=True`
- `is_active=True`

## Password Security

- Passwords are hashed using **pwdlib** (bundled with fastapi-users 15.x)
- Default algorithm: Argon2id (with bcrypt backward compatibility)
- Plain-text passwords are never stored

## Troubleshooting

### "Internal Server Error" on Login

**Cause**: Missing password hashing library

**Solution**: Ensure `pwdlib` is installed (transitive dep of fastapi-users)
```bash
uv sync
```

### "User Not Found" After Entering Correct Password

**Cause**: Admin user not created in database

**Solution**: Check startup logs for admin user creation:
```bash
python -m uvicorn fitness.main:app --reload
# Look for: "✅ Created admin user: admin"
```

### Can't Access Status Page

**Cause**: Not logged in

**Solution**:
1. Visit http://example.com:8000/admin/status
2. You'll be redirected to `/admin/login?next=/admin/status`
3. Enter your credentials from `.env`
4. After login, you'll be redirected back to the status page

## Protected Routes

The following routes require admin authentication:

| Route | Description |
|-------|-------------|
| `/admin/` | Admin dashboard with navigation cards |
| `/admin/status/` | Operational status with Bokeh charts |
| `/admin/certs` | Certification management interface |
| `/admin/tactical/dashboard` | CVE advisories and security intelligence |
| `/admin/tactical/advisories` | Advisory data API (JSON) |
| `/admin/tactical/stats` | Advisory statistics API (JSON) |
| `/admin/log` | Captain's Log dashboard (entry list) |
| `/admin/log/entry/{slug}` | Individual Captain's Log entry view |
| `/admin/media` | Media management dashboard (GET) |
| `/admin/media` | Media upload endpoint (POST) |
| `/admin/astrometrics` | Astrometrics lab (NASA APOD + NEO data) |
| `/admin/astrometrics/refresh` | Force-refresh cached NASA data (POST) |
| `/admin/login` | Login page (public) |

## Security Best Practices

1. **Change default credentials** in `.env` before deploying
2. **Use strong passwords** (12+ characters, mixed case, numbers, symbols)
3. **Rotate SECRET_KEY** periodically
4. **Enable HTTPS** in production (`ENVIRONMENT=production`)
5. **Set secure cookie flags** (automatic in production)
6. **Monitor failed login attempts** (check application logs)
7. **Keep dependencies updated** (`uv sync` to pick up security patches)

## API Endpoints

FastAPI Users provides these authentication endpoints:

- `POST /auth/jwt/login` - Login and get JWT token
- `POST /auth/jwt/logout` - Logout and invalidate token
- `POST /auth/register` - Register new user (may be disabled)
- `GET /users/me` - Get current user info

## For Developers

### Adding More Protected Routes

```python
from fitness.auth import current_active_user
from fastapi import Depends

@router.get("/my-protected-route")
async def my_route(user=Depends(current_active_user)):
    # Only authenticated users can access this
    return {"message": f"Hello {user.email}"}
```

### Customizing Login Redirect

The redirect logic is in `fitness/main.py:232-254` (HTTP exception handler):

```python
# For admin-protected pages, redirect to login instead of showing error
admin_paths = ["/admin"]
if any(request.url.path.startswith(path) for path in admin_paths):
    next_url = quote(str(request.url.path))
    login_url = f"/admin/login?next={next_url}"
    return RedirectResponse(url=login_url, status_code=302)
```

## References

- [FastAPI Users Documentation](https://fastapi-users.github.io/fastapi-users/)
- [pwdlib (password hashing)](https://github.com/frankie567/pwdlib)
- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)
