# Test Suite Documentation

This document describes the test suite structure, coverage goals, and testing practices for the Captain's Fitness Log application.

## Overview

**Current Coverage:** 62.77% (target: 80%+)
**Test Framework:** pytest with coverage plugins
**Test Count:** ~35 tests (expanding)

## Test Structure

```text
tests/
├── README.md                    # This file
├── conftest.py                  # Shared fixtures and test configuration
├── test_constants.py            # Certification metadata tests
├── test_dry.py                  # Code duplication enforcement
├── test_integration.py          # End-to-end integration tests
├── test_smoke.py                # Basic smoke tests
├── test_app_client.py           # API client tests
├── test_report_status.py        # Report status service tests
├── security/                    # Security module tests
│   └── test_csrf.py            # CSRF protection tests (100% coverage)
└── routers/                     # Router/endpoint tests
    └── test_ui.py              # UI route tests
```

## Running Tests

### Basic Usage

```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_smoke.py

# Run specific test
pytest tests/test_smoke.py::test_health_check

# Run with verbose output
pytest -v

# Run in parallel (faster)
pytest -n auto
```

### Coverage Reports

```bash
# Terminal report with missing lines
pytest --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov-report=html
open htmlcov/index.html

# JSON report for CI/CD
pytest --cov-report=json
```

### Environment Setup

Tests use SQLite by default:

```bash
export DATABASE_URL="sqlite:///test_app.db"
pytest
```

## Test Categories

### Smoke Tests (`test_smoke.py`)

Basic application health checks:
- `/healthz` endpoint returns 200
- Homepage loads with expected content
- Contact page renders
- Certificate PDF viewer works

**Coverage target:** Core endpoints functional

### Integration Tests (`test_integration.py`)

End-to-end workflows:
- Certificate deduplication logic
- Resume PDF generation and streaming
- Contact form submission with CSRF

**Coverage target:** Critical user journeys

### Unit Tests (Module-specific)

#### Security Tests (`security/test_csrf.py`)

CSRF protection mechanisms:
- Token generation and reuse
- Cookie setting (secure in production, not in debug)
- Token validation and verification
- Header-based token extraction
- Attack scenarios (tampering, missing tokens, mismatches)

**Coverage:** fitness/security/csrf.py → 100%

#### Router Tests (`routers/test_ui.py`)

UI endpoint behavior:
- Template rendering with CSRF tokens
- Certificate listing and filtering
- Resume download endpoints
- Contact form validation

**Coverage target:** fitness/routers/ui.py → 80%+

### Code Quality Tests

#### DRY Enforcement (`test_dry.py`)

Detects code duplication in `fitness/` module:
- Minimum 6 lines to flag
- 80% similarity threshold
- Function-level analysis

**Purpose:** Prevent copy-paste programming

#### Constants Tests (`test_constants.py`)

Certification metadata integrity:
- Case-insensitive slug lookup
- Badge URL validation
- Verification endpoint presence
- Issuer metadata completeness

**Purpose:** Ensure cert data consistency

## Coverage Goals

### Phase 1: Foundation (✅ Complete)

- Install pytest-cov and plugins
- Configure pyproject.toml
- Establish baseline: 45.93%

### Phase 2: Quick Wins (✅ Complete)

**Achieved:** 62.77% coverage (+16.84pp)

- ✅ Security module (csrf.py): 0% → 100%
- ✅ Services (pdf_resume.py): 14.72% → 90.48%
- ✅ Routers (ui.py): 31.95% → 59.02%

### Phase 3: Core Coverage (📋 Next)

**Target: 80% coverage** | **Estimated Effort: 16-22 hours**

Breaking into sub-phases for incremental progress:

#### Phase 3A: Quick Win - Security Middleware (2-3 hours) → ~65%

- **fitness/middleware/security.py**: 77.22% → 90%
  - Security headers (CSP, HSTS, X-Frame-Options)
  - Request/response middleware behavior
  - Error scenarios

#### Phase 3B: Admin Router (4-6 hours) → ~70%

- **fitness/routers/admin.py**: 39.18% → 80%
  - Admin authentication/authorization
  - Certificate CRUD operations
  - User management endpoints
  - File upload handling
  - **Why critical:** Security-sensitive admin operations

