# Public Status Dashboard Implementation Plan

**Mission Objective:** Build a public-facing status dashboard showcasing platform health without exposing security-sensitive information.

**Strategy:** Aggregate -> Scrub -> Snapshot -> Publish

---

## Implementation Phases

### Phase 1: Prometheus Recording Rules (3-4 hours)

**Objective:** Create sanitized metrics aggregations in Azure Monitor Managed Prometheus

**Files to create:**
- `deploy/azure/prometheus-rules/public-status.yaml`

**Implementation:**

```yaml
# deploy/azure/prometheus-rules/public-status.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: public-status-rules
  namespace: kube-system
data:
  public-status.yml: |
    groups:
      - name: public_status
        interval: 60s
        rules:
          # Request latency p95 (milliseconds)
          - record: public:http_request_p95_ms
            expr: |
              histogram_quantile(0.95,
                sum(rate(http_request_duration_seconds_bucket{job="fitness-app"}[5m])) by (le)
              ) * 1000

          # HTTP error rate (percentage)
          - record: public:http_error_rate_pct
            expr: |
              (
                sum(rate(http_requests_total{status=~"5.."}[5m]))
                /
                sum(rate(http_requests_total[5m]))
              ) * 100

          # Requests per second (rolling 5 min window)
          - record: public:http_rps
            expr: |
              sum(rate(http_requests_total{job="fitness-app"}[5m]))

          # 30-day availability (SLA style)
          - record: public:availability_pct_30d
            expr: |
              (
                1 - (
                  sum(increase(http_requests_total{status=~"5.."}[30d]))
                  /
                  sum(increase(http_requests_total[30d]))
                )
              ) * 100

          # Time since last deploy (hours)
          - record: public:deploy_age_hours
            expr: |
              (time() - app_deploy_timestamp_seconds) / 3600

          # Synthetic probe success rate
          - record: public:probe_success_rate
            expr: |
              avg_over_time(probe_success{job="blackbox"}[5m])
```

**Deployment:**
```bash
kubectl apply -f deploy/azure/prometheus-rules/public-status.yaml

# Verify rules loaded
kubectl get configmap -n kube-system public-status-rules
```

**Effort:** 3-4 hours (includes testing and validation)

---

### Phase 2: FastAPI Status Endpoints (4-6 hours)

**Objective:** Create `/status` page and `/status.json` API endpoint

**Files to create/modify:**
- `fitness/routers/status.py` (new)
- `fitness/templates/status.html` (new)
- `fitness/services/status_metrics.py` (new)
- `fitness/main.py` (add router)

#### 2.1 Status Service

