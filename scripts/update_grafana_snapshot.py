#!/usr/bin/env python3
"""Update Grafana public status snapshot.

This script creates a new Grafana snapshot and updates the snapshot URL
for the public status dashboard. Designed to run via GitHub Actions on
a scheduled basis (hourly).

Environment Variables:
    GRAFANA_URL: Grafana instance URL (e.g., https://fitness-grafana.grafana.azure.com)
    GRAFANA_API_KEY: API key with snapshot creation permissions
    DASHBOARD_UID: UID of the dashboard to snapshot (default: public-status)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Error: httpx package required. Install with: pip install httpx")
    sys.exit(1)


def create_snapshot() -> None:
    """Create new public snapshot and update URL file."""
    # Get configuration from environment
    grafana_url = os.getenv("GRAFANA_URL")
    grafana_api_key = os.getenv("GRAFANA_API_KEY")
    dashboard_uid = os.getenv("DASHBOARD_UID", "public-status")

    if not grafana_url:
        print("Error: GRAFANA_URL environment variable not set")
        sys.exit(1)

    if not grafana_api_key:
        print("Error: GRAFANA_API_KEY environment variable not set")
        sys.exit(1)

    # Remove trailing slash from URL
    grafana_url = grafana_url.rstrip("/")

    headers = {"Authorization": f"Bearer {grafana_api_key}"}

    print(f"Fetching dashboard: {dashboard_uid}")

    try:
        # Get dashboard
        response = httpx.get(
            f"{grafana_url}/api/dashboards/uid/{dashboard_uid}",
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        dashboard_data = response.json()

        if "dashboard" not in dashboard_data:
            print(f"Error: Invalid dashboard response: {dashboard_data}")
            sys.exit(1)

        dashboard = dashboard_data["dashboard"]

        print(f"Creating snapshot for dashboard: {dashboard.get('title', 'Unknown')}")

        # Create snapshot
        snapshot_payload = {
            "dashboard": dashboard,
            "name": "Public Status Dashboard",
            "expires": 86400,  # 24 hours
            "external": False,  # Internal only for security
        }

        snapshot_response = httpx.post(
            f"{grafana_url}/api/snapshots",
            headers=headers,
            json=snapshot_payload,
            timeout=30.0,
        )
        snapshot_response.raise_for_status()
        snapshot = snapshot_response.json()

        if "key" not in snapshot:
            print(f"Error: Invalid snapshot response: {snapshot}")
            sys.exit(1)

        # Construct snapshot URL
        snapshot_url = f"{grafana_url}/dashboard/snapshot/{snapshot['key']}"

        # Save URL to config file
        config_dir = Path("fitness/config")
        config_dir.mkdir(parents=True, exist_ok=True)

        snapshot_url_file = config_dir / "grafana_snapshot_url.txt"
        snapshot_url_file.write_text(snapshot_url + "\n", encoding="utf-8")

        print(f"✅ Snapshot created: {snapshot_url}")
        print(f"   Expires in: {snapshot.get('expires', 'unknown')} seconds")
        print(f"   Saved to: {snapshot_url_file}")

    except httpx.HTTPStatusError as exc:
        print(f"HTTP error: {exc.response.status_code} {exc.response.text}")
        sys.exit(1)
    except httpx.RequestError as exc:
        print(f"Request error: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Unexpected error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    create_snapshot()