#### Phase 3C: Storage & Badge Services (7-9 hours) → ~78%

- **fitness/services/storage.py**: 39.13% → 80%
  - Azure Blob storage operations
  - File upload/download
  - Network failure handling
  - Mock Azure SDK calls
- **fitness/services/open_badges.py**: 25.89% → 80%
  - Badge assertion generation
  - JSON-LD formatting
  - Cryptographic signing
  - Verification endpoint logic

#### Phase 3D: Model Layer (3-4 hours) → ~82%

- **fitness/models/certification.py**: New tests
  - ORM model behavior
  - Field validation
  - Relationships and queries
- **fitness/models/user.py**: New tests
  - User model validation
  - Authentication integration

**Success Criteria:**
- ✅ Overall coverage ≥ 80%
- ✅ All security-critical modules ≥ 90%
- ✅ No module below 60% (unless explicitly exempted)
- ✅ All admin and storage operations tested

### Phase 4A: Coverage Completion (📋 Future)

**Target: 90% coverage** | **Estimated Effort: 8-10 hours**

Remaining untested/undertested modules:
- **fitness/routers/api.py** - API endpoints
- **fitness/routers/contact.py** - Contact form handling
- **fitness/routers/reports.py** - Report generation endpoints
- **fitness/services/security_feed.py** - Security feed service
- **fitness/services/report_status.py** - Expand existing tests
- **fitness/observability/** - Logging, metrics, tracing
- **fitness/auth.py** - Authentication logic
- **fitness/config.py** - Configuration validation

**Success Criteria:**
- ✅ Overall coverage ≥ 90%
- ✅ All routers tested
- ✅ All services have comprehensive tests
- ✅ Observability stack verified

### Phase 4B: Advanced Testing Techniques (📋 Optional)

**Purpose:** Improve test quality and catch edge cases

These are **optional enhancements** - adopt selectively based on project needs:

#### Priority 1: Mutation Testing (Recommended)

**Tool:** mutmut==2.4.0 | **Effort:** 2-3 hours setup + 1 hour per module
- **Purpose:** Find weak tests that pass even when code is broken
- **Where:** All modules after reaching 80%+ coverage
- **Value:** Improves test quality, not just coverage percentage

#### Priority 2: Contract Testing (High Value)

**Tool:** schemathesis==3.26.0 | **Effort:** 3-4 hours
- **Purpose:** Auto-generate tests from OpenAPI schema
- **Where:** fitness/routers/api.py
- **Value:** Prevents API regressions and schema drift

#### Priority 3: Property-Based Testing (Selective)

**Tool:** hypothesis==6.92.0 | **Effort:** 4-6 hours
- **Where:** fitness/security/csrf.py (timing attack resistance)
- **Where:** fitness/services/open_badges.py (JSON-LD invariants)
- **Value:** Tests with random inputs to find unexpected bugs

#### Priority 4: Performance Regression Tests (As-Needed)

**Tool:** pytest-benchmark==4.0.0 | **Effort:** 3-4 hours
- **Where:** Performance-critical paths only
  - PDF generation (fitness/services/pdf_resume.py)
  - Database queries (certification listing)
  - Badge assertion generation
- **Value:** Detect performance degradation over time

**Note:** Complete Phase 4A (90% coverage) before adopting Phase 4B techniques.

## Writing New Tests

### Test Naming Convention

```python
# Pattern: test_<what>_<scenario>
def test_health_check_returns_200():
    """Test that /healthz endpoint returns 200 status."""
    pass

def test_csrf_token_rejects_tampering():
    """Test CSRF validation fails when signature is tampered."""
    pass
```

### Using Fixtures

```python
from tests.conftest import client, db_session

def test_with_database(client, db_session):
    """Use the test client and database session."""
    # client: FastAPI TestClient with SQLite backend
    # db_session: SQLAlchemy Session for test database
    pass
```

### Mocking External Dependencies

```python
from unittest.mock import patch, MagicMock

def test_mailer_handles_smtp_failure(monkeypatch):
    """Test graceful handling of SMTP errors."""
    monkeypatch.setattr("fitness.services.mailer.smtplib.SMTP", MagicMock(side_effect=ConnectionError))
    # Test error handling
```

### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_endpoint():
    """Test async endpoints with pytest-asyncio."""
    result = await some_async_function()
    assert result is not None
```

## Common Test Patterns

### Testing Routes

```python
def test_route_returns_expected_status(client):
    response = client.get("/endpoint")
    assert response.status_code == 200
    assert "expected content" in response.text
```

### Testing CSRF Protection

```python
def test_csrf_protected_route(client):
    # Get CSRF token from page
    response = client.get("/contact")
    token = client.cookies.get("csrf_token")

    # Submit form with token
    response = client.post("/contact", data={
        "csrf_token": token,
        "message": "test"
    })
    assert response.status_code == 200
```

### Testing Database Operations

```python
from fitness.models.certification import Certification

def test_certification_creation(db_session):
    cert = Certification(
        slug="test-cert",
        title="Test Certification",
        issuer="Test Issuer",
        sha256="abc123",
    )
    db_session.add(cert)
    db_session.commit()

    assert db_session.query(Certification).count() == 1
```

## CI/CD Integration

### GitHub Actions

Tests run automatically on:
- Every push to `main`
- Every pull request
- Weekly schedule (Sunday 2 AM UTC)

See `.github/workflows/data.yml` for configuration.

### Pre-commit Hooks

**Note:** pytest hook is currently disabled in `.pre-commit-config.yaml` (line 113).

To enable:
```yaml
- repo: local
  hooks:
    - id: pytest
      name: pytest
      entry: scripts/precommit_log.sh
      args: ['pytest', '.venv/bin/pytest']
      language: system
      pass_filenames: false
```

## Coverage Analysis

### View Coverage Report

```bash
# Generate and open HTML report
pytest --cov-report=html
open htmlcov/index.html
```

### Identify Untested Code

```bash
# Show missing lines
pytest --cov-report=term-missing

# Skip fully covered files
pytest --cov-report=term-missing:skip-covered
```

### Module-Specific Coverage

```bash
# Test only routers module
pytest tests/routers/ --cov=fitness.routers

# Test security with detailed report
pytest tests/security/ --cov=fitness.security --cov-report=term-missing
```

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError`:
```bash
# Ensure project root is in PYTHONPATH
export PYTHONPATH="${PWD}:${PYTHONPATH}"
pytest
```

### Database Errors

If tests fail with database connection errors:
```bash
# Use SQLite with a local test database
export DATABASE_URL="sqlite:///test_app.db"
pytest
```

### Async Warnings

If you see `RuntimeWarning: coroutine was never awaited`:
```python
# Mark test as async
@pytest.mark.asyncio
async def test_async_function():
    result = await async_call()
```

## Best Practices

### 1. Test Isolation

- Each test should be independent
- Use fixtures for setup/teardown
- Don't rely on test execution order

### 2. Clear Assertions

```python
# Good
assert response.status_code == 200, "Health check should return 200"

# Better
assert response.status_code == 200
assert response.json()["status"] == "healthy"
```

### 3. Test One Thing

```python
# Avoid
def test_everything():
    test_health()
    test_database()
    test_email()

# Prefer
def test_health_endpoint_returns_200():
    ...

def test_database_connection_succeeds():
    ...
```

### 4. Use Descriptive Names

```python
# Unclear
def test_login():
    ...

# Clear
def test_login_succeeds_with_valid_credentials():
    ...

def test_login_fails_with_invalid_password():
    ...
```

### 5. Mock External Services

- Don't make real HTTP requests in tests
- Don't send real emails
- Don't access real cloud services

## Contributing Tests

When adding new features:

1. Write tests alongside code (not after)
2. Aim for 80%+ coverage on new modules
3. Include edge cases and error scenarios
4. Update this documentation if adding new test categories

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov plugin](https://pytest-cov.readthedocs.io/)
- [FastAPI testing guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLAlchemy testing guide](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)

## Questions?

For test-related questions or issues:
- Check this documentation first
- Review existing tests for patterns
- See `docs/tooling.md` for general testing workflow
- Open an issue on GitHub for bugs or feature requests
