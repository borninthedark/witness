"""Safe, pre-sanitized metrics for public observability dashboard.

This module provides aggregated, high-level metrics safe for public display.

PRODUCTION ROADMAP:
-------------------
To integrate with real Prometheus metrics, update `get_safe_observability_snapshot()`
to query your Prometheus server using the example PromQL queries provided in the
docstring. Consider using the prometheus-client library or HTTP API calls.

For now, this module generates realistic placeholder data suitable for demos
and development environments.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass
class TimeSeriesPoint:
    """Single time-series data point."""

    timestamp: datetime
    rps: float
    p95_ms: float
    error_rate: float  # 0-1 range


@dataclass
class StatusSnapshot:
    """HTTP status code distribution."""

    labels: list[str]
    counts: list[int]


@dataclass
class ObservabilitySnapshot:
    """Complete observability snapshot for dashboard."""

    series: list[TimeSeriesPoint]
    status_codes: StatusSnapshot


def get_safe_observability_snapshot() -> ObservabilitySnapshot:
    """Return redacted, public-safe snapshot of metrics.

    This uses placeholder data. Replace with real Prometheus queries:

    Example PromQL queries:
    - RPS: rate(http_requests_total[5m])
    - p95: histogram_quantile(
        0.95, rate(http_request_duration_seconds_bucket[5m])
    )
    - Error rate: rate(http_requests_total{status=~"5.."}[5m]) /
        rate(http_requests_total[5m])

    Returns:
        ObservabilitySnapshot with time series and status code distribution
    """
    now = datetime.now(UTC)

    # Generate 12 time-series points (last hour, 5-min intervals)
    series: list[TimeSeriesPoint] = []
    for i in range(12):
        ts = now - timedelta(minutes=5 * (11 - i))
        rps = 5.0 + i * 0.8  # Simulate increasing traffic
        p95_ms = 120.0 + i * 8  # Simulate latency variance
        error_rate = 0.02 + i * 0.003  # Simulate error rate increase
        series.append(
            TimeSeriesPoint(
                timestamp=ts,
                rps=rps,
                p95_ms=p95_ms,
                error_rate=error_rate,
            )
        )

    # High-level status distribution - safe for public display
    # No individual request details, IPs, or internal paths
    status_codes = StatusSnapshot(
        labels=["2xx", "4xx", "5xx"],
        counts=[820, 35, 5],  # Placeholder counts
    )

    return ObservabilitySnapshot(series=series, status_codes=status_codes)
