"""Tests for status router and status_metrics service.

Covers:
- GET /admin/status/ (authenticated dashboard page with Bokeh charts)
- GET /admin/status/json (public JSON metrics)
- GET /admin/status/badge.svg (availability badge)
- GET /admin/status/uptime-badge.svg (uptime badge)
- _generate_bokeh_charts() helper
- StatusMetrics service methods (unit tests)
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from fitness.auth import current_active_user
from fitness.main import app
from fitness.observability.safe_metrics import (
    ObservabilitySnapshot,
    StatusSnapshot,
    TimeSeriesPoint,
)
from fitness.services.status_metrics import StatusMetrics

CSRF_TOKEN = "test-csrf-token"  # noqa: S105


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def auth_client(client):
    """Authenticated test client with CSRF token."""
    mock_user = MagicMock(email="test@test.com", id=uuid4(), is_active=True)
    app.dependency_overrides[current_active_user] = lambda: mock_user
    client.cookies.set("wtf_csrf", CSRF_TOKEN)
    yield client
    app.dependency_overrides.pop(current_active_user, None)
    client.cookies.delete("wtf_csrf")


def _make_metrics(
    *,
    status: str = "operational",
    latency_p95: float | None = 45.0,
    latency_status: str = "excellent",
    error_rate_pct: float = 0.01,
    error_status: str = "healthy",
    rps: float = 12.5,
    hours_since: float = 2.0,
    version: str = "abc12345",
) -> dict:
    """Build a metrics dict matching StatusMetrics.get_public_metrics() shape."""
    return {
        "status": status,
        "timestamp": "2026-02-22T12:00:00Z",
        "metrics": {
            "latency": {
                "p95_ms": latency_p95,
                "status": latency_status,
            },
            "error_rate": {
                "percentage": error_rate_pct,
                "status": error_status,
            },
            "throughput": {
                "requests_per_second": rps,
            },
            "deployment": {
                "hours_since_deploy": hours_since,
                "version": version,
            },
        },
        "updated_at": "2026-02-22T12:00:00Z",
    }


def _make_snapshot(
    n_points: int = 3,
    status_labels: list[str] | None = None,
    status_counts: list[int] | None = None,
) -> ObservabilitySnapshot:
    """Build a minimal ObservabilitySnapshot for chart tests."""
    now = datetime.now(UTC)
    series = [
        TimeSeriesPoint(
            timestamp=now,
            rps=5.0 + i,
            p95_ms=100.0 + i * 10,
            error_rate=0.01 * (i + 1),
        )
        for i in range(n_points)
    ]
    codes = StatusSnapshot(
        labels=status_labels or ["2xx", "4xx", "5xx"],
        counts=status_counts or [800, 30, 5],
    )
    return ObservabilitySnapshot(series=series, status_codes=codes)


# ── Router tests: /admin/status/json ────────────────────────────


class TestStatusJson:
    """GET /admin/status/json — public JSON metrics endpoint."""

    def test_returns_operational_metrics(self, client):
        metrics = _make_metrics()
        with patch("fitness.routers.status.status_service") as mock_svc:
            mock_svc.get_public_metrics.return_value = metrics
            resp = client.get("/admin/status/json")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "operational"
        assert body["metrics"]["latency"]["p95_ms"] == 45.0
        assert body["metrics"]["error_rate"]["percentage"] == 0.01
        assert body["metrics"]["throughput"]["requests_per_second"] == 12.5

    def test_returns_degraded_status(self, client):
        metrics = _make_metrics(
            status="degraded", error_rate_pct=1.5, error_status="degraded"
        )
        with patch("fitness.routers.status.status_service") as mock_svc:
            mock_svc.get_public_metrics.return_value = metrics
            resp = client.get("/admin/status/json")

        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"

    def test_returns_outage_status(self, client):
        metrics = _make_metrics(
            status="outage", error_rate_pct=7.0, error_status="degraded"
        )
        with patch("fitness.routers.status.status_service") as mock_svc:
            mock_svc.get_public_metrics.return_value = metrics
            resp = client.get("/admin/status/json")

        assert resp.status_code == 200
        assert resp.json()["status"] == "outage"

    def test_null_latency(self, client):
        metrics = _make_metrics(latency_p95=None, latency_status="unknown")
        with patch("fitness.routers.status.status_service") as mock_svc:
            mock_svc.get_public_metrics.return_value = metrics
            resp = client.get("/admin/status/json")

        body = resp.json()
        assert body["metrics"]["latency"]["p95_ms"] is None
        assert body["metrics"]["latency"]["status"] == "unknown"


# ── Router tests: /admin/status/badge.svg ───────────────────────


class TestAvailabilityBadge:
    """GET /admin/status/badge.svg — SVG availability badge."""

    @pytest.mark.parametrize(
        "status,expected_color",
        [
            ("operational", "brightgreen"),
            ("degraded", "yellow"),
            ("outage", "red"),
        ],
    )
    def test_badge_color_by_status(self, client, status, expected_color):
        metrics = _make_metrics(status=status)
        with patch("fitness.routers.status.status_service") as mock_svc:
            mock_svc.get_public_metrics.return_value = metrics
            resp = client.get("/admin/status/badge.svg")

        assert resp.status_code == 200
        assert "image/svg+xml" in resp.headers["content-type"]
        assert f'fill="#{expected_color}"' in resp.text
        assert status.upper() in resp.text

    def test_unknown_status_gets_lightgrey(self, client):
        metrics = _make_metrics(status="unknown")
        with patch("fitness.routers.status.status_service") as mock_svc:
            mock_svc.get_public_metrics.return_value = metrics
            resp = client.get("/admin/status/badge.svg")

        assert resp.status_code == 200
        assert 'fill="#lightgrey"' in resp.text

    def test_badge_is_valid_svg(self, client):
        metrics = _make_metrics()
        with patch("fitness.routers.status.status_service") as mock_svc:
            mock_svc.get_public_metrics.return_value = metrics
            resp = client.get("/admin/status/badge.svg")

        assert "<svg" in resp.text
        assert "</svg>" in resp.text


# ── Router tests: /admin/status/uptime-badge.svg ────────────────


class TestUptimeBadge:
    """GET /admin/status/uptime-badge.svg — uptime percentage badge."""

    @pytest.mark.parametrize(
        "error_rate,expected_color,expected_uptime",
        [
            (0.0, "brightgreen", "100.00%"),
            (0.05, "brightgreen", "99.95%"),
            (0.1, "brightgreen", "99.90%"),
            (0.5, "green", "99.50%"),
            (1.0, "yellow", "99.00%"),
        ],
    )
    def test_uptime_color_and_value(
        self, client, error_rate, expected_color, expected_uptime
    ):
        metrics = _make_metrics(error_rate_pct=error_rate)
        with patch("fitness.routers.status.status_service") as mock_svc:
            mock_svc.get_public_metrics.return_value = metrics
            resp = client.get("/admin/status/uptime-badge.svg")

        assert resp.status_code == 200
        assert "image/svg+xml" in resp.headers["content-type"]
        assert f'fill="#{expected_color}"' in resp.text
        assert expected_uptime in resp.text

    def test_error_rate_capped_at_one(self, client):
        """Error rate above 1.0 is clamped, so uptime is min 99.00%."""
        metrics = _make_metrics(error_rate_pct=5.0)
        with patch("fitness.routers.status.status_service") as mock_svc:
            mock_svc.get_public_metrics.return_value = metrics
            resp = client.get("/admin/status/uptime-badge.svg")

        assert resp.status_code == 200
        assert "99.00%" in resp.text

    def test_uptime_badge_is_valid_svg(self, client):
        metrics = _make_metrics()
        with patch("fitness.routers.status.status_service") as mock_svc:
            mock_svc.get_public_metrics.return_value = metrics
            resp = client.get("/admin/status/uptime-badge.svg")

        assert "<svg" in resp.text
        assert "</svg>" in resp.text


# ── Router tests: /admin/status/ (authenticated dashboard) ──────


class TestStatusDashboard:
    """GET /admin/status/ — authenticated HTML dashboard."""

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/admin/status/")
        assert resp.status_code == 401

    def test_dashboard_renders_with_metrics(self, auth_client):
        metrics = _make_metrics()
        snapshot = _make_snapshot()
        with (
            patch("fitness.routers.status.status_service") as mock_svc,
            patch(
                "fitness.routers.status.get_safe_observability_snapshot",
                return_value=snapshot,
            ),
        ):
            mock_svc.get_public_metrics.return_value = metrics
            resp = auth_client.get("/admin/status/")

        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_dashboard_metrics_error_triggers_fallback(self, auth_client):
        """If status_service.get_public_metrics() raises, the router catches it
        and uses a minimal fallback dict.  The template expects nested keys
        (metrics.latency, etc.) that the fallback lacks, so the template
        rendering raises a Jinja2 UndefinedError.

        This test verifies that the exception path is exercised and documents
        the current behaviour.  A future fix would enrich the fallback dict
        so the template renders gracefully.
        """
        with (
            patch("fitness.routers.status.status_service") as mock_svc,
            patch(
                "fitness.routers.status.get_safe_observability_snapshot",
                return_value=_make_snapshot(),
            ),
            pytest.raises(Exception),  # noqa: B017
        ):
            mock_svc.get_public_metrics.side_effect = RuntimeError("boom")
            auth_client.get("/admin/status/")

    def test_dashboard_falls_back_on_bokeh_error(self, auth_client):
        """If Bokeh chart generation fails, an error div is shown."""
        metrics = _make_metrics()
        with (
            patch("fitness.routers.status.status_service") as mock_svc,
            patch(
                "fitness.routers.status.get_safe_observability_snapshot",
                side_effect=RuntimeError("bokeh failure"),
            ),
        ):
            mock_svc.get_public_metrics.return_value = metrics
            resp = auth_client.get("/admin/status/")

        assert resp.status_code == 200
        assert "Unable to load charts" in resp.text


# ── _generate_bokeh_charts unit tests ───────────────────────────


class TestGenerateBokehCharts:
    """Unit tests for _generate_bokeh_charts() helper."""

    def test_valid_snapshot_returns_script_and_div(self):
        from fitness.routers.status import _generate_bokeh_charts

        snapshot = _make_snapshot(n_points=5)
        script, div = _generate_bokeh_charts(snapshot)
        assert "<script" in script
        assert "<div" in div

    def test_none_snapshot_returns_error_div(self):
        from fitness.routers.status import _generate_bokeh_charts

        script, div = _generate_bokeh_charts(None)
        assert script == ""
        assert "No metrics data available" in div

    def test_empty_series_returns_error_div(self):
        from fitness.routers.status import _generate_bokeh_charts

        snapshot = ObservabilitySnapshot(
            series=[],
            status_codes=StatusSnapshot(labels=["2xx"], counts=[100]),
        )
        script, div = _generate_bokeh_charts(snapshot)
        assert script == ""
        assert "No metrics data available" in div

    def test_empty_status_codes_returns_error_div(self):
        from fitness.routers.status import _generate_bokeh_charts

        now = datetime.now(UTC)
        snapshot = ObservabilitySnapshot(
            series=[
                TimeSeriesPoint(timestamp=now, rps=1.0, p95_ms=50.0, error_rate=0.01)
            ],
            status_codes=None,
        )
        script, div = _generate_bokeh_charts(snapshot)
        assert script == ""
        assert "No metrics data available" in div

    def test_missing_series_attr_returns_error_div(self):
        from fitness.routers.status import _generate_bokeh_charts

        obj = SimpleNamespace()  # no series or status_codes attributes
        script, div = _generate_bokeh_charts(obj)
        assert script == ""
        assert "No metrics data available" in div

    def test_snapshot_with_zero_error_rate(self):
        """Charts handle zero error rates without division errors."""
        from fitness.routers.status import _generate_bokeh_charts

        snapshot = _make_snapshot(n_points=2)
        # Override error rates to zero
        for point in snapshot.series:
            point.error_rate = 0.0
        script, div = _generate_bokeh_charts(snapshot)
        assert "<script" in script

    def test_single_data_point(self):
        from fitness.routers.status import _generate_bokeh_charts

        snapshot = _make_snapshot(n_points=1)
        script, div = _generate_bokeh_charts(snapshot)
        assert "<script" in script
        assert "<div" in div


# ── get_safe_observability_snapshot unit tests ────────────────────


class TestSafeObservabilitySnapshot:
    """Direct unit tests for get_safe_observability_snapshot()."""

    def test_returns_12_time_series_points(self):
        from fitness.observability.safe_metrics import get_safe_observability_snapshot

        snapshot = get_safe_observability_snapshot()
        assert len(snapshot.series) == 12

    def test_time_series_rps_increases(self):
        from fitness.observability.safe_metrics import get_safe_observability_snapshot

        snapshot = get_safe_observability_snapshot()
        rps_values = [p.rps for p in snapshot.series]
        assert rps_values == sorted(rps_values)

    def test_status_codes_has_three_buckets(self):
        from fitness.observability.safe_metrics import get_safe_observability_snapshot

        snapshot = get_safe_observability_snapshot()
        assert snapshot.status_codes.labels == ["2xx", "4xx", "5xx"]
        assert len(snapshot.status_codes.counts) == 3

    def test_timestamps_are_chronological(self):
        from fitness.observability.safe_metrics import get_safe_observability_snapshot

        snapshot = get_safe_observability_snapshot()
        timestamps = [p.timestamp for p in snapshot.series]
        assert timestamps == sorted(timestamps)

    def test_error_rates_are_positive(self):
        from fitness.observability.safe_metrics import get_safe_observability_snapshot

        snapshot = get_safe_observability_snapshot()
        for p in snapshot.series:
            assert p.error_rate > 0


# ── StatusMetrics service unit tests ────────────────────────────


class TestStatusMetricsInit:
    """StatusMetrics.__init__ and deploy timestamp."""

    def test_default_git_sha(self):
        with patch.dict("os.environ", {}, clear=False):
            # Remove GIT_SHA if present
            import os

            original = os.environ.pop("GIT_SHA", None)
            try:
                svc = StatusMetrics()
                assert svc.git_sha == "dev"
            finally:
                if original is not None:
                    os.environ["GIT_SHA"] = original

    def test_custom_git_sha(self):
        with patch.dict("os.environ", {"GIT_SHA": "abc123def456"}):
            svc = StatusMetrics()
            assert svc.git_sha == "abc123def456"

    def test_deploy_timestamp_from_file(self, tmp_path):
        ts_file = tmp_path / "config" / ".deploy_timestamp"
        ts_file.parent.mkdir(parents=True)
        ts_file.write_text("1708600000.0")

        with patch(
            "fitness.services.status_metrics.Path",
            return_value=ts_file,
        ):
            svc = StatusMetrics()
            assert svc.deploy_timestamp == 1708600000.0

    def test_deploy_timestamp_fallback_on_missing_file(self):
        with patch(
            "fitness.services.status_metrics.Path",
        ) as mock_path:
            mock_path.return_value.exists.return_value = False
            svc = StatusMetrics()
            # Should fall back to current time (recent timestamp)
            assert svc.deploy_timestamp > 0

    def test_deploy_timestamp_fallback_on_invalid_content(self, tmp_path):
        ts_file = tmp_path / "config" / ".deploy_timestamp"
        ts_file.parent.mkdir(parents=True)
        ts_file.write_text("not-a-number")

        with patch(
            "fitness.services.status_metrics.Path",
            return_value=ts_file,
        ):
            svc = StatusMetrics()
            # Should fall back to current time
            assert svc.deploy_timestamp > 0


class TestDetermineStatus:
    """StatusMetrics._determine_status()."""

    def setup_method(self):
        self.svc = StatusMetrics()

    def test_outage_on_high_error_rate(self):
        assert self.svc._determine_status(5.0, 100.0) == "outage"
        assert self.svc._determine_status(10.0, None) == "outage"

    def test_degraded_on_moderate_error_rate(self):
        assert self.svc._determine_status(1.0, 100.0) == "degraded"
        assert self.svc._determine_status(3.0, 50.0) == "degraded"

    def test_degraded_on_high_latency(self):
        assert self.svc._determine_status(0.05, 5001.0) == "degraded"

    def test_operational_on_low_error_rate(self):
        assert self.svc._determine_status(0.05, 100.0) == "operational"
        assert self.svc._determine_status(0.0, 50.0) == "operational"

    def test_operational_on_none_latency_low_error(self):
        assert self.svc._determine_status(0.05, None) == "operational"

    def test_operational_between_01_and_1_error_rate(self):
        """Error rate between 0.1 and 1.0 with normal latency is still operational."""
        assert self.svc._determine_status(0.5, 100.0) == "operational"


class TestLatencyStatus:
    """StatusMetrics._latency_status()."""

    def test_none_returns_unknown(self):
        assert StatusMetrics._latency_status(None) == "unknown"

    def test_under_100_is_excellent(self):
        assert StatusMetrics._latency_status(50.0) == "excellent"
        assert StatusMetrics._latency_status(0.0) == "excellent"
        assert StatusMetrics._latency_status(99.9) == "excellent"

    def test_100_to_300_is_good(self):
        assert StatusMetrics._latency_status(100.0) == "good"
        assert StatusMetrics._latency_status(200.0) == "good"
        assert StatusMetrics._latency_status(299.9) == "good"

    def test_300_to_1000_is_fair(self):
        assert StatusMetrics._latency_status(300.0) == "fair"
        assert StatusMetrics._latency_status(500.0) == "fair"
        assert StatusMetrics._latency_status(999.9) == "fair"

    def test_above_1000_is_degraded(self):
        assert StatusMetrics._latency_status(1000.0) == "degraded"
        assert StatusMetrics._latency_status(5000.0) == "degraded"


class TestCalculateErrorRate:
    """StatusMetrics._calculate_error_rate()."""

    def setup_method(self):
        self.svc = StatusMetrics()

    def _make_counter_metric(self, samples):
        """Build a mock metric with samples list."""
        metric = MagicMock()
        metric.samples = [
            SimpleNamespace(name=s["name"], labels=s["labels"], value=s["value"])
            for s in samples
        ]
        return metric

    def test_no_counter_returns_zero(self):
        assert self.svc._calculate_error_rate({}) == 0.0

    def test_counter_without_samples_attr_returns_zero(self):
        metric = MagicMock(spec=[])  # no 'samples' attribute
        assert self.svc._calculate_error_rate({"fitness_request_total": metric}) == 0.0

    def test_all_2xx_returns_zero_error_rate(self):
        counter = self._make_counter_metric(
            [
                {
                    "name": "fitness_request_total_total",
                    "labels": {"status_code": "200"},
                    "value": 100,
                },
                {
                    "name": "fitness_request_total_total",
                    "labels": {"status_code": "201"},
                    "value": 50,
                },
            ]
        )
        result = self.svc._calculate_error_rate({"fitness_request_total": counter})
        assert result == 0.0

    def test_mixed_status_codes(self):
        counter = self._make_counter_metric(
            [
                {
                    "name": "fitness_request_total_total",
                    "labels": {"status_code": "200"},
                    "value": 90,
                },
                {
                    "name": "fitness_request_total_total",
                    "labels": {"status_code": "500"},
                    "value": 10,
                },
            ]
        )
        result = self.svc._calculate_error_rate({"fitness_request_total": counter})
        assert result == 10.0  # 10/100 * 100

    def test_all_5xx(self):
        counter = self._make_counter_metric(
            [
                {
                    "name": "fitness_request_total_total",
                    "labels": {"status_code": "500"},
                    "value": 50,
                },
                {
                    "name": "fitness_request_total_total",
                    "labels": {"status_code": "503"},
                    "value": 50,
                },
            ]
        )
        result = self.svc._calculate_error_rate({"fitness_request_total": counter})
        assert result == 100.0

    def test_zero_total_requests(self):
        counter = self._make_counter_metric(
            [
                {
                    "name": "fitness_request_total_created",
                    "labels": {},
                    "value": 1708000000,
                },
            ]
        )
        result = self.svc._calculate_error_rate({"fitness_request_total": counter})
        assert result == 0.0

    def test_4xx_not_counted_as_errors(self):
        counter = self._make_counter_metric(
            [
                {
                    "name": "fitness_request_total_total",
                    "labels": {"status_code": "200"},
                    "value": 80,
                },
                {
                    "name": "fitness_request_total_total",
                    "labels": {"status_code": "404"},
                    "value": 20,
                },
            ]
        )
        result = self.svc._calculate_error_rate({"fitness_request_total": counter})
        assert result == 0.0


class TestCalculateLatencyP95:
    """StatusMetrics._calculate_latency_p95()."""

    def setup_method(self):
        self.svc = StatusMetrics()

    def _make_histogram_metric(self, samples):
        """Build a mock histogram metric."""
        metric = MagicMock()
        metric.samples = [
            SimpleNamespace(name=s["name"], labels=s["labels"], value=s["value"])
            for s in samples
        ]
        return metric

    def test_no_histogram_returns_none(self):
        assert self.svc._calculate_latency_p95({}) is None

    def test_histogram_without_samples_attr_returns_none(self):
        metric = MagicMock(spec=[])
        assert (
            self.svc._calculate_latency_p95(
                {"fitness_request_duration_seconds": metric}
            )
            is None
        )

    def test_empty_buckets_returns_none(self):
        histogram = self._make_histogram_metric(
            [
                {
                    "name": "fitness_request_duration_seconds_bucket",
                    "labels": {"le": "+Inf"},
                    "value": 100,
                },
            ]
        )
        # Only +Inf bucket, which is skipped
        assert (
            self.svc._calculate_latency_p95(
                {"fitness_request_duration_seconds": histogram}
            )
            is None
        )

    def test_p95_from_histogram_buckets(self):
        histogram = self._make_histogram_metric(
            [
                {
                    "name": "fitness_request_duration_seconds_bucket",
                    "labels": {"le": "0.05"},
                    "value": 50,
                },
                {
                    "name": "fitness_request_duration_seconds_bucket",
                    "labels": {"le": "0.1"},
                    "value": 80,
                },
                {
                    "name": "fitness_request_duration_seconds_bucket",
                    "labels": {"le": "0.25"},
                    "value": 95,
                },
                {
                    "name": "fitness_request_duration_seconds_bucket",
                    "labels": {"le": "0.5"},
                    "value": 100,
                },
                {
                    "name": "fitness_request_duration_seconds_bucket",
                    "labels": {"le": "+Inf"},
                    "value": 100,
                },
            ]
        )
        result = self.svc._calculate_latency_p95(
            {"fitness_request_duration_seconds": histogram}
        )
        assert result is not None
        # p95_rank = 100 * 0.95 = 95, bucket 0.25 has cumulative 95,
        # so 0.25 * 1000 = 250ms
        assert result == 250.0

    def test_p95_falls_in_first_bucket(self):
        histogram = self._make_histogram_metric(
            [
                {
                    "name": "fitness_request_duration_seconds_bucket",
                    "labels": {"le": "0.01"},
                    "value": 100,
                },
                {
                    "name": "fitness_request_duration_seconds_bucket",
                    "labels": {"le": "+Inf"},
                    "value": 100,
                },
            ]
        )
        result = self.svc._calculate_latency_p95(
            {"fitness_request_duration_seconds": histogram}
        )
        assert result == 10.0  # 0.01 * 1000

    def test_invalid_le_label_skipped(self):
        histogram = self._make_histogram_metric(
            [
                {
                    "name": "fitness_request_duration_seconds_bucket",
                    "labels": {"le": "not_a_number"},
                    "value": 50,
                },
                {
                    "name": "fitness_request_duration_seconds_bucket",
                    "labels": {"le": "0.1"},
                    "value": 100,
                },
                {
                    "name": "fitness_request_duration_seconds_bucket",
                    "labels": {"le": "+Inf"},
                    "value": 100,
                },
            ]
        )
        result = self.svc._calculate_latency_p95(
            {"fitness_request_duration_seconds": histogram}
        )
        assert result is not None
        assert result == 100.0  # 0.1 * 1000

    def test_non_bucket_samples_ignored(self):
        histogram = self._make_histogram_metric(
            [
                {
                    "name": "fitness_request_duration_seconds_count",
                    "labels": {},
                    "value": 100,
                },
                {
                    "name": "fitness_request_duration_seconds_sum",
                    "labels": {},
                    "value": 50.0,
                },
                {
                    "name": "fitness_request_duration_seconds_bucket",
                    "labels": {"le": "0.2"},
                    "value": 100,
                },
                {
                    "name": "fitness_request_duration_seconds_bucket",
                    "labels": {"le": "+Inf"},
                    "value": 100,
                },
            ]
        )
        result = self.svc._calculate_latency_p95(
            {"fitness_request_duration_seconds": histogram}
        )
        assert result == 200.0  # 0.2 * 1000


class TestCalculateRps:
    """StatusMetrics._calculate_rps()."""

    def setup_method(self):
        self.svc = StatusMetrics()
        # Set a known deploy timestamp 60 seconds ago
        self.svc.deploy_timestamp = datetime.now(UTC).timestamp() - 60.0

    def _make_counter_metric(self, samples):
        metric = MagicMock()
        metric.samples = [
            SimpleNamespace(name=s["name"], labels=s["labels"], value=s["value"])
            for s in samples
        ]
        return metric

    def test_no_counter_returns_zero(self):
        assert self.svc._calculate_rps({}) == 0.0

    def test_counter_without_samples_attr_returns_zero(self):
        metric = MagicMock(spec=[])
        assert self.svc._calculate_rps({"fitness_request_total": metric}) == 0.0

    def test_calculates_rps_from_total_and_uptime(self):
        counter = self._make_counter_metric(
            [
                {
                    "name": "fitness_request_total_total",
                    "labels": {"status_code": "200"},
                    "value": 120,
                },
            ]
        )
        result = self.svc._calculate_rps({"fitness_request_total": counter})
        # 120 requests / ~60 seconds = ~2.0 RPS
        assert 1.5 < result < 2.5

    def test_zero_uptime_returns_zero(self):
        self.svc.deploy_timestamp = datetime.now(UTC).timestamp() + 100
        counter = self._make_counter_metric(
            [
                {
                    "name": "fitness_request_total_total",
                    "labels": {"status_code": "200"},
                    "value": 100,
                },
            ]
        )
        result = self.svc._calculate_rps({"fitness_request_total": counter})
        assert result == 0.0

    def test_non_total_samples_ignored(self):
        counter = self._make_counter_metric(
            [
                {
                    "name": "fitness_request_total_created",
                    "labels": {},
                    "value": 1708000000.0,
                },
                {
                    "name": "fitness_request_total_total",
                    "labels": {"status_code": "200"},
                    "value": 60,
                },
            ]
        )
        result = self.svc._calculate_rps({"fitness_request_total": counter})
        # Only the _total sample (60) should be counted, not the _created one
        assert 0.5 < result < 1.5


class TestCollectPrometheusMetrics:
    """StatusMetrics._collect_prometheus_metrics()."""

    def test_collects_from_registry(self):
        svc = StatusMetrics()

        mock_sample = SimpleNamespace(name="test_metric_total", labels={}, value=42.0)
        mock_metric = SimpleNamespace(name="test_metric", samples=[mock_sample])
        mock_collector = MagicMock()
        mock_collector.collect.return_value = [mock_metric]

        with patch("fitness.services.status_metrics.REGISTRY") as mock_registry:
            mock_registry._collector_to_names = {mock_collector: ["test_metric"]}
            result = svc._collect_prometheus_metrics()

        assert "test_metric" in result
        assert result["test_metric"].name == "test_metric"

    def test_empty_registry(self):
        svc = StatusMetrics()
        with patch("fitness.services.status_metrics.REGISTRY") as mock_registry:
            mock_registry._collector_to_names = {}
            result = svc._collect_prometheus_metrics()

        assert result == {}


class TestGetPublicMetrics:
    """StatusMetrics.get_public_metrics() integration."""

    def test_returns_expected_structure(self):
        svc = StatusMetrics()
        with patch.object(svc, "_collect_prometheus_metrics", return_value={}):
            result = svc.get_public_metrics()

        assert "status" in result
        assert "timestamp" in result
        assert "metrics" in result
        assert "updated_at" in result

        metrics = result["metrics"]
        assert "latency" in metrics
        assert "error_rate" in metrics
        assert "throughput" in metrics
        assert "deployment" in metrics

    def test_timestamp_is_utc_iso_format(self):
        svc = StatusMetrics()
        with patch.object(svc, "_collect_prometheus_metrics", return_value={}):
            result = svc.get_public_metrics()

        assert result["timestamp"].endswith("Z")
        assert result["updated_at"].endswith("Z")

    def test_version_is_truncated_to_8_chars(self):
        svc = StatusMetrics()
        svc.git_sha = "abcdef1234567890"
        with patch.object(svc, "_collect_prometheus_metrics", return_value={}):
            result = svc.get_public_metrics()

        assert result["metrics"]["deployment"]["version"] == "abcdef12"

    def test_operational_with_no_prometheus_data(self):
        svc = StatusMetrics()
        with patch.object(svc, "_collect_prometheus_metrics", return_value={}):
            result = svc.get_public_metrics()

        # No metrics data means zero error rate -> operational
        assert result["status"] == "operational"
        assert result["metrics"]["latency"]["p95_ms"] is None
        assert result["metrics"]["latency"]["status"] == "unknown"
        assert result["metrics"]["error_rate"]["percentage"] == 0.0
        assert result["metrics"]["error_rate"]["status"] == "healthy"
        assert result["metrics"]["throughput"]["requests_per_second"] == 0.0

    def test_hours_since_deploy_is_positive(self):
        svc = StatusMetrics()
        svc.deploy_timestamp = datetime.now(UTC).timestamp() - 7200  # 2 hours ago
        with patch.object(svc, "_collect_prometheus_metrics", return_value={}):
            result = svc.get_public_metrics()

        hours = result["metrics"]["deployment"]["hours_since_deploy"]
        assert 1.9 < hours < 2.1
