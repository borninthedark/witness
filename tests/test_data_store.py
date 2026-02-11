"""Tests for DynamoDB data store service."""

from __future__ import annotations

from unittest.mock import MagicMock

from fitness.services.data_store import DataStoreService


class TestDataStoreService:
    """Unit tests for DataStoreService."""

    def _make_service(self) -> DataStoreService:
        svc = DataStoreService()
        svc._table = MagicMock()
        return svc

    def test_get_latest_returns_items(self):
        svc = self._make_service()
        svc._table.query.return_value = {
            "Items": [
                {
                    "source": "NASA_APOD",
                    "sort_key": "date#2026-02-10",
                    "payload": {"title": "Test"},
                },
            ]
        }
        items = svc.get_latest("NASA_APOD", limit=1)
        assert len(items) == 1
        assert items[0]["payload"]["title"] == "Test"
        svc._table.query.assert_called_once()

    def test_get_latest_returns_empty_on_error(self):
        svc = self._make_service()
        svc._table.query.side_effect = Exception("Connection error")
        items = svc.get_latest("NASA_APOD")
        assert items == []

    def test_query_by_type_with_time_range(self):
        svc = self._make_service()
        svc._table.query.return_value = {"Items": [{"data_type": "cve"}]}
        items = svc.query_by_type("cve", start="2026-01-01", end="2026-02-10")
        assert len(items) == 1
        call_kwargs = svc._table.query.call_args[1]
        assert call_kwargs["IndexName"] == "GSI1-DataType-Timestamp"

    def test_query_by_type_without_range(self):
        svc = self._make_service()
        svc._table.query.return_value = {"Items": []}
        items = svc.query_by_type("apod")
        assert items == []

    def test_get_item_returns_item(self):
        svc = self._make_service()
        svc._table.get_item.return_value = {
            "Item": {
                "source": "NIST_CVE",
                "sort_key": "date#2026-02-10#id#CVE-2026-1234",
            }
        }
        item = svc.get_item("NIST_CVE", "date#2026-02-10#id#CVE-2026-1234")
        assert item is not None
        assert item["source"] == "NIST_CVE"

    def test_get_item_returns_none_on_miss(self):
        svc = self._make_service()
        svc._table.get_item.return_value = {}
        item = svc.get_item("MISSING", "key")
        assert item is None

    def test_get_item_returns_none_on_error(self):
        svc = self._make_service()
        svc._table.get_item.side_effect = Exception("Timeout")
        item = svc.get_item("NASA_APOD", "key")
        assert item is None
