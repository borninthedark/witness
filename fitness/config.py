"""Application settings and SQLite helpers."""

from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration entrypoint for the FastAPI application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    # Server
    base_url: str = "http://127.0.0.1:8000"
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Observability
    log_level: str = "INFO"
    enable_tracing: bool = False
    otlp_endpoint: str | None = None
    otlp_headers: str | None = None

    # Docker/Container configuration
    image: str | None = Field(
        default=None,
        validation_alias=AliasChoices("IMAGE", "DOCKER_IMAGE"),
    )

    # Metrics endpoint authentication
    metrics_username: str = "prometheus"
    metrics_password: str | None = None

    # Database (SQLite only)
    database_url: str = Field(
        default="sqlite:///./data/fitness.db",
        validation_alias=AliasChoices("DATABASE_URL"),
    )
    async_database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ASYNC_DATABASE_URL"),
    )
    allow_sqlite_fallback: bool = Field(
        default=False,
        validation_alias=AliasChoices("ALLOW_SQLITE_FALLBACK"),
    )
    db_echo: bool = Field(
        default=False,
        validation_alias=AliasChoices("DB_ECHO", "SQL_ECHO"),
    )
    # Storage
    storage_backend: Literal["local", "azure_blob"] = "local"
    azure_storage_account: str | None = None
    azure_container_name: str = "certs"
    azure_sas_token: str | None = None

    # PDF defaults
    default_accent_color: str = "#2e3440"
    default_page_color: str = "#eceff4"

    # Data
    data_dir: str = "fitness/data"
    resume_data_file: str = "resume-data.yaml"

    # Security
    secret_key: str = "dev-secret"
    jwt_lifetime_seconds: int = 60 * 60
    auth_cookie_name: str = "fitness-auth"
    admin_username: str = "admin"
    admin_password: str = "change-me"
    enable_dns_verification: bool = True

    # CSRF Protection
    csrf_secret: str = Field(
        default="dev-csrf-secret-change-me",
        validation_alias=AliasChoices("CSRF_SECRET", "CSRF_SECRET_KEY"),
    )

    # Features
    enable_open_badges: bool = False

    # External API Keys
    nist_api_key: str | None = None  # NIST NVD API key for CVE data
    anthropic_api_key: str | None = None  # Anthropic API key for AI features
    nasa_api_key: str | None = None  # NASA API key (DEMO_KEY works for low traffic)

    # Email configuration
    email_enabled: bool = True
    resend_api_key: str | None = None
    email_from_name: str = "Princeton A. Strong"
    email_from_addr: str = "contact@princetonstrong.com"
    email_to_addr: str = "info@princetonstrong.com"

    # Legacy SMTP fields (for fallback)
    mail_from: str | None = None
    mail_to: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_pass: str | None = None
    smtp_starttls: bool = True

    # Status dashboard configuration
    # Option 1: Use static snapshot URL (updated by automation)
    grafana_snapshot_url: str = ""

    # Option 2: Use Azure Managed Grafana public dashboard (live, no expiry)
    grafana_public_dashboard_url: str = ""

    @property
    def grafana_snapshot_url_from_file(self) -> str:
        """Load Grafana snapshot URL from config file (updated by automation)."""
        snapshot_file = Path(__file__).parent / "config" / "grafana_snapshot_url.txt"
        if snapshot_file.exists():
            try:
                return snapshot_file.read_text().strip()
            except (OSError, UnicodeDecodeError):
                pass
        return ""

    @property
    def grafana_dashboard_url(self) -> str:
        """Get Grafana dashboard URL.

        Prefers public dashboard (live), falls back to snapshot.
        """
        # Prefer public dashboard (live, no expiry)
        if self.grafana_public_dashboard_url:
            return self.grafana_public_dashboard_url

        # Fallback to snapshot (expires after 24h, updated hourly)
        return self.grafana_snapshot_url_from_file or self.grafana_snapshot_url

    # Feature flags
    enable_reports_dashboard: bool = False

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: str | list[str] | None) -> list[str]:
        """Normalize ALLOWED_ORIGINS env input into a list."""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in raw.split(",") if item.strip()]
        return []

    @property
    def is_production(self) -> bool:
        """Return True when running in production."""
        return self.environment == "production"

    @property
    def cors_origins(self) -> list[str]:
        """Expose allowed CORS origins for middleware wiring."""
        return self.allowed_origins

    @cached_property
    def resolved_database_url(self) -> str:
        """Return the primary sync SQLAlchemy URL."""
        return self.database_url

    @cached_property
    def resolved_async_database_url(self) -> str:
        """Return the async SQLAlchemy URL derived from the sync configuration."""
        if self.async_database_url:
            return self.async_database_url
        base_url = self.resolved_database_url
        if base_url.startswith("sqlite:///"):
            return base_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        return base_url


settings = Settings()
