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
| `APP_URL_PROD` | crusher | `https://engage.princetonstrong.com` |
| `TF_CLOUD_ORG` | tasha, crusher | `DefiantEmissary` |
| `ENABLE_TERRAFORM` | laforge, tasha | `true` |

## Terraform Structure

```text
terraform/
├── bootstrap/             # OIDC, IAM, Route 53 hosted zone
├── modules/
│   ├── networking/        # VPC, subnets, NAT, IGW
│   ├── security/          # KMS, CloudTrail, Config
│   ├── app-runner/        # ECR, Secrets Manager, App Runner
│   ├── dns/               # Route 53 records, App Runner custom domain
│   ├── observability/     # CloudWatch logs, dashboards, alarms
│   └── codepipeline/      # CodePipeline, CodeBuild, S3
├── dev/                   # witness-dev workspace
└── prod/                  # witness-prod workspace
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

Domain `princetonstrong.com` is registered via Route 53 Domains in the
bootstrap configuration. The hosted zone is auto-created by the domain
registration. Custom domains (`engage.princetonstrong.com` for dev,
`staging.princetonstrong.com` for prod) are wired via the `dns` module.

## First Deploy

1. Run `terraform apply` in `terraform/bootstrap/` (registers domain, creates
   OIDC + IAM)
2. Note the `hosted_zone_id` output
3. Configure HCP Terraform workspace variables (dynamic provider credentials,
   `secret_key`, `admin_password`, `hosted_zone_id`)
4. Push terraform changes to trigger VCS workflow
5. After apply, note the `service_url` and `custom_domain_url` outputs
6. Trigger Picard to build first container image
