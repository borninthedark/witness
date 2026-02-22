"""Tests for fitness/utils/assets.py and fitness/utils/yaml_loader.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


class TestAssetUrl:
    """Asset URL cache-busting helper."""

    def test_asset_url_returns_static_path(self, tmp_path):
        """Existing file gets a ?v=<hash> suffix."""
        from fitness.utils.assets import asset_url

        css = tmp_path / "main.css"
        css.write_text("body { color: red; }")

        with patch("fitness.utils.assets.STATIC_ROOT", tmp_path):
            asset_url.cache_clear()
            result = asset_url("main.css")

        assert result.startswith("/static/main.css?v=")
        assert len(result.split("?v=")[1]) == 12

    def test_asset_url_missing_file(self):
        """Missing file returns path without hash."""
        from fitness.utils.assets import asset_url

        with patch("fitness.utils.assets.STATIC_ROOT", Path("/nonexistent")):
            asset_url.cache_clear()
            result = asset_url("missing.css")

        assert result == "/static/missing.css"
        assert "?v=" not in result


class TestYamlLoader:
    """YAML loading with newline coercion."""

    def test_load_yaml_file(self, tmp_path):
        """Valid YAML parses correctly."""
        from fitness.utils.yaml_loader import load_yaml

        yml = tmp_path / "data.yaml"
        yml.write_text("name: Picard\nrank: Captain\n")

        result = load_yaml(yml)
        assert result == {"name": "Picard", "rank": "Captain"}

    def test_load_yaml_missing_file(self):
        """Missing YAML raises FileNotFoundError."""
        from fitness.utils.yaml_loader import load_yaml

        with pytest.raises(FileNotFoundError):
            load_yaml(Path("/nonexistent/missing.yaml"))

    def test_load_yaml_with_crlf(self, tmp_path):
        """Windows-style line endings are handled."""
        from fitness.utils.yaml_loader import load_yaml

        yml = tmp_path / "crlf.yaml"
        yml.write_bytes(b"name: Riker\r\nrank: Commander\r\n")

        result = load_yaml(yml)
        assert result["name"] == "Riker"
