"""Pydantic schemas for blog entries."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class LogStatus(str, Enum):
    """Blog entry status."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Category(str, Enum):
    """Blog entry category."""

    TECHNICAL = "technical"
    TUTORIAL = "tutorial"
    SYSTEMS = "systems"
    CLOUD = "cloud"
    SECURITY = "security"
    PERSONAL = "personal"
    EXPLORATION = "exploration"


class BlogEntryBase(BaseModel):
    """Base blog entry schema."""

    title: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=200)
    summary: str = Field(..., max_length=500)
    content: str
    category: Category
    tags: list[str] = Field(default_factory=list)
    stardate: str | None = None
    status: LogStatus = LogStatus.DRAFT


class BlogEntryCreate(BlogEntryBase):
    """Schema for creating a blog entry."""

    pass


class BlogEntryUpdate(BaseModel):
    """Schema for updating a blog entry."""

    title: str | None = None
    summary: str | None = None
    content: str | None = None
    category: Category | None = None
    tags: list[str] | None = None
    stardate: str | None = None
    status: LogStatus | None = None


class BlogEntryOut(BlogEntryBase):
    """Blog entry output schema."""

    id: int
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None
    view_count: int = 0
    reading_time_minutes: int = 0

    class Config:
        from_attributes = True


class BlogEntryPublic(BaseModel):
    """Public view of blog entry with rendered HTML."""

    id: int
    title: str
    slug: str
    summary: str
    content_html: str  # Rendered markdown
    category: Category
    tags: list[str]
    stardate: str | None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    reading_time_minutes: int
    view_count: int


class SearchResult(BaseModel):
    """Search results container."""

    total: int
    entries: list[BlogEntryOut]
    query: str
