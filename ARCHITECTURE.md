# Witness - AWS Architecture

## Migration: Azure Container Apps to AWS App Runner

Replatform migration (6Rs) from Azure Container Apps to AWS App Runner,
keeping HCP Terraform VCS-driven workflow.

Architecture targets SAP-C02 800 score, emphasizing:

- **Domain 1** - Design for Organizational Complexity
- **Domain 4** - Design for New Solutions (Migration/Modernization)

## Service Mapping

| Azure Service | AWS Service | Module |
|---------------|-------------|--------|
| Container Apps | App Runner | `terraform-aws-modules/app-runner/aws` |
| ACR | ECR | `terraform-aws-modules/ecr/aws` |
| Key Vault | Secrets Manager | `aws_secretsmanager_secret` |
| VNet | VPC | `terraform-aws-modules/vpc/aws` |
| Log Analytics | CloudWatch Logs | `terraform-aws-modules/cloudwatch/aws` |
| Azure Monitor | CloudWatch Alarms/Dashboards | `terraform-aws-modules/cloudwatch/aws` |
| N/A | KMS | `terraform-aws-modules/kms/aws` |
| N/A | CloudTrail | `aws_cloudtrail` |
| N/A | AWS Config | `aws_config_configuration_recorder` |
| N/A | CodePipeline | `aws_codepipeline` |

## Architecture Diagram

```text
                    ┌──────────────────────────────────────────────┐
                    │              AWS Account                      │
                    │                                              │
   GitHub ──push──> │  ┌──────────┐    ┌──────────┐               │
   Actions          │  │   ECR    │───>│App Runner │──> :8000      │
   (Picard)         │  └──────────┘    └────┬─────┘               │
                    │                       │                      │
                    │                  ┌────┴─────┐                │
                    │                  │   VPC    │                │
                    │                  │ Connector│                │
                    │                  └────┬─────┘                │
                    │                       │                      │
                    │  ┌─────────┐   ┌─────┴──────┐  ┌─────────┐ │
                    │  │Secrets  │   │  Private    │  │   KMS   │ │
                    │  │Manager  │   │  Subnets    │  │ (CMK)   │ │
                    │  └─────────┘   └────────────┘  └─────────┘ │
                    │                                              │
                    │  ┌───────────┐  ┌───────────┐               │
                    │  │CloudWatch │  │CloudTrail │               │
                    │  │Logs/Alarms│  │+ S3 Logs  │               │
                    │  └───────────┘  └───────────┘               │
                    └──────────────────────────────────────────────┘

   HCP Terraform (VCS-driven)
   ├── witness-dev   → terraform/dev/
   └── witness-prod  → terraform/prod/
```

## Directory Layout

```text
terraform/
├── modules/
│   ├── networking/      # VPC, subnets, NAT, IGW
│   ├── security/        # KMS, CloudTrail, Config, IAM
│   ├── app-runner/      # ECR, Secrets Manager, App Runner
│   ├── observability/   # CloudWatch log groups, dashboards, alarms
│   └── codepipeline/    # CodePipeline, CodeBuild, S3 artifacts
├── dev/                 # Dev workspace (HCP Terraform: witness-dev)
└── prod/                # Prod workspace (HCP Terraform: witness-prod)
```

## Module Versions

| Module | Version | Purpose |
|--------|---------|---------|
| `terraform-aws-modules/app-runner/aws` | 1.2.2 | App Runner service, IAM, VPC connector, auto-scaling |
| `terraform-aws-modules/vpc/aws` | 6.6.0 | VPC, subnets, NAT, IGW, route tables |
| `terraform-aws-modules/kms/aws` | 4.2.0 | KMS keys for ECR, Secrets Manager, App Runner |
| `terraform-aws-modules/s3-bucket/aws` | 5.10.0 | CodePipeline artifact bucket, CloudTrail bucket |
| `terraform-aws-modules/ecr/aws` | 3.2.0 | ECR repository with lifecycle, scanning, KMS |
| `terraform-aws-modules/iam/aws` | 6.4.0 | IAM roles for CodeBuild, CodePipeline |
| `terraform-aws-modules/cloudwatch/aws` | 5.7.2 | Log groups, dashboards, metric alarms |

## CI/CD Pipeline

```text
Push to main
    │
    ├── terraform/** changed
    │   └── La Forge (laforge.yml)
    │       ├── Data CI (lint, test)
    │       └── Worf Security (Checkov, Trivy, tfsec)
    │           └── HCP Terraform VCS auto plan/apply
    │
    ├── Application code changed
    │   └── Picard (picard.yml) - ECR build/push
    │       └── Riker (riker.yml) - ECR retag + GitHub Release
    │
    └── Tasha (tasha.yml) - Auto-rollback on failed applies
```

## SAP-C02 Domain Coverage

### Domain 1: Organizational Complexity

- Multi-account ready (IAM roles, cross-account patterns)
- HCP Terraform workspaces per environment (dev/prod)
- KMS CMKs with key policies and aliases
- CloudTrail for API audit logging
- AWS Config for compliance recording

### Domain 2: New Solutions

- App Runner for managed container hosting (no ECS/EKS overhead)
- VPC connector for private subnet access
- ECR with image scanning and lifecycle policies
- Secrets Manager with automatic rotation support

### Domain 3: Migration

- Replatform (6Rs): Container Apps -> App Runner
- Equivalent health checks (/healthz, /readyz)
- Same container image, same port (8000)
- HCP Terraform backend preserved (organization: DefiantEmissary)

### Domain 4: Cost Optimization

- App Runner auto-scaling (pay per request in provisioned mode)
- NAT Gateway in single AZ for dev (multi-AZ for prod)
- S3 Intelligent-Tiering for artifact buckets
- CloudWatch log retention policies
