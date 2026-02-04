from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from fitness.database import Base


class Certification(Base):
    """Certification model with status and visibility controls.

    Status values:
    - active: Current, valid certification
    - deprecated: No longer maintained but kept for historical records
    - expired: Certification has expired and is no longer valid

    Visibility:
    - is_visible=True: Shows in public listings
    - is_visible=False: Hidden from public view (admin only)

    This allows combinations like:
    - Active + Visible = Public active certification
    - Active + Hidden = Preparing to publish
    - Deprecated + Visible = Publicly show it's deprecated
    - Deprecated + Hidden = Historical record only
    """

    __tablename__ = "certifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    issuer: Mapped[str] = mapped_column(String(255))
    pdf_url: Mapped[str] = mapped_column(String(1024))
    sha256: Mapped[str] = mapped_column(String(128))
    dns_name: Mapped[str] = mapped_column(String(255), default="")
    assertion_url: Mapped[str] = mapped_column(String(1024), default="")
    verification_url: Mapped[str] = mapped_column(String(1024), default="")
    status: Mapped[str] = mapped_column(
        String(50), default="active", server_default="active"
    )
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    # Legacy field for backward compatibility
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
