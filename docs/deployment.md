# Deployment Guide (Docker + Caddy)

> This deployment walkthrough complements FastAPI’s official guidance for [server machines / Gunicorn](https://fastapi.tiangolo.com/deployment/manually/#server-machine-and-server-program) and [Docker images](https://fastapi.tiangolo.com/deployment/docker/). The app uses the same Gunicorn-with-Uvicorn-worker pattern recommended in those docs.

# Build the application image

```bash
docker build -t fitness:latest -f Dockerfile .
```

If you prefer Podman, pass `--format docker` to preserve `HEALTHCHECK` behavior:

```bash
podman build --format docker -t localhost/fitness:latest -f Dockerfile .
```

The `Dockerfile`:
- Installs OS-level dependencies (curl, tzdata, libmagic).
- Installs Python requirements.
- Runs Gunicorn with Uvicorn workers.
- Exposes `/healthz` via a container healthcheck.

## Bare-metal / VM service (optional)

If you are not containerizing, follow the FastAPI manual deployment playbook and run Gunicorn directly on the server:

```bash
cd /opt/fitness
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
WEB_WORKERS=$(nproc) gunicorn -c gunicorn.conf.py fitness.main:app
```

- Keep this process behind a reverse proxy (Caddy/Nginx) for TLS, buffering, and static asset caching.
- Use `systemd` or a process supervisor (e.g. `systemd --user` example below) so Gunicorn restarts automatically after crashes or reboots.
- Do not use `--reload` outside of development; rely on rolling restarts or blue/green swaps for code changes.

## Local stack (Docker Compose)

1. Copy `.env.example` to `.env` and set secrets (ADMIN credentials, SMTP, TURNSTILE, etc.).
2. Apply database migrations once: `python scripts/db_upgrade.py` (or `alembic upgrade head`).
3. Launch the stack (Caddy will listen on `http://localhost:8000` for rootless compatibility):

```bash
docker compose up -d --build
docker compose logs -f app
```

3. Tear it down:

```bash
docker compose down
```

`docker-compose.yml` runs the FastAPI app plus a local Caddy proxy that serves static assets and fronts `/healthz`. The container entrypoint executes `alembic upgrade head` before starting Gunicorn (set `SKIP_DB_MIGRATIONS=1` if migrations are handled elsewhere).

## Security defaults

- Responses are wrapped with CSP/HSTS/Referrer headers via the `SecurityHeadersMiddleware`.
- SlowAPI enforces per-route rate limits (contact + `/api`) and a Cloudflare Turnstile challenge can be enabled by setting `TURNSTILE_SITE_KEY`/`TURNSTILE_SECRET_KEY`.
- The contact form rejects oversized payloads; remember to keep SMTP credentials/secret keys in a managed secret store for production.

## Systemd integration (optional, Podman pods)

```bash
podman generate systemd --name fitness --files --new
mkdir -p ~/.config/systemd/user
mv fitness*.service fitness*.pod ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now pod-fitness
```

Enable lingering for reboot persistence:

```bash
loginctl enable-linger "$USER"
```

## Health and updates

- `/healthz` powers Caddy and container healthchecks.
- Rebuild/push new image versions and restart the container inside the pod.
- For zero-downtime, build a second tag (blue/green) and swap the Caddy backend.

## Backups & retention

- Schedule encrypted backups for your database (SQLite file or managed DB) and any object/local storage buckets that host PDF assets.
- Keep a retention policy (e.g., daily for 7 days, weekly for 4 weeks, monthly for 6 months) and test restores periodically.

## Observability

- Logging: structured JSON written to stdout; each response includes `X-Request-ID`. Adjust `LOG_LEVEL` for production vs. debug.
- Metrics: scrape `http://<host>:8000/metrics` (or behind Caddy) with Prometheus. Default counters/histograms include method/path labels.
- Tracing: enable OTLP export by setting `ENABLE_TRACING=true`, `OTLP_ENDPOINT=https://otel-collector:4318/v1/traces`, and optional `OTLP_HEADERS` (`key=value,...`). Spans cover FastAPI routes, SQLAlchemy queries, and outgoing HTTPX calls.

## Static assets & PDFs

- Static assets are served with immutable cache headers and fingerprinted query strings via `asset_url(...)`. Rolling deploys automatically bust caches because the hash comes from the file contents.
- The résumé PDF endpoint emits `ETag` and `Last-Modified` headers so proxies/clients can send conditional requests instead of downloading duplicate binaries.

## Azure Container Apps

Azure Container Apps provides a serverless container platform with automatic scaling, built-in HTTPS, and scale-to-zero capability.

### Architecture

```
Internet -> HTTPS Ingress (Auto TLS) -> Container Apps Environment
                                              |
                                        [witness app]
                                        - FastAPI container
                                        - System-assigned identity
                                        - Auto-scaling (0-N replicas)
                                              |
                                        Log Analytics Workspace
```

### Deployment

```bash
cd deploy/terraform/container-apps

# Authenticate with HCP Terraform
terraform login

# Initialize and deploy
terraform init
terraform plan -var-file="dev/terraform.tfvars" -out=tfplan
terraform apply tfplan
```

### Compose-Style Configuration

The Terraform module uses a compose-style approach familiar to Docker Compose users:

```hcl
container_apps = {
  app = {
    name          = "witness"
    revision_mode = "Single"

    template = {
      min_replicas = 1
      max_replicas = 3
      containers = [{
        name   = "witness"
        image  = "ghcr.io/borninthedark/witness:latest"
        cpu    = "0.5"
        memory = "1Gi"
        env    = [...]
        liveness_probe  = { path = "/healthz", ... }
        readiness_probe = { path = "/readyz", ... }
      }]
    }

    ingress = {
      external_enabled = true
      target_port      = 8000
    }
  }
}
```

### Key Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `min_replicas` | `1` | Minimum replicas (set to `0` for scale-to-zero) |
| `max_replicas` | `3` | Maximum replicas |
| `container_cpu` | `0.5` | CPU allocation |
| `container_memory` | `1Gi` | Memory allocation |
| `revision_mode` | `Single` | `Single` or `Multiple` for traffic splitting |

### Environment-Specific Configuration

**Development (scale-to-zero):**
```hcl
# dev/terraform.tfvars
min_replicas       = 0
max_replicas       = 2
log_retention_days = 7
```

**Production:**
```hcl
# prod/terraform.tfvars
min_replicas       = 1
max_replicas       = 5
log_retention_days = 90
```

See `deploy/terraform/container-apps/README.md` for complete configuration options.

## Terraform Infrastructure

Terraform configuration for Azure Container Apps lives in `deploy/terraform/container-apps/`.

**Module:** `Azure/container-apps/azure` v0.4.0

**State Management:** HCP Terraform (organization: `DefiantEmissary`, workspace: `witness-container-apps`).

**Required GitHub Secrets:**
- `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` - OIDC authentication
- `TF_API_TOKEN` - HCP Terraform API token
- `APP_SECRET_KEY` - Application secret

**Required GitHub Variables:**
- `TF_CLOUD_ORG` - HCP Terraform organization (`DefiantEmissary`)

## CI/CD Pipeline

GitHub Actions workflows use Star Trek TNG-themed names and run in sequence:

**Application Pipeline:**
```
Data - CI (lint, test, validate)

Picard - Build (build, scan, sign, push to GHCR)
    |-> Riker - Release (retag, semantic versioning)
    |-> Troi - Docs (badges, reports)
```

**Infrastructure Pipeline (CLI-driven via La Forge):**
```
Push to deploy/terraform/** (or manual dispatch)
    |-> La Forge - Deploy (calls Data CI + Worf Security, then plan/apply)
        |-> terraform plan -var-file=<env>/terraform.tfvars
        |-> terraform apply (manual dispatch only, action=apply)
        |-> [on failure] Tasha - Destroy (auto-rollback)
```

**Workflows:**
| Workflow | File | Trigger |
|----------|------|---------|
| Data - CI | `data.yml` | Push/PR to main |
| Picard - Build | `picard.yml` | Scheduled / manual |
| Riker - Release | `riker.yml` | After Picard succeeds |
| Troi - Docs | `troi.yml` | After Picard / scheduled |
| Worf - Security | `worf.yml` | PR to terraform paths / manual |
| La Forge - Deploy | `laforge.yml` | Push to terraform paths / manual |
| Crusher - Health | `crusher.yml` | Manual |
| Tasha - Destroy | `tasha.yml` | Scheduled (auto-rollback) / manual |

## CI notes

Picard builds and scans the image with Buildah using the Containerfile (pushing OCI-formatted artifacts to GHCR). Images are signed with Cosign using Sigstore keyless OIDC. Riker pulls the `dev` tag from GHCR and retags for release (no rebuild).

## Security notes

- Run containers rootless whenever possible (Podman or Docker).
- Mount `/app` read-only and enable `--read-only` plus tmpfs if you do not write to disk (`:Z` helps on SELinux hosts).
- Drop Linux capabilities (`--cap-drop=ALL`) once verified.
- The contact form logs to `fitness/data/contact-messages.jsonl`; secure that directory and avoid committing it.