```python
# fitness/services/status_metrics.py
"""Public status metrics service."""

from datetime import datetime, timedelta
from typing import Dict, Any
import httpx
from prometheus_client import REGISTRY

from fitness.config import settings


class StatusMetrics:
    """Fetch and format public status metrics."""

    def __init__(self):
        self.prom_url = settings.PROMETHEUS_QUERY_URL  # From Azure config
        self.auth = (settings.METRICS_USERNAME, settings.METRICS_PASSWORD)

    async def get_public_metrics(self) -> Dict[str, Any]:
        """Fetch sanitized public metrics from recording rules."""
        async with httpx.AsyncClient() as client:
            # Query the public:* recording rules
            queries = {
                "latency_p95_ms": "public:http_request_p95_ms",
                "error_rate_pct": "public:http_error_rate_pct",
                "requests_per_sec": "public:http_rps",
                "availability_30d": "public:availability_pct_30d",
                "uptime_hours": "public:deploy_age_hours",
                "probe_success": "public:probe_success_rate",
            }

            metrics = {}
            for key, query in queries.items():
                response = await client.get(
                    f"{self.prom_url}/api/v1/query",
                    params={"query": query},
                    auth=self.auth,
                    timeout=5.0,
                )
                data = response.json()
                if data["status"] == "success" and data["data"]["result"]:
                    metrics[key] = float(data["data"]["result"][0]["value"][1])
                else:
                    metrics[key] = None

            return {
                "status": "operational" if metrics["error_rate_pct"] < 1.0 else "degraded",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "metrics": {
                    "latency": {
                        "p95_ms": round(metrics["latency_p95_ms"], 2),
                        "status": self._latency_status(metrics["latency_p95_ms"]),
                    },
                    "error_rate": {
                        "percentage": round(metrics["error_rate_pct"], 3),
                        "status": "healthy" if metrics["error_rate_pct"] < 0.1 else "warning",
                    },
                    "throughput": {
                        "requests_per_second": round(metrics["requests_per_sec"], 1),
                    },
                    "availability": {
                        "30_day_percentage": round(metrics["availability_30d"], 2),
                        "sla_met": metrics["availability_30d"] >= 99.9,
                    },
                    "deployment": {
                        "hours_since_deploy": round(metrics["uptime_hours"], 1),
                        "version": settings.GIT_SHA[:8] if settings.GIT_SHA else "unknown",
                    },
                    "probes": {
                        "success_rate": round(metrics["probe_success"] * 100, 1),
                    },
                },
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }

    @staticmethod
    def _latency_status(latency_ms: float) -> str:
        """Classify latency health."""
        if latency_ms < 100:
            return "excellent"
        elif latency_ms < 300:
            return "good"
        elif latency_ms < 1000:
            return "fair"
        else:
            return "degraded"


status_service = StatusMetrics()
```

#### 2.2 Status Router

```python
# fitness/routers/status.py
"""Public status dashboard endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, HTMLResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from fitness.services.status_metrics import status_service
from fitness.templates import templates

router = APIRouter(prefix="/status", tags=["status"])
limiter = Limiter(key_func=get_remote_address)


@router.get("/", response_class=HTMLResponse)
@limiter.limit("60/minute")
async def status_page(request: Request):
    """Public status dashboard page."""
    metrics = await status_service.get_public_metrics()
    return templates.TemplateResponse(
        "status.html",
        {
            "request": request,
            "status": metrics,
            "page_title": "System Status",
        },
    )


@router.get("/json", response_class=JSONResponse)
@limiter.limit("60/minute")
async def status_json(request: Request):
    """Public status API endpoint (JSON)."""
    metrics = await status_service.get_public_metrics()
    return JSONResponse(content=metrics)


@router.get("/badge.svg")
@limiter.limit("120/minute")
async def availability_badge(request: Request):
    """Generate availability badge SVG."""
    metrics = await status_service.get_public_metrics()
    availability = metrics["metrics"]["availability"]["30_day_percentage"]

    color = "brightgreen" if availability >= 99.9 else "yellow" if availability >= 99.5 else "red"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="120" height="20">
  <linearGradient id="b" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <rect rx="3" width="120" height="20" fill="#555"/>
  <rect rx="3" x="75" width="45" height="20" fill="{color}"/>
  <text x="37.5" y="15" fill="#fff" font-family="Verdana" font-size="11">Uptime</text>
  <text x="97.5" y="15" fill="#fff" font-family="Verdana" font-size="11">{availability:.1f}%</text>
</svg>"""

    return Response(content=svg, media_type="image/svg+xml")
```

#### 2.3 Status Template

