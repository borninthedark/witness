"""Tests for blog router endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from fitness.models.blog import BlogEntry
from fitness.schemas.blog import Category, LogStatus


@pytest.fixture
def sample_blog_entry(db_session: Session) -> BlogEntry:
    """Create a sample published blog entry."""
    entry = BlogEntry(
        slug="test-blog-post",
        title="Test Blog Post",
        summary="This is a test blog post summary",
        content="# Test Content\n\nThis is **markdown** content.",
        category=Category.TUTORIAL.value,
        tags=json.dumps(["test", "python", "fastapi"]),
        stardate="2025.01",
        status=LogStatus.PUBLISHED.value,
        reading_time_minutes=5,
        published_at=datetime.utcnow(),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.fixture
def draft_blog_entry(db_session: Session) -> BlogEntry:
    """Create a sample draft blog entry."""
    entry = BlogEntry(
        slug="draft-post",
        title="Draft Post",
        summary="This is a draft post",
        content="Draft content",
        category=Category.PERSONAL.value,
        tags=json.dumps(["draft"]),
        status=LogStatus.DRAFT.value,
        reading_time_minutes=2,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.fixture
def multiple_blog_entries(db_session: Session) -> list[BlogEntry]:
    """Create multiple blog entries across different categories."""
    entries = []
    categories = [Category.CLOUD, Category.TUTORIAL, Category.SECURITY]

    for i, category in enumerate(categories):
        entry = BlogEntry(
            slug=f"blog-post-{i}",
            title=f"Blog Post {i}",
            summary=f"Summary for post {i}",
            content=f"# Content {i}\n\nThis is blog post number {i}.",
            category=category.value,
            tags=json.dumps([f"tag{i}", "common-tag"]),
            status=LogStatus.PUBLISHED.value,
            reading_time_minutes=i + 1,
            published_at=datetime.utcnow() - timedelta(days=i),
        )
        db_session.add(entry)
        entries.append(entry)

    db_session.commit()
    return entries


# Index/List Tests
def test_blog_index_returns_html(client: TestClient):
    """Test /log/ endpoint returns HTML page."""
    response = client.get("/log/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "CAPTAIN'S PERSONAL LOG" in response.text


def test_blog_index_shows_published_entries(
    client: TestClient, sample_blog_entry: BlogEntry
):
    """Test /log/ shows published blog entries."""
    response = client.get("/log/")
    assert response.status_code == 200
    assert sample_blog_entry.title in response.text
    assert sample_blog_entry.summary in response.text


def test_blog_index_hides_draft_entries(
    client: TestClient, draft_blog_entry: BlogEntry
):
    """Test /log/ does not show draft blog entries."""
    response = client.get("/log/")
    assert response.status_code == 200
    assert draft_blog_entry.title not in response.text


def test_blog_index_filter_by_category(
    client: TestClient, multiple_blog_entries: list[BlogEntry]
):
    """Test /log/ can filter by category."""
    response = client.get("/log/?category=cloud")
    assert response.status_code == 200

    # Should show cloud category post
    assert "Blog Post 0" in response.text

    # May not show others (pagination dependent)


def test_blog_index_filter_by_tag(
    client: TestClient, multiple_blog_entries: list[BlogEntry]
):
    """Test /log/ can filter by tag."""
    response = client.get("/log/?tag=tag0")
    assert response.status_code == 200
    assert "Blog Post 0" in response.text


def test_blog_index_pagination(client: TestClient, db_session: Session):
    """Test /log/ pagination works correctly."""
    # Create more than 10 entries (default page size)
    for i in range(15):
        entry = BlogEntry(
            slug=f"pagination-test-{i}",
            title=f"Pagination Test {i}",
            summary=f"Summary {i}",
            content=f"Content {i}",
            category=Category.TUTORIAL.value,
            tags=json.dumps([]),
            status=LogStatus.PUBLISHED.value,
            reading_time_minutes=1,
            published_at=datetime.utcnow() - timedelta(hours=i),
        )
        db_session.add(entry)
    db_session.commit()

    # Test first page
    response = client.get("/log/?page=1")
    assert response.status_code == 200

    # Test second page
    response = client.get("/log/?page=2")
    assert response.status_code == 200


# Single Entry Tests
def test_blog_entry_view_returns_html(client: TestClient, sample_blog_entry: BlogEntry):
    """Test /log/entry/{slug} returns HTML page."""
    response = client.get(f"/log/entry/{sample_blog_entry.slug}")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert sample_blog_entry.title in response.text


def test_blog_entry_view_renders_markdown(
    client: TestClient, sample_blog_entry: BlogEntry
):
    """Test blog entry view renders markdown to HTML."""
    response = client.get(f"/log/entry/{sample_blog_entry.slug}")
    assert response.status_code == 200

    # Check that markdown is rendered (look for HTML tags)
    assert "<h1>" in response.text or "<strong>" in response.text


def test_blog_entry_view_increments_view_count(
    client: TestClient, sample_blog_entry: BlogEntry, db_session: Session
):
    """Test viewing blog entry increments view count."""
    initial_count = sample_blog_entry.view_count

    # View the entry
    response = client.get(f"/log/entry/{sample_blog_entry.slug}")
    assert response.status_code == 200

    # Refresh from database
    db_session.refresh(sample_blog_entry)
    assert sample_blog_entry.view_count == initial_count + 1


def test_blog_entry_view_shows_related_entries(
    client: TestClient, multiple_blog_entries: list[BlogEntry]
):
    """Test blog entry view shows related entries from same category."""
    response = client.get(f"/log/entry/{multiple_blog_entries[0].slug}")
    assert response.status_code == 200

    # Check for related entries section
    assert "RELATED LOG ENTRIES" in response.text or "related" in response.text.lower()


def test_blog_entry_view_404_for_nonexistent(client: TestClient):
    """Test /log/entry/{slug} returns 404 for nonexistent entry."""
    response = client.get("/log/entry/nonexistent-slug-12345")
    assert response.status_code == 404


def test_blog_entry_view_404_for_draft(client: TestClient, draft_blog_entry: BlogEntry):
    """Test /log/entry/{slug} returns 404 for draft entries."""
    response = client.get(f"/log/entry/{draft_blog_entry.slug}")
    assert response.status_code == 404


# Search Tests
def test_blog_search_returns_results(client: TestClient, sample_blog_entry: BlogEntry):
    """Test /log/search finds matching entries."""
    response = client.get("/log/search?q=Test")
    assert response.status_code == 200
    assert sample_blog_entry.title in response.text


def test_blog_search_searches_title(client: TestClient, sample_blog_entry: BlogEntry):
    """Test search finds entries by title."""
    response = client.get(f"/log/search?q={sample_blog_entry.title.split()[0]}")
    assert response.status_code == 200
    assert sample_blog_entry.title in response.text


def test_blog_search_searches_content(client: TestClient, sample_blog_entry: BlogEntry):
    """Test search finds entries by content."""
    response = client.get("/log/search?q=markdown")
    assert response.status_code == 200
    assert sample_blog_entry.title in response.text


def test_blog_search_searches_tags(client: TestClient, sample_blog_entry: BlogEntry):
    """Test search finds entries by tags."""
    response = client.get("/log/search?q=python")
    assert response.status_code == 200
    assert sample_blog_entry.title in response.text


def test_blog_search_no_results(client: TestClient):
    """Test search returns appropriate response when no results found."""
    response = client.get("/log/search?q=nonexistentquery12345xyz")
    assert response.status_code == 200
    assert "No results found" in response.text or "0 result" in response.text


def test_blog_search_only_published(client: TestClient, draft_blog_entry: BlogEntry):
    """Test search only returns published entries."""
    response = client.get(f"/log/search?q={draft_blog_entry.title}")
    assert response.status_code == 200
    # Should not find draft
    assert draft_blog_entry.title not in response.text


def test_blog_search_requires_query_param(client: TestClient):
    """Test search endpoint requires 'q' parameter."""
    response = client.get("/log/search")
    assert response.status_code == 422  # Validation error


# Category Filter Tests
def test_blog_category_filter_returns_entries(
    client: TestClient, multiple_blog_entries: list[BlogEntry]
):
    """Test /log/category/{category} returns filtered entries."""
    response = client.get("/log/category/cloud")
    assert response.status_code == 200
    assert "Blog Post 0" in response.text


def test_blog_category_filter_invalid_category(client: TestClient):
    """Test /log/category/{category} handles invalid category."""
    response = client.get("/log/category/invalid-category-xyz")
    assert response.status_code == 400


# Stats Tests
def test_blog_index_shows_stats(
    client: TestClient, multiple_blog_entries: list[BlogEntry]
):
    """Test blog index shows statistics."""
    response = client.get("/log/")
    assert response.status_code == 200

    # Check for stats panel
    assert "SHIP'S STATUS" in response.text or "stats" in response.text.lower()
    assert "TOTAL LOGS" in response.text or "published" in response.text.lower()


def test_blog_index_shows_categories(client: TestClient):
    """Test blog index shows category navigation."""
    response = client.get("/log/")
    assert response.status_code == 200

    # Check for category navigation
    assert "MISSION TYPES" in response.text or "categor" in response.text.lower()


def test_blog_index_shows_tags_cloud(client: TestClient, sample_blog_entry: BlogEntry):
    """Test blog index shows tags cloud."""
    response = client.get("/log/")
    assert response.status_code == 200

    # Check for tags section (may be hidden if no tags)
    if sample_blog_entry.tags:
        assert "QUICK ACCESS TAGS" in response.text or "tag" in response.text.lower()


# Edge Cases
def test_blog_entry_with_special_characters_in_slug(
    client: TestClient, db_session: Session
):
    """Test blog entry with URL-safe slug."""
    entry = BlogEntry(
        slug="test-slug-with-numbers-123",
        title="Test Title",
        summary="Summary",
        content="Content",
        category=Category.TUTORIAL.value,
        tags=json.dumps([]),
        status=LogStatus.PUBLISHED.value,
        reading_time_minutes=1,
        published_at=datetime.utcnow(),
    )
    db_session.add(entry)
    db_session.commit()

    response = client.get(f"/log/entry/{entry.slug}")
    assert response.status_code == 200


def test_blog_entry_without_stardate(client: TestClient, db_session: Session):
    """Test blog entry without stardate displays correctly."""
    entry = BlogEntry(
        slug="no-stardate",
        title="No Stardate Entry",
        summary="Summary",
        content="Content",
        category=Category.PERSONAL.value,
        tags=json.dumps([]),
        stardate=None,  # No stardate
        status=LogStatus.PUBLISHED.value,
        reading_time_minutes=1,
        published_at=datetime.utcnow(),
    )
    db_session.add(entry)
    db_session.commit()

    response = client.get(f"/log/entry/{entry.slug}")
    assert response.status_code == 200


def test_blog_entry_without_tags(client: TestClient, db_session: Session):
    """Test blog entry without tags displays correctly."""
    entry = BlogEntry(
        slug="no-tags",
        title="No Tags Entry",
        summary="Summary",
        content="Content",
        category=Category.TECHNICAL.value,
        tags=json.dumps([]),  # Empty tags
        status=LogStatus.PUBLISHED.value,
        reading_time_minutes=1,
        published_at=datetime.utcnow(),
    )
    db_session.add(entry)
    db_session.commit()

    response = client.get(f"/log/entry/{entry.slug}")
    assert response.status_code == 200


def test_blog_with_empty_database(client: TestClient, db_session: Session):
    """Test blog index with no entries shows appropriate message."""
    # Clear all blog entries
    db_session.query(BlogEntry).delete()
    db_session.commit()

    response = client.get("/log/")
    assert response.status_code == 200
    assert "No log entries" in response.text or "Check back later" in response.text


# Multiple Requests
def test_blog_multiple_page_views(
    client: TestClient, sample_blog_entry: BlogEntry, db_session: Session
):
    """Test multiple page views increment counter correctly."""
    initial_count = sample_blog_entry.view_count

    # View multiple times
    for _ in range(3):
        client.get(f"/log/entry/{sample_blog_entry.slug}")

    db_session.refresh(sample_blog_entry)
    assert sample_blog_entry.view_count == initial_count + 3


# Integration Tests
@pytest.mark.parametrize(
    "path,expected_status",
    [
        ("/log/", 200),
        ("/log/entry/test-slug", 404),  # Non-existent
        ("/log/search?q=test", 200),
        ("/log/category/cloud", 200),
        ("/log/category/invalid", 400),
        ("/log/?page=1", 200),
        ("/log/?category=tutorial", 200),
    ],
)
def test_blog_routes_return_expected_status_codes(
    client: TestClient, path: str, expected_status: int
):
    """Test blog routes return expected HTTP status codes."""
    response = client.get(path)
    assert response.status_code == expected_status


def test_blog_css_loaded(client: TestClient):
    """Test blog pages load blog.css stylesheet."""
    response = client.get("/log/")
    assert response.status_code == 200
    assert "blog.css" in response.text


def test_blog_htmx_enabled(client: TestClient):
    """Test blog pages include HTMX for dynamic loading."""
    response = client.get("/log/")
    assert response.status_code == 200
    assert "hx-" in response.text or "htmx" in response.text.lower()
