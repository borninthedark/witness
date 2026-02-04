# Status Dashboard Setup Guide

This guide walks through deploying the public status dashboard for production use.

## Quick Start

The status dashboard is already implemented in the codebase with:
- [x] Public-safe metrics endpoints (`/status`, `/status/json`)
- [x] SVG badges for embedding (`/status/badge.svg`, `/status/uptime-badge.svg`)
- [x] Rate limiting (60 req/min for pages, 120 req/min for badges)
- [x] Prometheus recording rules (sanitized, aggregated metrics)
- [x] Grafana automation scripts
- [x] Navigation integration

## Prerequisites

- Azure Managed Prometheus enabled on AKS cluster
- Azure Managed Grafana instance provisioned
- GitHub repository secrets configured

## Step 1: Deploy Prometheus Recording Rules

Deploy the recording rules to your AKS cluster:

```bash
kubectl apply -f deploy/azure/prometheus-rules/public-status.yaml
```

Verify deployment:

```bash
kubectl get configmap -n kube-system public-status-rules
kubectl describe configmap -n kube-system public-status-rules
```

Wait 1-2 minutes for Prometheus to reload the rules, then verify they're evaluating:

```bash
# If you have Prometheus UI access
# Navigate to Status > Rules and look for "public_status" group

# Or check metrics directly (if Prometheus port-forwarded)
curl 'http://localhost:9090/api/v1/query?query=public:http_request_p95_ms'
```

## Step 2: Configure Azure Managed Grafana

### Create Dashboard

1. Login to Azure Managed Grafana:
   ```bash
   az grafana show --name fitness-grafana --resource-group utopia-rg --query url -o tsv
   ```

2. Create new dashboard:
   - **Name:** "Public Status Dashboard"
   - **UID:** `public-status` (important!)

3. Add panels for each recording rule:

   **Panel 1: Request Latency**
   - Metric: `public:http_request_p95_ms`
   - Visualization: Stat / Graph
   - Unit: milliseconds (ms)
   - Thresholds: Green <200ms, Yellow <1000ms, Red ≥1000ms

   **Panel 2: Error Rate**
   - Metric: `public:http_error_rate_pct`
   - Visualization: Stat / Gauge
   - Unit: percent (0-100)
   - Thresholds: Green <0.1%, Yellow <1%, Red ≥1%

   **Panel 3: Requests Per Second**
   - Metric: `public:http_rps`
   - Visualization: Graph / Stat
   - Unit: requests/sec

   **Panel 4: 30-Day Availability**
   - Metric: `public:availability_pct_30d`
   - Visualization: Stat / Gauge
   - Unit: percent (0-100)
   - Thresholds: Green ≥99.9%, Yellow ≥99.5%, Red <99.5%

4. Configure dashboard settings:
   - Refresh interval: **5 minutes**
   - Time range: **Last 24 hours**
   - Timezone: **Browser time**

5. **Save** the dashboard (ensure UID is `public-status`)

### Create API Key

In Grafana UI:

1. Navigate to **Configuration** > **API Keys**
2. Click **Add API key**
3. Settings:
   - **Name:** `snapshot-automation`
   - **Role:** `Viewer` (minimum required)
   - **Time to live:** No expiration