```html
<!-- fitness/templates/status.html -->
{% extends "base.html" %}

{% block title %}{{ page_title }}{% endblock %}

{% block content %}
<section class="status-dashboard lcars-frame">
  <header class="lcars-bar">
    <h1>⭘ SYSTEM STATUS</h1>
    <span class="status-indicator {{ status.status }}">{{ status.status | upper }}</span>
  </header>

  <div class="metrics-grid">
    <!-- Latency -->
    <div class="metric-card">
      <h3>Response Time</h3>
      <div class="metric-value">{{ status.metrics.latency.p95_ms }}ms</div>
      <div class="metric-label">95th percentile</div>
      <div class="status-badge {{ status.metrics.latency.status }}">
        {{ status.metrics.latency.status }}
      </div>
    </div>

    <!-- Error Rate -->
    <div class="metric-card">
      <h3>Error Rate</h3>
      <div class="metric-value">{{ "%.3f"|format(status.metrics.error_rate.percentage) }}%</div>
      <div class="metric-label">5xx responses</div>
      <div class="status-badge {{ status.metrics.error_rate.status }}">
        {{ status.metrics.error_rate.status }}
      </div>
    </div>

    <!-- Throughput -->
    <div class="metric-card">
      <h3>Throughput</h3>
      <div class="metric-value">{{ status.metrics.throughput.requests_per_second }}</div>
      <div class="metric-label">requests/sec</div>
    </div>

    <!-- Availability -->
    <div class="metric-card highlight">
      <h3>30-Day Availability</h3>
      <div class="metric-value">{{ "%.2f"|format(status.metrics.availability["30_day_percentage"]) }}%</div>
      <div class="metric-label">
        SLA Target: 99.9%
        {% if status.metrics.availability.sla_met %}✅{% else %}⚠️{% endif %}
      </div>
    </div>

    <!-- Deployment -->
    <div class="metric-card">
      <h3>Current Deployment</h3>
      <div class="metric-value">{{ status.metrics.deployment.version }}</div>
      <div class="metric-label">{{ status.metrics.deployment.hours_since_deploy }}h ago</div>
    </div>

    <!-- Probes -->
    <div class="metric-card">
      <h3>Health Checks</h3>
      <div class="metric-value">{{ status.metrics.probes.success_rate }}%</div>
      <div class="metric-label">synthetic probes</div>
    </div>
  </div>

  <!-- Grafana Embed -->
  <section class="grafana-embed">
    <h2>Live Metrics Dashboard</h2>
    <iframe
      src="{{ grafana_snapshot_url }}"
      width="100%" height="550" frameborder="0" loading="lazy"
      title="Grafana Metrics Dashboard">
    </iframe>
    <p class="lcars-note">Metrics aggregate · No customer data · Updated hourly</p>
  </section>

  <footer class="status-footer">
    <p>Last updated: {{ status.updated_at }}</p>
    <p><a href="/status/json">JSON API</a> | <a href="/status/badge.svg">Badge</a></p>
  </footer>
</section>
{% endblock %}
```

**Effort:** 4-6 hours (includes template styling and testing)

---

### Phase 3: Grafana Dashboard & Snapshot (6-8 hours)

**Objective:** Create public Grafana dashboard with automated snapshot publishing

#### 3.1 Grafana Dashboard

**Manual Steps (one-time):**

1. **Login to Azure Managed Grafana:**
   ```bash
   az grafana show --name fitness-grafana --resource-group utopia-rg --query url -o tsv
   ```

2. **Create "Public Status" Dashboard:**
   - New Dashboard → Import
   - Use recording rules as data sources:
     - `public:http_request_p95_ms`
     - `public:http_error_rate_pct`
     - `public:http_rps`
     - `public:availability_pct_30d`
   - Configure panels with **no labels**, only aggregated values
   - Set refresh interval: 5m

3. **Enable Public Snapshot:**
   - Dashboard Settings → Sharing
   - Enable "Snapshot"
   - Set expiry: 24 hours
   - **Important:** Disable "External Enabled" for kill-switch capability

4. **Save Dashboard JSON:**
   ```bash
   # Export dashboard definition for version control
   curl -H "Authorization: Bearer $GRAFANA_API_KEY" \
     https://fitness-grafana.grafana.azure.com/api/dashboards/uid/public-status \
     > deploy/grafana/public-status-dashboard.json
   ```

#### 3.2 Snapshot Automation

**Files to create:**
- `scripts/update_grafana_snapshot.py`

**Note:** Grafana snapshot automation is handled by the `Troi - Docs` workflow (`.github/workflows/troi.yml`) which runs after Data CI and on a schedule when `ENABLE_STATUS_DASHBOARD=true`.

