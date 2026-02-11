"""Lambda handler — DynamoDB Streams → Azure AI Search embedding sync.

Triggered by DynamoDB Streams on INSERT/MODIFY events. For each new or
updated item, generates an embedding via Azure OpenAI and upserts the
vector + metadata into Azure AI Search.
"""

from __future__ import annotations

import json
import logging
import os
from urllib.request import Request, urlopen

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY", "")
AZURE_SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_KEY = os.environ.get("AZURE_SEARCH_KEY", "")

EMBEDDING_DEPLOYMENT = "text-embedding-3-large"
SEARCH_INDEX = "witness-data"


def _get_embedding(text: str) -> list[float]:
    """Call Azure OpenAI embedding API."""
    url = (
        f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/"
        f"{EMBEDDING_DEPLOYMENT}/embeddings?api-version=2024-06-01"
    )
    body = json.dumps({"input": text}).encode()
    req = Request(  # noqa: S310
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_KEY,
        },
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:  # noqa: S310
        data = json.loads(resp.read())
    return data["data"][0]["embedding"]


def _upsert_search_doc(doc: dict) -> None:
    """Upsert document into Azure AI Search index."""
    url = (
        f"{AZURE_SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}"
        "/docs/index?api-version=2024-07-01"
    )
    payload = {"value": [{"@search.action": "mergeOrUpload", **doc}]}
    body = json.dumps(payload).encode()
    req = Request(  # noqa: S310
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "api-key": AZURE_SEARCH_KEY,
        },
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:  # noqa: S310
        resp.read()


def _build_text_for_embedding(item: dict) -> str:
    """Build searchable text from a DynamoDB item for embedding."""
    payload = item.get("payload", {})
    parts = []

    # Add source context
    source = item.get("source", "")
    data_type = item.get("data_type", "")
    parts.append(f"Source: {source} Type: {data_type}")

    # Extract text fields from payload
    for key in [
        "title",
        "description",
        "explanation",
        "name",
        "planet_name",
        "summary",
        "cve_id",
        "report_type",
    ]:
        if key in payload and payload[key]:
            parts.append(str(payload[key]))

    return " | ".join(parts)


def _process_record(record: dict) -> None:
    """Process a single DynamoDB stream record."""
    if record.get("eventName") not in ("INSERT", "MODIFY"):
        return

    new_image = record.get("dynamodb", {}).get("NewImage", {})
    if not new_image:
        return

    # Deserialize DynamoDB JSON format
    item = {}
    for key, value in new_image.items():
        if "S" in value:
            item[key] = value["S"]
        elif "N" in value:
            item[key] = float(value["N"])
        elif "M" in value:
            item[key] = {k: v.get("S", v.get("N", "")) for k, v in value["M"].items()}
        elif "BOOL" in value:
            item[key] = value["BOOL"]

    text = _build_text_for_embedding(item)
    if not text.strip():
        return

    # Generate embedding
    vector = _get_embedding(text)

    # Build search document
    doc_id = f"{item.get('source', '')}_{item.get('sort_key', '')}".replace("#", "_")
    search_doc = {
        "id": doc_id,
        "source": item.get("source", ""),
        "sort_key": item.get("sort_key", ""),
        "data_type": item.get("data_type", ""),
        "timestamp": item.get("timestamp", ""),
        "content": text,
        "content_vector": vector,
        "payload_json": json.dumps(item.get("payload", {})),
    }

    _upsert_search_doc(search_doc)
    logger.info("Upserted %s to search index", doc_id)


def lambda_handler(event, context):
    """Lambda entry point — process DynamoDB stream records."""
    if not AZURE_OPENAI_ENDPOINT or not AZURE_SEARCH_ENDPOINT:
        logger.warning("Azure endpoints not configured, skipping embed sync")
        return {"statusCode": 200, "body": "skipped"}

    records = event.get("Records", [])
    processed = 0
    errors = 0

    for record in records:
        try:
            _process_record(record)
            processed += 1
        except Exception:
            logger.exception("Failed to process record")
            errors += 1

    logger.info("Processed %d records, %d errors", processed, errors)
    return {
        "statusCode": 200,
        "body": {"processed": processed, "errors": errors},
    }
