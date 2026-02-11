"""Lambda handler — Ingest NIST NVD CVE data."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from urllib.request import Request, urlopen

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ["DYNAMODB_TABLE"]
NIST_API_KEY = os.environ.get("NIST_API_KEY", "")
TTL_DAYS = 90

NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def _ttl_epoch() -> int:
    return int(time.time()) + (TTL_DAYS * 86400)


def _fetch_cves(days: int = 7) -> list[dict]:
    """Fetch recent CVEs from NIST NVD 2.0 API."""
    end = datetime.now(UTC)
    start = end - timedelta(days=days)

    params = {
        "pubStartDate": start.strftime("%Y-%m-%dT00:00:00.000"),
        "pubEndDate": end.strftime("%Y-%m-%dT23:59:59.999"),
        "resultsPerPage": "100",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{NVD_API_URL}?{query}"

    headers = {"User-Agent": "witness-ingest/1.0"}
    if NIST_API_KEY:
        headers["apiKey"] = NIST_API_KEY

    req = Request(url, headers=headers)  # noqa: S310
    with urlopen(req, timeout=60) as resp:  # noqa: S310
        data = json.loads(resp.read())

    now = datetime.now(UTC).isoformat()
    items = []

    for vuln in data.get("vulnerabilities", []):
        cve = vuln.get("cve", {})
        cve_id = cve.get("id", "UNKNOWN")
        descriptions = cve.get("descriptions", [])
        description = next(
            (d["value"] for d in descriptions if d.get("lang") == "en"), ""
        )

        # Extract CVSS score
        metrics = cve.get("metrics", {})
        cvss_score = 0.0
        severity = "UNKNOWN"
        for version in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
            if version in metrics:
                metric_data = metrics[version][0].get("cvssData", {})
                cvss_score = metric_data.get("baseScore", 0.0)
                severity = metric_data.get("baseSeverity", "UNKNOWN")
                break

        published = cve.get("published", "")
        modified = cve.get("lastModified", "")

        references = [ref.get("url", "") for ref in cve.get("references", [])[:5]]

        items.append(
            {
                "source": "NIST_CVE",
                "sort_key": f"date#{published[:10]}#id#{cve_id}",
                "data_type": "cve",
                "timestamp": now,
                "expiry_epoch": _ttl_epoch(),
                "payload": {
                    "cve_id": cve_id,
                    "description": description[:2000],
                    "severity": severity,
                    "cvss_score": cvss_score,
                    "published_date": published,
                    "modified_date": modified,
                    "references": references,
                },
            }
        )

    return items


def lambda_handler(event, context):
    """Lambda entry point — ingest NIST CVE data."""
    import sys

    sys.path.insert(0, "/opt")
    from dynamo_writer import batch_write_items

    try:
        items = _fetch_cves(days=7)
        written = batch_write_items(TABLE_NAME, items)
        logger.info("NIST CVE: fetched=%d written=%d", len(items), written)
        return {
            "statusCode": 200,
            "body": {"fetched": len(items), "written": written},
        }
    except Exception:
        logger.exception("Failed to ingest NIST CVEs")
        return {"statusCode": 500, "body": {"error": "CVE ingest failed"}}