```python
# scripts/update_grafana_snapshot.py
"""Update Grafana public status snapshot."""

import os
import httpx
from pathlib import Path

GRAFANA_URL = os.getenv("GRAFANA_URL")
GRAFANA_API_KEY = os.getenv("GRAFANA_API_KEY")
DASHBOARD_UID = os.getenv("DASHBOARD_UID", "public-status")

def create_snapshot():
    """Create new public snapshot, delete old one."""
    headers = {"Authorization": f"Bearer {GRAFANA_API_KEY}"}

    # Get dashboard
    resp = httpx.get(
        f"{GRAFANA_URL}/api/dashboards/uid/{DASHBOARD_UID}",
        headers=headers,
    )
    dashboard = resp.json()["dashboard"]

    # Create snapshot
    snapshot_resp = httpx.post(
        f"{GRAFANA_URL}/api/snapshots",
        headers=headers,
        json={
            "dashboard": dashboard,
            "name": "Public Status Dashboard",
            "expires": 86400,  # 24 hours
            "external": False,  # Internal only for security
        },
    )
    snapshot = snapshot_resp.json()

    # Save URL to config file
    snapshot_url = f"{GRAFANA_URL}/dashboard/snapshot/{snapshot['key']}"
    Path("fitness/config/grafana_snapshot_url.txt").write_text(snapshot_url)

    print(f"✅ Snapshot created: {snapshot_url}")
    print(f"   Expires: {snapshot['expires']}")

if __name__ == "__main__":
    create_snapshot()
```

**Effort:** 6-8 hours (dashboard design + automation testing)

---

### Phase 4: Security & Rate Limiting (2-3 hours)

**Objective:** Ensure status endpoints don't leak sensitive data

#### 4.1 Update Config

```python
# fitness/config.py additions

class Settings(BaseSettings):
    # ... existing settings ...

    # Prometheus query endpoint (Azure Managed Prometheus)
    PROMETHEUS_QUERY_URL: str = "https://fitness-prometheus.azuremonitor.com"

    # Grafana snapshot URL (updated by automation)
    @property
    def GRAFANA_SNAPSHOT_URL(self) -> str:
        snapshot_file = Path(__file__).parent / "config" / "grafana_snapshot_url.txt"
        if snapshot_file.exists():
            return snapshot_file.read_text().strip()
        return ""

    # Git SHA for version tracking (set by CI)
    GIT_SHA: str = os.getenv("GIT_SHA", "dev")
```

#### 4.2 Add Deploy Timestamp Metric

```python
# fitness/observability/metrics.py additions

from prometheus_client import Gauge

# Track deployment timestamp
DEPLOY_TIMESTAMP = Gauge(
    "app_deploy_timestamp_seconds",
    "Unix timestamp of current deployment",
)

# Set on startup
DEPLOY_TIMESTAMP.set_to_current_time()
```

#### 4.3 Security Checklist

- [x] No `/metrics` endpoint exposed publicly (already protected with HTTP Basic Auth)
- [x] Recording rules strip all labels (PII, paths, IPs)
- [x] Grafana snapshots are read-only
- [x] Rate limiting on status endpoints (60 r/m via slowapi)
- [x] Snapshot expiry enforced (24h)
- [x] No external snapshot sharing enabled
- [x] Status page has no user session data

**Effort:** 2-3 hours (testing + validation)

---

### Phase 5: Frontend Integration (3-4 hours)

**Objective:** Embed status dashboard in resume site

#### 5.1 Add Status Link to Navigation

```html
<!-- fitness/templates/base.html -->
<nav class="lcars-nav">
  <a href="/">Home</a>
  <a href="/certifications">Certifications</a>
  <a href="/resume">Resume</a>
  <a href="/status" class="status-link">⭘ Status</a>
  <a href="/contact">Contact</a>
</nav>
```

#### 5.2 Add Status Badge to Footer

```html
<!-- fitness/templates/base.html footer -->
<footer>
  <img src="/status/badge.svg" alt="Uptime" />
  <p>Powered by FastAPI · Monitored with Azure</p>
</footer>
```

