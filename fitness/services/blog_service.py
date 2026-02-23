"""Blog service layer for Captain's Personal Log."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import frontmatter
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.tables import TableExtension
from markdown.extensions.toc import TocExtension
from slugify import slugify

from fitness.models.blog import BlogEntry
from fitness.schemas.blog import BlogEntryPublic, Category, LogStatus

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class BlogService:
    """Service for blog operations."""

    def __init__(self):
        """Initialize markdown processor."""
        self.md = markdown.Markdown(
            extensions=[
                FencedCodeExtension(),
                CodeHiliteExtension(css_class="highlight", linenums=False),
                TableExtension(),
                TocExtension(toc_depth="2-3"),
                "nl2br",
                "sane_lists",
            ]
        )

    def render_markdown(self, content: str) -> str:
        """Render markdown to HTML.

        Args:
            content: Markdown content

        Returns:
            Rendered HTML
        """
        self.md.reset()
        return self.md.convert(content)

    @staticmethod
    def generate_slug(title: str) -> str:
        """Generate URL-safe slug from title.

        Args:
            title: Blog entry title

        Returns:
            URL-safe slug
        """
        return slugify(title, max_length=200)

    @staticmethod
    def calculate_reading_time(content: str) -> int:
        """Calculate estimated reading time in minutes.

        Args:
            content: Blog content

        Returns:
            Reading time in minutes (minimum 1)
        """
        word_count = len(content.split())
        # Average reading speed: 200 words per minute
        return max(1, word_count // 200)

    def create_entry_from_markdown_file(self, filepath: str, db: Session) -> BlogEntry:
        """Create blog entry from markdown file with frontmatter.

        Args:
            filepath: Path to markdown file
            db: Database session

        Returns:
            Created BlogEntry
        """
        with open(filepath, encoding="utf-8") as f:
            post = frontmatter.load(f)

        # Extract metadata from frontmatter
        title = post.get("title", os.path.basename(filepath))
        slug = post.get("slug", self.generate_slug(title))
        summary = post.get("summary", "")
        category = Category(post.get("category", "personal"))
        tags = post.get("tags", [])
        stardate = post.get("stardate")
        status = LogStatus(post.get("status", "draft"))

        # Create entry
        entry = BlogEntry(
            title=title,
            slug=slug,
            summary=summary,
            content=post.content,
            category=category.value,
            tags=json.dumps(tags),
            stardate=stardate,
            status=status.value,
            reading_time_minutes=self.calculate_reading_time(post.content),
        )

        # Set published_at if status is published
        if status == LogStatus.PUBLISHED:
            entry.published_at = datetime.now(UTC)

        db.add(entry)
        db.commit()
        db.refresh(entry)

        return entry

    def get_public_entry(self, entry: BlogEntry) -> BlogEntryPublic:
        """Convert BlogEntry to public schema with rendered HTML.

        Args:
            entry: Blog entry model

        Returns:
            Public blog entry with rendered content
        """
        content_html = self.render_markdown(entry.content)

        return BlogEntryPublic(
            id=entry.id,
            title=entry.title,
            slug=entry.slug,
            summary=entry.summary,
            content_html=content_html,
            category=Category(entry.category),
            tags=json.loads(entry.tags) if entry.tags else [],
            stardate=entry.stardate,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            published_at=entry.published_at,
            reading_time_minutes=entry.reading_time_minutes,
            view_count=entry.view_count,
        )

    def load_markdown_files(self, db: Session, directory: str = "data/blog") -> int:
        """Load all markdown files from directory into database.

        Args:
            db: Database session
            directory: Directory containing markdown files

        Returns:
            Number of files loaded
        """
        blog_dir = Path(directory)
        if not blog_dir.exists():
            blog_dir.mkdir(parents=True, exist_ok=True)
            return 0

        loaded_count = 0
        for filepath in blog_dir.glob("*.md"):
            try:
                # Check if slug already exists
                with open(filepath, encoding="utf-8") as f:
                    post = frontmatter.load(f)

                title = post.get("title", os.path.basename(filepath.name))
                slug = post.get("slug", self.generate_slug(title))

                existing = db.query(BlogEntry).filter(BlogEntry.slug == slug).first()
                if existing:
                    print(f"Skipping {filepath.name} - slug '{slug}' already exists")
                    continue

                self.create_entry_from_markdown_file(str(filepath), db)
                loaded_count += 1
                print(f"Loaded: {filepath.name}")
            except Exception as e:
                print(f"Error loading {filepath.name}: {e}")

        return loaded_count


# Singleton instance
blog_service = BlogService()
