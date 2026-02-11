"""DynamoDB batch write helper for Lambda ingest functions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import boto3
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient

logger = logging.getLogger(__name__)


def get_dynamodb_client() -> DynamoDBClient:
    """Create a DynamoDB resource client."""
    return boto3.resource("dynamodb")


def batch_write_items(
    table_name: str,
    items: list[dict[str, Any]],
) -> int:
    """Write items to DynamoDB using batch_writer.

    Args:
        table_name: DynamoDB table name.
        items: List of item dicts to write.

    Returns:
        Number of items written successfully.
    """
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(table_name)
    written = 0

    try:
        with table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)
                written += 1
    except ClientError:
        logger.exception("Batch write failed after %d items", written)

    return written


def put_item(table_name: str, item: dict[str, Any]) -> bool:
    """Write a single item to DynamoDB.

    Args:
        table_name: DynamoDB table name.
        item: Item dict to write.

    Returns:
        True if successful.
    """
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(table_name)

    try:
        table.put_item(Item=item)
        return True
    except ClientError:
        logger.exception(
            "put_item failed for %s/%s", item.get("source"), item.get("sort_key")
        )
        return False