#### 5.3 QR Code for Printed Resume

```python
# fitness/services/pdf_resume.py additions
import qrcode

def add_status_qr_to_resume(canvas, status_url: str):
    """Add QR code linking to status dashboard."""
    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(status_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    # Add to resume footer with label "Live Status →"
```

**Effort:** 3-4 hours (design + testing)

---

## Total Implementation Effort

| Phase | Description | Effort |
|-------|-------------|--------|
| 1 | Prometheus Recording Rules | 3-4 hours |
| 2 | FastAPI Status Endpoints | 4-6 hours |
| 3 | Grafana Dashboard & Automation | 6-8 hours |
| 4 | Security & Rate Limiting | 2-3 hours |
| 5 | Frontend Integration | 3-4 hours |
| **Total** | **End-to-end implementation** | **18-25 hours** |

---

## Deployment Checklist

### Prerequisites

- [ ] Azure Managed Prometheus enabled on AKS cluster
- [ ] Azure Managed Grafana instance provisioned
- [ ] Grafana API key created (Viewer role)
- [ ] GitHub secrets configured:
  - `GRAFANA_URL`
  - `GRAFANA_API_KEY`

### Deployment Order

1. [ ] Deploy Prometheus recording rules to AKS
2. [ ] Wait 5 minutes for rules to populate
3. [ ] Create Grafana dashboard manually
4. [ ] Test snapshot creation
5. [ ] Deploy FastAPI status endpoints
6. [ ] Enable GitHub Actions snapshot automation
7. [ ] Test end-to-end flow
8. [ ] Add status link to navigation

### Testing

- [ ] Verify recording rules return data: `kubectl logs -n kube-system prometheus-0`
- [ ] Test `/status/json` returns valid metrics
- [ ] Test `/status/badge.svg` renders correctly
- [ ] Verify rate limiting (61st request in 1 min should fail)
- [ ] Test Grafana snapshot updates hourly
- [ ] Validate no sensitive data in public metrics

### Monitoring

- [ ] Set up alert if snapshot automation fails
- [ ] Monitor status endpoint error rate
- [ ] Track snapshot view count (Grafana analytics)

---

## Security Validation

**Threat Model:**
- **Attacker goal:** Discover infrastructure details for exploitation
- **Mitigations:**
  - Recording rules strip all labels (no paths, IPs, user agents)
  - Snapshots are read-only (no PromQL injection)
  - No `/metrics` endpoint exposed (protected with HTTP Basic Auth)
  - Rate limiting prevents enumeration attacks
  - Snapshot expiry limits data freshness for attackers

**Red Team Test:**
```bash
# Attempt to access raw metrics (should fail)
curl https://engage.princetonstrong.online/metrics

# Attempt to inject PromQL via snapshot (should be read-only)
# Snapshots don't expose query strings

# Attempt rate limit bypass
for i in {1..100}; do curl https://engage.princetonstrong.online/status/json; done
# Should see 429 Too Many Requests after 60 requests
```

---

## Documentation Updates

Add to `docs/observability.md`:
- Public status dashboard architecture
- Recording rules explanation
- Grafana snapshot automation
- Security considerations for public metrics

Add to `README.md`:
- Link to live status dashboard
- Embed availability badge

---

## Future Enhancements

### Phase 6 (Optional)

- **Historical trends**: 7-day latency/availability charts
- **Incident timeline**: Display past outages with RCA links
- **Component status**: Break down by service (API, auth, storage)
- **Subscription**: Email/SMS alerts for status changes (via SendGrid)
- **Dark mode toggle**: LCARS light/dark theme switcher

**Effort:** +10-15 hours

---

## Final Notes

This implementation provides a **living proof-of-concept** that demonstrates:
- Modern observability practices (Prometheus + Grafana)
- Security-first design (aggregate before publish)
- Production-ready automation (GitHub Actions)
- Professional presentation (LCARS aesthetic)

The dashboard becomes a **portfolio piece** itself - showing technical depth without exposing vulnerabilities. Perfect for a resume site.
