# Testing Guide

## Overview

This test suite provides comprehensive coverage for all routers in the Witness application, including the new Captain's Personal Log (blog) feature and all existing routers.

## Test Structure

```text
tests/
├── conftest.py                    # Test fixtures and configuration
├── routers/
│   ├── test_ui.py                # UI router tests (existing)
│   ├── test_blog.py              # Blog router tests (NEW)
│   └── test_all_routers.py       # Comprehensive router tests (NEW)
├── security/
│   └── test_csrf.py              # CSRF tests
├── test_401.py                   # 401 error handler tests
├── test_404.py                   # 404 error handler tests
├── test_503.py                   # 503 error handler tests
└── TESTING_GUIDE.md              # This file
```

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/routers/test_blog.py
```

### Run Specific Test

```bash
pytest tests/routers/test_blog.py::test_blog_index_returns_html
```

### Run With Coverage

```bash
pytest --cov=fitness --cov-report=html
```

### Run With Verbose Output

```bash
pytest -v
```

## Test Coverage

### Blog Router (`test_blog.py`) - 40+ Tests

**Index/List Tests:**
- ✅ Blog index returns HTML
- ✅ Shows published entries
- ✅ Hides draft entries
- ✅ Filter by category
- ✅ Filter by tag
- ✅ Pagination works correctly

**Single Entry Tests:**
- ✅ Entry view returns HTML
- ✅ Renders markdown to HTML
- ✅ Increments view count
- ✅ Shows related entries
- ✅ Returns 404 for nonexistent entries
- ✅ Returns 404 for draft entries

**Search Tests:**
- ✅ Search returns results
- ✅ Searches by title
- ✅ Searches by content
- ✅ Searches by tags
- ✅ Handles no results
- ✅ Only returns published entries
- ✅ Requires query parameter

**Category Filter Tests:**
- ✅ Returns filtered entries
- ✅ Handles invalid categories

**Stats Tests:**
- ✅ Shows statistics
- ✅ Shows categories
- ✅ Shows tags cloud

**Edge Cases:**
- ✅ Special characters in slug
- ✅ Entries without stardate
- ✅ Entries without tags
- ✅ Empty database
- ✅ Multiple page views

**Integration:**
- ✅ CSS loaded
- ✅ HTMX enabled
- ✅ All routes return correct status codes

### All Routers (`test_all_routers.py`) - 50+ Tests

**Admin Router:**
- ✅ Login page loads
- ✅ Requires authentication
- ✅ Status badge endpoint

**API Router:**
- ✅ Endpoints exist
- ✅ Certifications endpoint

**Contact Router:**
- ✅ Page loads
- ✅ Has form elements
- ✅ Validates input

**Reports Router:**
- ✅ Index loads
- ✅ Returns HTML or redirect

**Security Dashboard Router:**
- ✅ Dashboard loads
- ✅ Advisories endpoint
- ✅ Stats endpoint

**Status Router:**
- ✅ Status page loads
- ✅ Admin status page

**Health & System:**
- ✅ Health check endpoint
- ✅ Readiness check endpoint
- ✅ Metrics requires auth

**QR Code:**
- ✅ QR code generation

**Error Handlers:**
- ✅ 404 custom page
- ✅ 401/403 handlers

**Security:**
- ✅ Security headers present
- ✅ CSP header

**Static Files:**
- ✅ CSS accessible
- ✅ Blog CSS accessible

**Authentication:**
- ✅ JWT endpoints exist
- ✅ Registration endpoint
- ✅ Protected routes require auth

**Parametrized Tests:**
- ✅ All public routes accessible
- ✅ Protected routes require auth

**Infrastructure:**
- ✅ App can register new routes
- ✅ Middleware chain works
- ✅ Database connections work
- ✅ Rate limiting doesn't break usage
- ✅ Templates render correctly

### UI Router (`test_ui.py`) - 15+ Tests

- ✅ Home endpoint HTML/JSON responses
- ✅ Certification count
- ✅ Certifications page
- ✅ Deduplication by SHA256
- ✅ Hidden cert slugs
- ✅ Active/inactive separation
- ✅ Contact page CSRF
- ✅ Resume page
- ✅ Health checks
- ✅ Session maintenance

## Test Fixtures

### `client` (session scope)

Provides a TestClient with test database setup. All database changes are isolated to test database.

### `db_session`

Provides a database session for direct database operations in tests.

### `sample_blog_entry`

Creates a sample published blog entry for blog tests.

### `draft_blog_entry`

Creates a sample draft blog entry for testing draft behavior.

### `multiple_blog_entries`

Creates multiple blog entries across different categories for pagination and filtering tests.

## Writing New Tests

### Example: Testing a New Router

```python
from fastapi.testclient import TestClient

def test_new_router_endpoint(client: TestClient):
    """Test new router endpoint."""
    response = client.get("/new-route")
    assert response.status_code == 200
    assert "expected content" in response.text
```

### Example: Testing with Database

```python
from sqlalchemy.orm import Session
from fitness.models.blog import BlogEntry

def test_with_database(client: TestClient, db_session: Session):
    """Test with database fixture."""
    # Create test data
    entry = BlogEntry(
        slug="test",
        title="Test",
        content="Content",
        # ... other fields
    )
    db_session.add(entry)
    db_session.commit()

    # Test endpoint
    response = client.get("/log/entry/test")
    assert response.status_code == 200
```

### Example: Testing HTMX Endpoints

```python
def test_htmx_endpoint(client: TestClient):
    """Test HTMX partial response."""
    response = client.get("/log/category/cloud")
    assert response.status_code == 200
    # HTMX endpoints return HTML fragments
    assert "text/html" in response.headers["content-type"]
```

## Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Cleanup**: Use fixtures that auto-cleanup (session-scoped database)
3. **Descriptive Names**: Test names should clearly describe what they test
4. **Fast Tests**: Keep tests fast by using in-memory database (SQLite)
5. **Parametrize**: Use `@pytest.mark.parametrize` for testing multiple scenarios
6. **Mock External APIs**: Mock external API calls to avoid network dependencies
7. **Edge Cases**: Test edge cases, empty data, invalid inputs
8. **HTTP Status Codes**: Always verify expected status codes
9. **Response Content**: Verify both status codes and response content

## Continuous Integration

Tests are automatically run on:
- Pull requests
- Pushes to main branch
- Pre-commit hooks (linting and formatting)

## Coverage Goals

- **Overall**: 80%+ code coverage
- **Routers**: 90%+ coverage (business logic)
- **Models**: 100% coverage (data structures)
- **Services**: 85%+ coverage (complex logic)

## Troubleshooting

### Tests Failing Locally

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Clear test database**: `rm test_app.db`
3. **Check environment**: Ensure `DATABASE_URL` points to a local SQLite file

### Slow Tests

Security dashboard tests may be slow due to external API calls. Use timeouts:

```python
response = client.get("/security/dashboard", timeout=30)
```

### Database Conflicts

If tests fail with database errors:

```bash
# Remove test database and retry
rm test_app.db
pytest
```

## Future Test Additions

When adding new routers:

1. Create test file in `tests/routers/test_{router_name}.py`
2. Add comprehensive tests following existing patterns
3. Update `test_all_routers.py` with basic smoke tests
4. Update this guide with new test coverage

## Test Metrics

Run pytest with coverage to see metrics:

```bash
pytest --cov=fitness --cov-report=term-missing
```

This shows:
- Lines covered
- Lines missing
- Coverage percentage per file
- Overall coverage

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites)
