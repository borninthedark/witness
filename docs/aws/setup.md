# AWS Setup Guide

## Prerequisites

- AWS account with appropriate permissions
- HCP Terraform org: `DefiantEmissary`
- GitHub repo with Actions enabled

## HCP Terraform Workspace Variables

Both `witness-dev` and `witness-prod` need:

| Variable | Type | Category | Notes |
|----------|------|----------|-------|
| `secret_key` | sensitive | Terraform | Application secret key |
| `AWS_ACCESS_KEY_ID` | sensitive | Environment | Or use dynamic credentials |
| `AWS_SECRET_ACCESS_KEY` | sensitive | Environment | Or use dynamic credentials |

**Recommended:** Use [HCP Terraform dynamic provider credentials](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/dynamic-provider-credentials/aws-configuration) for AWS instead of static keys.

## GitHub Actions Secrets

| Secret | Used By | Notes |
|--------|---------|-------|
| `GHCR_TOKEN` | picard, riker | GitHub Container Registry access |
| `TF_API_TOKEN` | tasha, crusher | HCP Terraform API token |

## GitHub Actions Variables

| Variable | Used By | Example |
|----------|---------|---------|
| `AWS_REGION` | crusher | `us-east-1` |
| `APP_URL_DEV` | crusher | App Runner URL (after first apply) |
| `APP_URL_PROD` | crusher | `https://engage.princetonstrong.online` |
| `TF_CLOUD_ORG` | tasha, crusher | `DefiantEmissary` |
| `ENABLE_TERRAFORM` | laforge, tasha | `true` |

## Terraform Structure

```text
terraform/
├── modules/
│   ├── networking/      # VPC, subnets, NAT, IGW
│   ├── security/        # KMS, CloudTrail, Config
│   ├── app-runner/      # ECR, Secrets Manager, App Runner
│   ├── observability/   # CloudWatch logs, dashboards, alarms
│   └── codepipeline/    # CodePipeline, CodeBuild, S3
├── dev/                 # witness-dev workspace
└── prod/                # witness-prod workspace
```

## CI/CD Workflows

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| Data | `data.yml` | workflow_call | Lint, test |
| Picard | `picard.yml` | schedule/manual | GHCR build/push |
| Riker | `riker.yml` | after Picard | GHCR retag + GitHub Release |
| Worf | `worf.yml` | workflow_call | Checkov, tfsec, Trivy |
| La Forge | `laforge.yml` | push terraform/** | CI gate for HCP Terraform |
| Tasha | `tasha.yml` | schedule/manual | Auto-rollback |
| Crusher | `crusher.yml` | manual | Health checks |
| Troi | `troi.yml` | push/schedule | Docs, badges, reports |

## Container Images

Images are built and stored in **GitHub Container Registry (GHCR)**:

```bash
# Pull dev image
docker pull ghcr.io/borninthedark/witness:dev

# Pull release image
docker pull ghcr.io/borninthedark/witness:latest
```

Tags: `dev`, `latest`, `prod`, `v*.*.*`

## DNS

Update `engage.princetonstrong.online` to point to the App Runner
service URL after first successful `terraform apply`.

## First Deploy

1. Configure HCP Terraform workspace variables (AWS creds + `secret_key`)
2. Push terraform changes to trigger VCS workflow
3. After apply, note the `service_url` output
4. Update DNS to point to the App Runner URL
5. Trigger Picard to build first container image
