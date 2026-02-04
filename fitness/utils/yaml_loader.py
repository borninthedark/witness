"""YAML IO helpers with newline coercion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _coerce_newlines(raw: str) -> str:
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def load_yaml(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8")
    try:
        return yaml.safe_load(raw)
    except Exception:  # pragma: no cover
        return yaml.safe_load(_coerce_newlines(raw))
