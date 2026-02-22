# Variable Reference

All variables used across bootstrap (local apply), HCP Terraform workspaces,
and GitHub Actions.

## Bootstrap (Local Apply)

Bootstrap is applied locally from `terraform/bootstrap/`. A template is
provided — copy it and fill in your values:

```bash
cd terraform/bootstrap
cp bootstrap.tfvars.example bootstrap.tfvars  # edit with your contact info
terraform init
terraform apply -var-file="bootstrap.tfvars"
```

`bootstrap.tfvars` is git-ignored. Only the `.example` template is tracked.

### Project

| Variable | Default | Description |
|----------|---------|-------------|
| `project` | `witness` | Resource naming prefix |
| `aws_region` | `us-east-1` | AWS region |
| `tfc_organization` | `DefiantEmissary` | HCP Terraform org name |
| `tfc_workspace_names` | `["witness-dev", "witness-prod"]` | Workspaces that need AWS access |

### Domain Registration

| Variable | Default | Sensitive | Description |
|----------|---------|-----------|-------------|
| `domain_name` | `princetonstrong.com` | no | Domain to register via Route 53 Domains |
| `contact_first_name` | — | no | Registrant first name |
| `contact_last_name` | — | no | Registrant last name |
| `contact_email` | — | yes | Registrant email (WHOIS privacy on) |
| `contact_phone` | — | yes | Registrant phone (`+1.5551234567` format) |
| `contact_address_line_1` | — | yes | Registrant street address |
| `contact_city` | — | no | Registrant city |
| `contact_state` | — | no | Registrant state/province |
| `contact_zip_code` | — | no | Registrant zip/postal code |
| `contact_country_code` | `US` | no | Registrant country code |

### Bootstrap Outputs

| Output | Where to Use | Description |
|--------|--------------|-------------|
| `role_arn` | HCP TF workspace env vars | IAM role ARN for dynamic credentials |
| `hosted_zone_id` | HCP TF workspace TF vars | Route 53 zone ID (both workspaces) |
| `workspace_env_vars` | Reference only | Shows env vars to set on workspaces |
| `domain_name` | Reference only | Registered domain name |
| `domain_expiration` | Reference only | Domain expiration date |

## HCP Terraform Workspace Variables

Set these in the HCP Terraform UI or API for each workspace.

### Environment Variables (both workspaces)

These enable OIDC dynamic provider credentials (no static AWS keys).

| Variable | Category | Sensitive | Source | Description |
|----------|----------|-----------|--------|-------------|
| `TFC_AWS_PROVIDER_AUTH` | env | no | Set to `true` | Enable dynamic AWS credentials |
| `TFC_AWS_RUN_ROLE_ARN` | env | no | Bootstrap `role_arn` output | IAM role to assume |

### Terraform Variables (both workspaces)

| Variable | Category | Sensitive | Default | Description |
|----------|----------|-----------|---------|-------------|
| `secret_key` | terraform | yes | — | Application secret key (FastAPI) |
| `admin_password` | terraform | yes | — | Admin console password |
| `hosted_zone_id` | terraform | no | — | Route 53 zone ID (from bootstrap output) |
| `alarm_email` | terraform | no | `null` | Email for CloudWatch alarm SNS delivery |

### Terraform Variables with Defaults

These have defaults in `variables.tf` and only need to be set if overriding.

| Variable | Dev Default | Prod Default | Description |
|----------|-------------|--------------|-------------|
| `domain_name` | `princetonstrong.com` | `princetonstrong.com` | Root domain |
| `image_tag` | `dev` | `latest` | Container image tag |
| `instance_cpu` | `512` | `1024` | App Runner CPU (millicores) |
| `instance_memory` | `1024` | `2048` | App Runner memory (MB) |
| `auto_deploy` | `true` | `false` | Auto-deploy on ECR push |
| `min_size` | `1` | `2` | Minimum App Runner instances |
| `max_size` | `3` | `5` | Maximum App Runner instances |
| `max_concurrency` | `100` | `100` | Max concurrent requests per instance |
| `log_retention_days` | `30` | `90` | CloudWatch log retention |
| `log_level` | `INFO` | `INFO` | Application log level |
| `database_url` | `sqlite:////app/data/fitness.db` | `sqlite:////app/data/fitness.db` | Database connection string |
| `admin_username` | `admin` | `admin` | Admin console username |
| `vpc_cidr` | `10.0.0.0/16` | `10.0.0.0/16` | VPC CIDR block |
| `enable_codepipeline` | `false` | `false` | Enable CodePipeline module |
| `enable_media` | `false` | `false` | Enable Media CDN module (S3 + CloudFront) |
| `monthly_budget_limit` | — | `100` | Monthly budget alert threshold (prod only) |

## GitHub Actions Secrets

Set in GitHub repo Settings > Secrets and variables > Actions > Secrets.

| Secret | Used By | Description |
|--------|---------|-------------|
| `AWS_ROLE_ARN` | La Forge, Riker | GitHub Actions OIDC role ARN for ECR push |
| `TF_API_TOKEN` | Tasha, Crusher | HCP Terraform API token for workspace queries |
| `GRAFANA_URL` | Troi | Grafana instance URL (optional, for status snapshots) |
| `GRAFANA_API_KEY` | Troi | Grafana API key (optional, for status snapshots) |

`GITHUB_TOKEN` is automatically provided by GitHub Actions and does not need
to be configured.

## GitHub Actions Variables

Set in GitHub repo Settings > Secrets and variables > Actions > Variables.

| Variable | Used By | Example | Description |
|----------|---------|---------|-------------|
| `AWS_REGION` | Crusher | `us-east-1` | AWS region for health checks |
| `APP_URL_DEV` | Crusher | `https://engage.princetonstrong.com` | Dev App Runner URL |
| `APP_URL_PROD` | Crusher | `https://staging.princetonstrong.com` | Prod App Runner URL |
| `TF_CLOUD_ORG` | Tasha, Crusher | `DefiantEmissary` | HCP Terraform org name |
| `ENABLE_TERRAFORM` | Picard, Tasha | `true` | Enable Terraform workflows |
| `ENABLE_STATUS_DASHBOARD` | Troi | `true` | Enable Grafana snapshot updates |
| `DASHBOARD_UID` | Troi | `public-status` | Grafana dashboard UID |

## Setup Checklist

### 1. Bootstrap (one-time, local)

```bash
cd terraform/bootstrap
cp bootstrap.tfvars.example bootstrap.tfvars   # fill in contact info
terraform init
terraform apply -var-file="bootstrap.tfvars"
# Note the hosted_zone_id and role_arn outputs
```

### 2. HCP Terraform Workspaces

For **both** `witness-dev` and `witness-prod`:

- [ ] Set env var `TFC_AWS_PROVIDER_AUTH` = `true`
- [ ] Set env var `TFC_AWS_RUN_ROLE_ARN` = `<role_arn from bootstrap>`
- [ ] Set TF var `hosted_zone_id` = `<hosted_zone_id from bootstrap>`
- [ ] Set TF var `secret_key` (sensitive)
- [ ] Set TF var `admin_password` (sensitive)

### 3. GitHub Repository

Secrets:
- [ ] `GHCR_TOKEN` — GitHub PAT with `write:packages` scope
- [ ] `TF_API_TOKEN` — HCP Terraform team or user token

Variables:
- [ ] `TF_CLOUD_ORG` = `DefiantEmissary`
- [ ] `ENABLE_TERRAFORM` = `true`
- [ ] `APP_URL_DEV` — set after first dev apply (App Runner service URL)
- [ ] `APP_URL_PROD` — set after first prod apply