4. Copy the API key (you won't see it again!)

## Step 3: Configure GitHub Secrets

In your GitHub repository settings:

### Secrets (Settings > Secrets and variables > Actions > Secrets)

Add the following secrets:

```bash
GRAFANA_URL=https://fitness-grafana.grafana.azure.com
GRAFANA_API_KEY=<your-api-key-from-step-2>
```

Optionally, for auto-committing snapshot URLs:

```bash
GHCR_PAT=<your-personal-access-token>
```

### Variables (Settings > Secrets and variables > Actions > Variables)

Add the following variables:

```bash
ENABLE_STATUS_DASHBOARD=true
DASHBOARD_UID=public-status
```

## Step 4: Test Locally

Before enabling automation, test the snapshot creation manually:

```bash
# Set environment variables
export GRAFANA_URL="https://fitness-grafana.grafana.azure.com"
export GRAFANA_API_KEY="<your-api-key>"
export DASHBOARD_UID="public-status"

# Run the script
python scripts/update_grafana_snapshot.py

# Verify output
cat fitness/config/grafana_snapshot_url.txt
```

Expected output:

```text
Fetching dashboard: public-status
Creating snapshot for dashboard: Public Status Dashboard
✅ Snapshot created: https://fitness-grafana.grafana.azure.com/dashboard/snapshot/abc123xyz
   Expires in: 86400 seconds
   Saved to: fitness/config/grafana_snapshot_url.txt
```

## Step 5: Enable GitHub Actions Workflow

The workflow (`.github/workflows/troi.yml`) handles status snapshot updates as part of the Troi - Docs pipeline:

- Runs every hour on the hour (when `ENABLE_STATUS_DASHBOARD=true`)
- Creates a new snapshot with 24-hour expiry
- Commits the updated snapshot URL to `fitness/config/grafana_snapshot_url.txt`

Trigger manually to test:

```bash
# Via GitHub UI: Actions > Troi - Docs > Run workflow

# Or via gh CLI:
gh workflow run troi.yml
```

Check the workflow run:

```bash
gh run list --workflow=troi.yml
gh run view <run-id>
```

## Step 6: Deploy to Production

Deploy the updated application with status dashboard:

```bash
# Build new container image
podman build --format docker -t ghcr.io/borninthedark/witness:latest -f Containerfile .

# Push to registry
podman push ghcr.io/borninthedark/witness:latest

# Update Kubernetes deployment
kubectl rollout restart deployment/fitness-app -n fitness

# Verify deployment
kubectl rollout status deployment/fitness-app -n fitness
```

## Step 7: Verify

1. **Status Page:** Visit `https://engage.princetonstrong.online/status`
2. **JSON API:** `https://engage.princetonstrong.online/status/json`
3. **Status Badge:** `https://engage.princetonstrong.online/status/badge.svg`
4. **Uptime Badge:** `https://engage.princetonstrong.online/status/uptime-badge.svg`

Check that:
- [x] Metrics are displaying (not `null` or `--`)
- [x] Grafana snapshot iframe is loading (if workflow has run)
- [x] Status badges are rendering
- [x] Rate limiting works (61st request in 1 minute returns 429)

## Monitoring

### Check Workflow Health

Monitor the automated snapshot updates:

```bash
# View recent workflow runs
gh run list --workflow=troi.yml --limit 10

# View specific run with logs
gh run view <run-id> --log
```

### Alert on Failures

Add a GitHub Action notification workflow to alert when snapshot updates fail:

```yaml
# In .github/workflows/alert-on-failure.yml
# (Optional - implement if needed)
```

### Verify Snapshot Freshness

The snapshot URL should update hourly. Check last commit:

```bash
git log -1 --oneline fitness/config/grafana_snapshot_url.txt
```

## Troubleshooting

### Metrics showing null/undefined

**Cause:** Prometheus recording rules not evaluating yet

**Fix:**
1. Check recording rules are deployed:
   ```bash
   kubectl get configmap -n kube-system public-status-rules
   ```
2. Check Prometheus logs for errors:
   ```bash
   kubectl logs -n kube-system prometheus-0 | grep ERROR
   ```
3. Verify base metrics exist:
   ```bash
   # Check that app is exposing metrics
   kubectl port-forward -n fitness svc/fitness-app 8000:8000
   curl http://localhost:8000/metrics | grep fitness_request
   ```

### Grafana snapshot not updating

**Cause:** Workflow not running or failing

**Fix:**
1. Check workflow is enabled and scheduled
2. Verify secrets are set correctly
3. Check workflow runs for errors:
   ```bash
   gh run list --workflow=troi.yml
   gh run view <run-id> --log
   ```

### Rate limiting not working

**Cause:** slowapi middleware not initialized or IP detection failing

**Fix:**
1. Check slowapi is installed: `pip list | grep slowapi`
2. Verify middleware in `fitness/main.py`
3. Test with curl:
   ```bash
   for i in {1..65}; do curl -s https://engage.princetonstrong.online/status/json; done
   ```
   Should see 429 after 60 requests

### Dashboard shows "No data"

**Cause:** Recording rules not matching Prometheus metrics

**Fix:**
1. Check metric names match in both:
   - `fitness/observability/metrics.py` (source metrics)
   - `deploy/azure/prometheus-rules/public-status.yaml` (recording rules)
2. Verify job labels:
   ```promql
   # Should return data
   fitness_request_total{job="fitness-app"}
   ```

## Security Validation

### Red Team Test

```bash
# 1. Attempt to access raw metrics (should require auth)
curl https://engage.princetonstrong.online/metrics
# Expected: 401 Unauthorized

# 2. Test rate limiting
for i in {1..65}; do
  curl -s -o /dev/null -w "%{http_code}\n" https://engage.princetonstrong.online/status/json
done
# Expected: First 60 return 200, rest return 429

# 3. Verify no sensitive data in JSON
curl https://engage.princetonstrong.online/status/json | jq .
# Expected: No paths, IPs, user agents, or other PII

# 4. Check snapshot is read-only
# Visit snapshot URL - should not allow editing or queries
```

### Expected Security Posture

- [x] `/metrics` protected with HTTP Basic Auth
- [x] Recording rules strip all labels
- [x] Snapshots are internal-only (external=false)
- [x] Rate limiting prevents enumeration
- [x] No PII in public metrics
- [x] Snapshot expiry limits stale data

## Cost Estimate

### Azure Resources

- **Prometheus recording rules:** Included in Azure Monitor
- **Grafana snapshots:** ~100KB each, 720/month = ~70MB total
- **API calls:** 720 snapshot creates/month (hourly)
- **Storage:** Negligible (<1MB sustained)

**Estimated monthly cost:** <$1 USD

### GitHub Actions

- **Workflow runs:** 720/month (hourly schedule)
- **Runtime:** ~30 seconds per run
- **Minutes used:** 360 minutes/month

**Estimated monthly cost:** Free tier (2000 min/month)

## Maintenance

### Monthly Tasks

- [ ] Review snapshot workflow success rate
- [ ] Check for Prometheus recording rule errors
- [ ] Verify Grafana dashboard is current
- [ ] Test rate limiting still effective
- [ ] Scan for any new sensitive metrics

### Quarterly Tasks

- [ ] Rotate Grafana API key
- [ ] Review and update recording rules
- [ ] Test full disaster recovery (rebuild dashboard)
- [ ] Update documentation with lessons learned

### Annual Tasks

- [ ] Security audit of public metrics
- [ ] Cost optimization review
- [ ] Evaluate new Grafana features (public dashboards, etc.)

## Reference

- Implementation plan: `docs/status-dashboard-implementation.md`
- Grafana setup: `deploy/grafana/README.md`
- Recording rules: `deploy/azure/prometheus-rules/public-status.yaml`
- Automation script: `scripts/update_grafana_snapshot.py`
- Workflow: `.github/workflows/troi.yml`
