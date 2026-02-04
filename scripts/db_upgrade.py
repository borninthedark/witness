#!/usr/bin/env python3
"""Run Alembic migrations up to head."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


def upgrade_head() -> None:
    project_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(project_root / "alembic.ini"))
    command.upgrade(cfg, "head")


def main() -> None:
    upgrade_head()


if __name__ == "__main__":
    main()
