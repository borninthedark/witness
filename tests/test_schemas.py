"""Tests for fitness/schemas/ — Pydantic validation models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestCertificationSchema:
    """CertificationOut schema validation."""

    def test_valid_certification_parses(self):
        from fitness.schemas.certification import CertificationOut

        data = {
            "slug": "ckad",
            "title": "Certified Kubernetes Admin",
            "issuer": "CNCF",
            "pdf_url": "/static/certs/ckad.pdf",
            "sha256": "a" * 64,
        }
        cert = CertificationOut(**data)
        assert cert.slug == "ckad"
        assert cert.dns_name is None

    def test_missing_required_field_errors(self):
        from fitness.schemas.certification import CertificationOut

        with pytest.raises(ValidationError):
            CertificationOut(  # missing issuer, pdf_url, sha256
                slug="ckad", title="Test"
            )


class TestContactSchema:
    """ContactForm schema validation."""

    def test_valid_contact_parses(self):
        from fitness.schemas.contact import ContactForm

        form = ContactForm(
            name="Jean-Luc Picard",
            email="picard@enterprise.fed",
            subject="First Contact",
            message="Make it so.",
        )
        assert form.name == "Jean-Luc Picard"

    def test_invalid_email_errors(self):
        from fitness.schemas.contact import ContactForm

        with pytest.raises(ValidationError, match="email"):
            ContactForm(
                name="Test",
                email="not-an-email",
                subject="Test",
                message="Hello",
            )

    def test_empty_name_errors(self):
        from fitness.schemas.contact import ContactForm

        with pytest.raises(ValidationError):
            ContactForm(
                name="   ",
                email="test@test.com",
                subject="Test",
                message="Hello",
            )

    def test_message_too_long_errors(self):
        from fitness.schemas.contact import ContactForm

        with pytest.raises(ValidationError, match="too long"):
            ContactForm(
                name="Test",
                email="test@test.com",
                subject="Test",
                message="x" * 4001,
            )


class TestOpenBadgesSchema:
    """BadgeAssertionOut schema validation."""

    def test_badge_assertion_parses(self):
        from fitness.schemas.open_badges import BadgeAssertionOut

        badge = BadgeAssertionOut(
            assertion_id="urn:uuid:abc123",
            badge_name="AWS SAP-C02",
            evidence=["https://credly.com/badges/123"],
        )
        assert badge.badge_name == "AWS SAP-C02"
        assert badge.issuer_name is None

    def test_badge_missing_required_errors(self):
        from fitness.schemas.open_badges import BadgeAssertionOut

        with pytest.raises(ValidationError):
            BadgeAssertionOut(badge_name="Test")  # missing assertion_id, evidence


class TestBlogSchemas:
    """Blog entry schema validation."""

    def test_blog_entry_create(self):
        from fitness.schemas.blog import BlogEntryCreate, Category

        entry = BlogEntryCreate(
            title="First Post",
            slug="first-post",
            summary="A summary",
            content="# Hello World",
            category=Category.TECHNICAL,
        )
        assert entry.status.value == "draft"

    def test_blog_entry_title_too_long(self):
        from fitness.schemas.blog import BlogEntryCreate, Category

        with pytest.raises(ValidationError):
            BlogEntryCreate(
                title="x" * 201,
                slug="too-long",
                summary="A summary",
                content="Content",
                category=Category.TECHNICAL,
            )

    def test_blog_entry_update_partial(self):
        from fitness.schemas.blog import BlogEntryUpdate

        update = BlogEntryUpdate(title="New Title")
        assert update.title == "New Title"
        assert update.content is None
