# Grafana Public Status Dashboard

This directory contains configuration for the public-facing status dashboard.

## Setup

### 1. Create Dashboard in Azure Managed Grafana

1. Log in to Azure Managed Grafana:
   ```bash
   az grafana show --name fitness-grafana --resource-group utopia-rg --query url -o tsv
   ```

2. Create a new dashboard:
   - Name: "Public Status Dashboard"
   - UID: `public-status`

3. Add panels using Prometheus recording rules:
   - `public:http_request_p95_ms` - Request Latency
   - `public:http_error_rate_pct` - Error Rate
   - `public:http_rps` - Requests Per Second
   - `public:availability_pct_30d` - 30-Day Availability

4. Configure panels:
   - **No labels** - All metrics are pre-aggregated
   - Refresh interval: 5m
   - Time range: Last 24 hours

5. Save dashboard and note the UID

### 2. Create Grafana API Key

```bash
# In Grafana UI: Configuration > API Keys > Add API key
# Role: Viewer (minimum required for snapshots)
# Name: snapshot-automation
# Expiration: No expiration
```

### 3. Configure GitHub Secrets

In your GitHub repository settings, add:

- **Secrets:**
  - `GRAFANA_URL`: `https://fitness-grafana.grafana.azure.com`
  - `GRAFANA_API_KEY`: (API key from step 2)
  - `GH_PAT`: (Optional) Personal Access Token for commits

- **Variables:**
  - `ENABLE_STATUS_DASHBOARD`: `true`
  - `DASHBOARD_UID`: `public-status`

### 4. Test Snapshot Creation

```bash
# Set environment variables
export GRAFANA_URL="https://fitness-grafana.grafana.azure.com"
export GRAFANA_API_KEY="your-api-key"
export DASHBOARD_UID="public-status"

# Run script
python scripts/update_grafana_snapshot.py

# Check output
cat fitness/config/grafana_snapshot_url.txt
```

### 5. Enable Workflow

The GitHub Actions workflow (`.github/workflows/update-status-snapshot.yml`) will:
- Run every hour on the hour
- Create a new snapshot with 24-hour expiry
- Commit the updated snapshot URL

## Dashboard Export

To export the dashboard JSON for version control:

```bash
curl -H "Authorization: Bearer $GRAFANA_API_KEY" \
  "$GRAFANA_URL/api/dashboards/uid/public-status" \
  | jq '.dashboard' > deploy/grafana/public-status-dashboard.json
```

## Troubleshooting

### Snapshot not updating

1. Check workflow runs in GitHub Actions
2. Verify secrets are set correctly
3. Check Grafana API key permissions
4. Ensure `ENABLE_STATUS_DASHBOARD` variable is `true`

### Dashboard not showing data

1. Verify Prometheus recording rules are deployed:
   ```bash
   kubectl get configmap -n kube-system public-status-rules
   ```

2. Check Prometheus logs for rule evaluation errors:
   ```bash
   kubectl logs -n kube-system prometheus-0 | grep public_status
   ```

3. Query recording rules directly:
   ```bash
   # If you have Prometheus port-forwarded
   curl 'http://localhost:9090/api/v1/query?query=public:http_request_p95_ms'
   ```

### Snapshot expires too quickly

Adjust expiry in `scripts/update_grafana_snapshot.py`:
```python
"expires": 86400,  # 24 hours (change to 0 for no expiry)
```

Note: Longer expiries may expose stale data if automation fails.

## Security Considerations

- ✅ Snapshots are **internal only** (`external: false`)
- ✅ Recording rules strip all sensitive labels
- ✅ No `/metrics` endpoint exposed (protected with HTTP Basic Auth)
- ✅ Snapshot URLs are read-only (no PromQL execution)
- ✅ 24-hour expiry limits stale data exposure

## Cost Optimization

Grafana snapshot storage is minimal, but consider:
- Snapshots auto-delete after expiry
- Hourly updates = ~720 snapshots/month (old ones removed)
- Each snapshot is ~50-100KB

Total storage: <10MB sustained
