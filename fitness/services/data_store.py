"""DynamoDB data store read abstraction for the FastAPI app."""

from __future__ import annotations

import logging
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from fitness.config import settings

logger = logging.getLogger(__name__)


class DataStoreService:
    """Read interface for the witness DynamoDB data store."""

    def __init__(self) -> None:
        self._table = None

    @property
    def table(self):
        if self._table is None:
            dynamodb = boto3.resource("dynamodb", region_name=settings.aws_region)
            self._table = dynamodb.Table(settings.dynamodb_table_name)
        return self._table

    def get_latest(
        self,
        source: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Query items by source (PK), sorted by sort_key descending.

        Args:
            source: Partition key value (e.g., NASA_APOD, NIST_CVE).
            limit: Max items to return.

        Returns:
            List of item dicts.
        """
        try:
            resp = self.table.query(
                KeyConditionExpression=Key("source").eq(source),
                ScanIndexForward=False,
                Limit=limit,
            )
            return resp.get("Items", [])
        except Exception:
            logger.exception("DynamoDB query failed for source=%s", source)
            return []

    def query_by_type(
        self,
        data_type: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query GSI1 by data_type with optional timestamp range.

        Args:
            data_type: GSI1 partition key (e.g., apod, neo, cve).
            start: ISO-8601 start timestamp (inclusive).
            end: ISO-8601 end timestamp (inclusive).
            limit: Max items to return.

        Returns:
            List of item dicts.
        """
        try:
            key_expr = Key("data_type").eq(data_type)
            if start and end:
                key_expr &= Key("timestamp").between(start, end)
            elif start:
                key_expr &= Key("timestamp").gte(start)

            resp = self.table.query(
                IndexName="GSI1-DataType-Timestamp",
                KeyConditionExpression=key_expr,
                ScanIndexForward=False,
                Limit=limit,
            )
            return resp.get("Items", [])
        except Exception:
            logger.exception("DynamoDB GSI1 query failed for data_type=%s", data_type)
            return []

    def get_item(self, source: str, sort_key: str) -> dict[str, Any] | None:
        """Get a single item by composite key.

        Args:
            source: Partition key value.
            sort_key: Sort key value.

        Returns:
            Item dict or None.
        """
        try:
            resp = self.table.get_item(Key={"source": source, "sort_key": sort_key})
            return resp.get("Item")
        except Exception:
            logger.exception("DynamoDB get_item failed for %s/%s", source, sort_key)
            return None


data_store_service = DataStoreService()


def read_latest_from_dynamo(
    source: str,
    model_cls: type,
    limit: int = 50,
    logger_instance: logging.Logger | None = None,
) -> list | None:
    """Shared helper: read latest items from DynamoDB and deserialize into models.

    Returns a list of ``model_cls`` instances, or ``None`` on miss/error so
    callers can fall through to the API path.
    """
    _log = logger_instance or logger
    try:
        items = data_store_service.get_latest(source, limit=limit)
        if not items:
            return None
        return [model_cls(**item.get("payload", {})) for item in items]
    except Exception:
        _log.warning("DynamoDB %s read failed", source)
        return None
