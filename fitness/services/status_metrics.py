"""Public status metrics service.

This service provides sanitized, aggregated metrics for public consumption
without exposing sensitive infrastructure details.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from prometheus_client import REGISTRY


class StatusMetrics:
    """Fetch and format public status metrics."""

    def __init__(self):
        """Initialize status metrics service."""
        self.git_sha = os.getenv("GIT_SHA", "dev")
        self.deploy_timestamp = self._get_deploy_timestamp()

    def _get_deploy_timestamp(self) -> float:
        """Get deployment timestamp from app start time."""
        # In production, this would be set by the deployment process
        # For now, use a file-based approach
        timestamp_file = Path("fitness/config/.deploy_timestamp")
        if timestamp_file.exists():
            try:
                return float(timestamp_file.read_text().strip())
            except (ValueError, FileNotFoundError):
                pass
        return datetime.now(timezone.utc).timestamp()

    def get_public_metrics(self) -> dict[str, Any]:
        """Get sanitized public metrics from Prometheus registry.

        Aggregates metrics without exposing paths, IPs, or other sensitive data.
        """
        # Collect metrics from Prometheus registry
        metrics_data = self._collect_prometheus_metrics()

        # Calculate aggregated values
        latency_p95 = self._calculate_latency_p95(metrics_data)
        error_rate = self._calculate_error_rate(metrics_data)
        rps = self._calculate_rps(metrics_data)

        # Determine overall status
        overall_status = self._determine_status(error_rate, latency_p95)

        return {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "metrics": {
                "latency": {
                    "p95_ms": round(latency_p95, 2) if latency_p95 else None,
                    "status": self._latency_status(latency_p95)
                    if latency_p95
                    else "unknown",
                },
                "error_rate": {
                    "percentage": round(error_rate, 3) if error_rate else 0.0,
                    "status": "healthy"
                    if error_rate < 0.1
                    else "warning"
                    if error_rate < 1.0
                    else "degraded",
                },
                "throughput": {
                    "requests_per_second": round(rps, 1) if rps else 0.0,
                },
                "deployment": {
                    "hours_since_deploy": round(
                        (datetime.now(timezone.utc).timestamp() - self.deploy_timestamp)
                        / 3600,
                        1,
                    ),
                    "version": self.git_sha[:8],
                },
            },
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

    def _collect_prometheus_metrics(self) -> dict[str, Any]:
        """Collect metrics from Prometheus registry."""
        metrics = {}
        for collector in REGISTRY._collector_to_names.keys():
            for metric in collector.collect():
                metrics[metric.name] = metric
        return metrics

    def _calculate_latency_p95(  # noqa: C901
        self, metrics_data: dict[str, Any]
    ) -> float | None:
        """Calculate p95 latency from histogram data."""
        # Look for the fitness_request_duration_seconds metric
        histogram = metrics_data.get("fitness_request_duration_seconds")
        if not histogram or not hasattr(histogram, "samples"):
            return None

        # Aggregate all buckets (strip path/method labels for public view)
        buckets: dict[float, float] = {}
        total_count = 0

        for sample in histogram.samples:
            if sample.name.endswith("_bucket"):
                # Extract bucket upper bound
                le = sample.labels.get("le")
                if le == "+Inf":
                    continue
                try:
                    bucket_le = float(le)
                    buckets[bucket_le] = buckets.get(bucket_le, 0) + sample.value
                    total_count = max(total_count, sample.value)
                except (ValueError, TypeError):
                    continue

        if not buckets or total_count == 0:
            return None

        # Calculate p95 (95th percentile)
        p95_rank = total_count * 0.95
        cumulative = 0
        sorted_buckets = sorted(buckets.items())

        for bucket_le, count in sorted_buckets:
            cumulative = count
            if cumulative >= p95_rank:
                # Convert to milliseconds
                return bucket_le * 1000

        # If we get here, return the largest bucket
        if sorted_buckets:
            return sorted_buckets[-1][0] * 1000
        return None

    def _calculate_error_rate(self, metrics_data: dict[str, Any]) -> float:
        """Calculate error rate (5xx responses as percentage)."""
        counter = metrics_data.get("fitness_request_total")
        if not counter or not hasattr(counter, "samples"):
            return 0.0

        total_requests = 0
        error_requests = 0

        for sample in counter.samples:
            if sample.name.endswith("_total"):
                status_code = sample.labels.get("status_code", "")
                count = sample.value
                total_requests += count
                if status_code.startswith("5"):
                    error_requests += count

        if total_requests == 0:
            return 0.0

        return (error_requests / total_requests) * 100

    def _calculate_rps(self, metrics_data: dict[str, Any]) -> float:
        """Calculate approximate requests per second.

        Note: This is a simplified calculation. In production with Prometheus,
        use rate() over a time window.
        """
        counter = metrics_data.get("fitness_request_total")
        if not counter or not hasattr(counter, "samples"):
            return 0.0

        # For a rough estimate, we'd need time-series data
        # This is a placeholder - in production, query Prometheus directly
        total = sum(
            sample.value for sample in counter.samples if sample.name.endswith("_total")
        )

        # Estimate: divide by uptime in seconds (very rough approximation)
        uptime_seconds = datetime.now(timezone.utc).timestamp() - self.deploy_timestamp
        if uptime_seconds > 0:
            return total / uptime_seconds

        return 0.0

    def _determine_status(self, error_rate: float, latency_p95: float | None) -> str:
        """Determine overall system status."""
        if error_rate >= 5.0:
            return "outage"
        elif error_rate >= 1.0:
            return "degraded"
        elif latency_p95 and latency_p95 > 5000:  # 5 seconds
            return "degraded"
        elif error_rate < 0.1:
            return "operational"
        else:
            return "operational"

    @staticmethod
    def _latency_status(latency_ms: float | None) -> str:
        """Classify latency health."""
        if latency_ms is None:
            return "unknown"
        if latency_ms < 100:
            return "excellent"
        elif latency_ms < 300:
            return "good"
        elif latency_ms < 1000:
            return "fair"
        else:
            return "degraded"


# Singleton instance
status_service = StatusMetrics()
