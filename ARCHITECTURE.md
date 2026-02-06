# Witness - AWS Architecture

## Migration: Azure Container Apps to AWS App Runner

Replatform migration (7R's) from Azure Container Apps to AWS App Runner,
keeping HCP Terraform VCS-driven workflow.

### AWS 7R's Migration Strategies

| Strategy | Description | This Project |
|----------|-------------|--------------|
| **Retire** | Decommission — app no longer needed | Retired old AKS manifests (`k8s/`) and Azure Container Apps module |
| **Retain** | Keep as-is, revisit later | N/A — full migration, nothing retained on Azure |
| **Relocate** | Move to AWS with zero changes (e.g., VMware Cloud on AWS) | N/A — not a VM-based workload |
| **Rehost** | Lift-and-shift to EC2, no code changes | N/A — chose managed container service over EC2 |
| **Replatform** | Lift, tinker, and shift — swap to managed equivalents | **Selected** — same app/image/port, swap Container Apps for App Runner |
| **Repurchase** | Drop-and-shop — switch to a SaaS product | N/A — custom application, no SaaS replacement |
| **Refactor** | Re-architect for cloud-native patterns | N/A — app already containerized, no redesign needed |

Architecture targets SAP-C02 800 score across all four domains:

- **Domain 1** - Design Solutions for Organizational Complexity (26%)
- **Domain 2** - Design for New Solutions (29%)
- **Domain 3** - Continuous Improvement for Existing Solutions (25%)
- **Domain 4** - Accelerate Workload Migration and Modernization (20%)

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
    │   └── Picard (picard.yml) - GHCR build/push
    │       └── Riker (riker.yml) - GHCR retag + GitHub Release
    │
    └── Tasha (tasha.yml) - Auto-rollback on failed applies
```

## SAP-C02 Domain Coverage

### Domain 1: Design Solutions for Organizational Complexity (26%)

- Multi-account ready IAM roles with least-privilege policies and trust boundaries
- HCP Terraform workspaces per environment (witness-dev, witness-prod) with VCS-driven applies
- KMS CMKs with per-service key policies, aliases, and configurable deletion windows
- CloudTrail enabled for management event audit logging with encrypted S3 storage
- AWS Config for continuous compliance recording and resource configuration history
- Separation of concerns via Terraform modules (networking, security, app-runner, observability, codepipeline)
- Tag-based resource management with default_tags propagation across all resources
- Centralized secrets management via Secrets Manager with KMS encryption

### Domain 2: Design for New Solutions (29%)

- App Runner for fully managed container hosting (no ECS/EKS cluster overhead)
- VPC connector for private subnet access from App Runner to internal resources
- GHCR container registry with image scanning, Cosign signing, and Trivy vulnerability analysis
- Secrets Manager with KMS-backed encryption and IAM-scoped access policies
- Auto-scaling configuration with min/max instance counts and max concurrency thresholds
- CloudWatch dashboards with request count, latency percentile, and CPU/memory utilization widgets
- CloudWatch metric alarms for 5xx error rates and p99 latency with SNS notifications
- CodePipeline/CodeBuild for optional CI/CD within AWS (validate + plan stages)

### Domain 3: Continuous Improvement for Existing Solutions (25%)

- CloudWatch Logs with configurable retention (30 days dev, 90 days prod) and KMS encryption
- Metric alarms with environment-appropriate thresholds (relaxed for dev, tight for prod)
- Crusher health check workflow validates container image, application endpoints, and Terraform state
- Tasha auto-rollback workflow triggers on failed HCP Terraform applies
- Multi-AZ NAT Gateways in prod for high availability, single AZ in dev for cost savings
- VPC Flow Logs for network traffic analysis and troubleshooting
- Security scanning pipeline: Checkov (CIS benchmarks), tfsec (HCL analysis), Trivy (config + image)

### Domain 4: Accelerate Workload Migration and Modernization (20%)

- **7R's strategy: Replatform** — swap Azure managed services for AWS equivalents with no app code changes (see table above)
- **Retire** applied to dead artifacts: removed AKS manifests (`k8s/`), deleted Azure Container Apps Terraform module
- **Retain** not applicable — full cutover, no workloads left on Azure
- Equivalent health check endpoints preserved (/healthz, /readyz)
- Same container image and port (8000), no application code changes required
- HCP Terraform cloud backend preserved (org: DefiantEmissary) across migration
- Service mapping documented: ACR->GHCR, Key Vault->Secrets Manager, VNet->VPC, Log Analytics->CloudWatch
- GitHub Actions CI/CD pipeline preserved with updated provider-specific steps
- DNS cutover strategy via princetonstrong.online domain
- Buildspec files for CodeBuild integration (validate.yml, plan.yml) enabling AWS-native CI option
