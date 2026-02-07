# Admin User Setup

This document explains how the admin authentication system works and how to configure it.

## Overview

The application uses **FastAPI Users** for authentication, providing secure JWT-based login for admin access to protected routes like `/status` and `/admin/*`.

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

When an unauthenticated user tries to access `/status` or `/admin/*`:

```text
GET /status → 401 Unauthorized → Redirect to /admin/login?next=/status
```

### 2. Login Process

1. User visits `/admin/login`
2. Enters username and password
3. Form submits to `/auth/jwt/login` (FastAPI Users endpoint)
4. On success: Redirects back to original page (via `?next=` parameter)
5. On failure: Shows error message on login form

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
    hashed_password: str        # bcrypt hashed
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

- Passwords are hashed using **bcrypt** (via passlib)
- Compatible bcrypt version: `4.1.3` (pinned in requirements.txt)
- Hashes are salted and use bcrypt's adaptive cost factor
- Plain-text passwords are never stored

## Troubleshooting

### "Internal Server Error" on Login

**Cause**: bcrypt version incompatibility

**Solution**: Ensure `bcrypt==4.1.3` is installed
```bash
pip install bcrypt==4.1.3
```

### "User Not Found" After Entering Correct Password

**Cause**: Admin user not created in database

**Solution**: Check startup logs for admin user creation:
```bash
python -m uvicorn fitness.main:app --reload
# Look for: "✅ Created admin user: admin"
```

### Can't Access `/status` Page

**Cause**: Not logged in

**Solution**:
1. Visit http://example.com:8000/status
2. You'll be redirected to `/admin/login?next=/status`
3. Enter your credentials from `.env`
4. After login, you'll be redirected back to `/status`

## Protected Routes

The following routes require admin authentication:

| Route | Description |
|-------|-------------|
| `/status` | System status dashboard with Bokeh charts |
| `/admin/` | Redirects to `/admin/certs` |
| `/admin/certs` | Certification management interface |
| `/admin/login` | Login page (public) |

## Security Best Practices

1. **Change default credentials** in `.env` before deploying
2. **Use strong passwords** (12+ characters, mixed case, numbers, symbols)
3. **Rotate SECRET_KEY** periodically
4. **Enable HTTPS** in production (`ENVIRONMENT=production`)
5. **Set secure cookie flags** (automatic in production)
6. **Monitor failed login attempts** (check application logs)
7. **Keep bcrypt updated** (but pinned for compatibility)

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
admin_paths = ["/status", "/admin"]
if any(request.url.path.startswith(path) for path in admin_paths):
    next_url = quote(str(request.url.path))
    login_url = f"/admin/login?next={next_url}"
    return RedirectResponse(url=login_url, status_code=302)
```

## References

- [FastAPI Users Documentation](https://fastapi-users.github.io/fastapi-users/)
- [Passlib bcrypt Handler](https://passlib.readthedocs.io/en/stable/lib/passlib.hash.bcrypt.html)
- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)
