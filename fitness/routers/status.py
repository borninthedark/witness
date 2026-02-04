"""Admin-only status dashboard endpoints.

Provides system status information with Bokeh visualizations.
All metrics are aggregated and sanitized to prevent information leakage.
"""

from __future__ import annotations

from bokeh.embed import components
from bokeh.layouts import column
from bokeh.models import ColumnDataSource, HoverTool, LinearAxis, Range1d
from bokeh.plotting import figure
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from fitness.auth import current_active_user
from fitness.config import settings
from fitness.observability.safe_metrics import get_safe_observability_snapshot
from fitness.services.status_metrics import status_service
from fitness.staticfiles import templates

router = APIRouter(prefix="/admin/status", tags=["admin", "status"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/", response_class=HTMLResponse)
@limiter.limit("60/minute")
async def status_page(request: Request, user=Depends(current_active_user)):
    """Admin-only status dashboard page with Bokeh visualizations.

    Requires authentication. Rate limited to 60 requests per minute.
    """
    try:
        metrics = status_service.get_public_metrics()
    except Exception as e:
        # Fallback to minimal metrics if service fails
        metrics = {
            "status": "unknown",
            "timestamp": "",
            "metrics": {},
        }
        print(f"Warning: Failed to get status metrics: {e}")

    # Get Grafana snapshot URL from file (updated by automation)
    grafana_url = getattr(settings, "grafana_dashboard_url", None)

    # Generate Bokeh visualizations with error handling
    bokeh_script = ""
    bokeh_div = ""
    try:
        snapshot = get_safe_observability_snapshot()
        bokeh_script, bokeh_div = _generate_bokeh_charts(snapshot)
    except Exception as e:
        print(f"Warning: Failed to generate Bokeh charts: {e}")
        bokeh_div = '<div class="error">Unable to load charts at this time.</div>'

    return templates.TemplateResponse(
        "status.html",
        {
            "request": request,
            "status": metrics,
            "grafana_snapshot_url": grafana_url,
            "page_title": "System Status",
            "bokeh_script": bokeh_script,
            "bokeh_div": bokeh_div,
        },
    )


def _generate_bokeh_charts(snapshot) -> tuple[str, str]:
    """Generate Bokeh chart components for status dashboard.

    Args:
        snapshot: ObservabilitySnapshot with time series data

    Returns:
        Tuple of (script, div) for embedding in template
    """
    # Validate snapshot data
    if (
        not snapshot
        or not hasattr(snapshot, "series")
        or not snapshot.series
        or not hasattr(snapshot, "status_codes")
        or not snapshot.status_codes
    ):
        return "", '<div class="error">No metrics data available</div>'

    # Extract time series data
    times = [p.timestamp for p in snapshot.series]
    rps = [p.rps for p in snapshot.series]
    p95 = [p.p95_ms for p in snapshot.series]
    err_rate = [p.error_rate * 100.0 for p in snapshot.series]  # convert to %

    ts_source = ColumnDataSource(
        data={
            "timestamp": times,
            "rps": rps,
            "p95": p95,
            "error_rate": err_rate,
        }
    )

    # ===== Chart 1: Requests per Second =====
    p_rps = figure(
        x_axis_type="datetime",
        height=260,
        sizing_mode="stretch_width",
        title="Requests per Second (Last Hour)",
        toolbar_location=None,
    )
    p_rps.line("timestamp", "rps", source=ts_source, line_width=3, color="#f2c94c")
    p_rps.circle("timestamp", "rps", source=ts_source, size=6, color="#f2c94c")
    p_rps.yaxis.axis_label = "RPS"
    p_rps.add_tools(
        HoverTool(
            tooltips=[
                ("Time", "@timestamp{%H:%M:%S}"),
                ("RPS", "@rps{0.0}"),
            ],
            formatters={"@timestamp": "datetime"},
            mode="vline",
        )
    )

    # ===== Chart 2: p95 Latency + Error Rate (Dual Axis) =====
    p_latency = figure(
        x_axis_type="datetime",
        height=260,
        sizing_mode="stretch_width",
        title="p95 Latency & Error Rate",
        toolbar_location=None,
        x_range=p_rps.x_range,  # linked x-axis
    )

    # Primary axis: p95 latency
    p_latency.line(
        "timestamp",
        "p95",
        source=ts_source,
        line_width=3,
        color="#6fcf97",
        legend_label="p95 latency (ms)",
    )
    p_latency.yaxis.axis_label = "Latency (ms)"

    # Secondary axis: error rate
    max_err = max(err_rate) if err_rate else 1
    p_latency.extra_y_ranges = {"err_pct": Range1d(start=0, end=max_err * 1.3)}

    p_latency.add_layout(
        LinearAxis(y_range_name="err_pct", axis_label="Error Rate (%)"),
        "right",
    )

    p_latency.line(
        "timestamp",
        "error_rate",
        source=ts_source,
        line_width=2,
        line_dash="dashed",
        color="#eb5757",
        y_range_name="err_pct",
        legend_label="Error rate (%)",
    )

    p_latency.add_tools(
        HoverTool(
            tooltips=[
                ("Time", "@timestamp{%H:%M:%S}"),
                ("p95 (ms)", "@p95{0.0}"),
                ("Error rate (%)", "@error_rate{0.00}"),
            ],
            formatters={"@timestamp": "datetime"},
            mode="vline",
        )
    )
    p_latency.legend.location = "top_left"

    # ===== Chart 3: Status Code Distribution =====
    labels = snapshot.status_codes.labels
    counts = snapshot.status_codes.counts
    total = sum(counts) or 1
    percentages = [c * 100.0 / total for c in counts]

    status_source = ColumnDataSource(
        data={
            "label": labels,
            "count": counts,
            "pct": percentages,
        }
    )

    p_status = figure(
        x_range=labels,
        height=260,
        sizing_mode="stretch_width",
        title="Status Code Distribution",
        toolbar_location=None,
    )
    p_status.vbar(
        x="label",
        top="count",
        width=0.6,
        source=status_source,
        color="#56ccf2",
    )
    p_status.yaxis.axis_label = "Requests"
    p_status.add_tools(
        HoverTool(
            tooltips=[
                ("Status", "@label"),
                ("Count", "@count"),
                ("Percent", "@pct{0.0}%"),
            ]
        )
    )

    # Combine all charts vertically
    layout = column(
        p_rps,
        p_latency,
        p_status,
        sizing_mode="stretch_width",
    )

    script, div = components(layout)
    return script, div


@router.get("/json", response_class=JSONResponse)
@limiter.limit("60/minute")
async def status_json(request: Request):
    """Public status API endpoint (JSON).

    Returns aggregated metrics without sensitive labels or paths.
    Suitable for programmatic access and monitoring.

    Rate limited to 60 requests per minute.
    """
    metrics = status_service.get_public_metrics()
    return JSONResponse(content=metrics)


@router.get("/badge.svg")
@limiter.limit("120/minute")
async def availability_badge(request: Request):
    """Generate availability badge SVG.

    Displays current operational status as a shields.io-style badge.
    Rate limited to 120 requests per minute (higher limit for badge embedding).
    """
    metrics = status_service.get_public_metrics()
    status_text = metrics["status"].upper()

    # Determine badge color based on status
    color_map = {
        "operational": "brightgreen",
        "degraded": "yellow",
        "outage": "red",
    }
    color = color_map.get(metrics["status"], "lightgrey")

    # SVG badge template (shields.io style)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="140" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <mask id="a">
    <rect width="140" height="20" rx="3" fill="#fff"/>
  </mask>
  <g mask="url(#a)">
    <path fill="#555" d="M0 0h50v20H0z"/>
    <path fill="#{color}" d="M50 0h90v20H50z"/>
    <path fill="url(#b)" d="M0 0h140v20H0z"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">  # noqa: E501
    <text x="25" y="15" fill="#010101" fill-opacity=".3">status</text>
    <text x="25" y="14">status</text>
    <text x="95" y="15" fill="#010101" fill-opacity=".3">{status_text}</text>
    <text x="95" y="14">{status_text}</text>
  </g>
</svg>"""

    return Response(content=svg, media_type="image/svg+xml")


@router.get("/uptime-badge.svg")
@limiter.limit("120/minute")
async def uptime_badge(request: Request):
    """Generate uptime percentage badge SVG.

    Note: This requires Prometheus with recording rules for accurate 30-day data.
    For now, displays based on current error rate.
    """
    metrics = status_service.get_public_metrics()
    error_rate = metrics["metrics"]["error_rate"]["percentage"]

    # Estimate uptime from error rate (simplified)
    uptime = 100.0 - min(error_rate, 1.0)

    # Determine color
    if uptime >= 99.9:
        color = "brightgreen"
    elif uptime >= 99.5:
        color = "green"
    elif uptime >= 99.0:
        color = "yellow"
    else:
        color = "red"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="150" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <mask id="a">
    <rect width="150" height="20" rx="3" fill="#fff"/>
  </mask>
  <g mask="url(#a)">
    <path fill="#555" d="M0 0h60v20H0z"/>
    <path fill="#{color}" d="M60 0h90v20H60z"/>
    <path fill="url(#b)" d="M0 0h150v20H0z"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">  # noqa: E501
    <text x="30" y="15" fill="#010101" fill-opacity=".3">uptime</text>
    <text x="30" y="14">uptime</text>
    <text x="105" y="15" fill="#010101" fill-opacity=".3">{uptime:.2f}%</text>
    <text x="105" y="14">{uptime:.2f}%</text>
  </g>
</svg>"""

    return Response(content=svg, media_type="image/svg+xml")
