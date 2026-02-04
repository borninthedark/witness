# Azure Container Apps Terraform Deployment

This directory contains Terraform configuration for deploying the application to Azure Container Apps using the official `Azure/container-apps/azure` module.

## Overview

Azure Container Apps provides a serverless container platform that abstracts away infrastructure management while providing:

- Automatic scaling (including scale to zero)
- Built-in HTTPS ingress with automatic TLS
- Traffic splitting for blue/green deployments
- Integration with Dapr for microservices
- Log Analytics integration

## Architecture

```
                                    ┌─────────────────────────────────────┐
                                    │    Azure Container Apps Environment │
                                    │                                     │
Internet ──▶ HTTPS Ingress ──────▶ │  ┌─────────────────────────────┐    │
             (Auto TLS)             │  │     Container App: app      │    │
                                    │  │  ┌─────────────────────┐    │    │
                                    │  │  │   witness container │    │    │
                                    │  │  │   - FastAPI app     │    │    │
                                    │  │  │   - Port 8000       │    │    │
                                    │  │  │   - Health probes   │    │    │
                                    │  │  └─────────────────────┘    │    │
                                    │  │                             │    │
                                    │  │  Secrets: secret-key        │    │
                                    │  │  Identity: System-assigned  │    │
                                    │  └─────────────────────────────┘    │
                                    │                                     │
                                    │  Log Analytics Workspace            │
                                    └─────────────────────────────────────┘
```

## Compose-Style Configuration

The module uses a compose-style approach where multiple container apps can be defined in a single `container_apps` map. This provides a familiar developer experience similar to Docker Compose:

```hcl
container_apps = {
  app = {
    name          = var.app_name
    revision_mode = "Single"

    template = {
      min_replicas = 1
      max_replicas = 3

      containers = [
        {
          name   = "witness"
          image  = var.container_image
          cpu    = "0.5"
          memory = "1Gi"
          env    = [...]
          liveness_probe  = {...}
          readiness_probe = {...}
        }
      ]
    }

    ingress = {
      external_enabled = true
      target_port      = 8000
      traffic_weight   = { latest_revision = "true", percentage = 100 }
    }
  }

  # Additional apps can be added here
  # worker = { ... }
  # redis = { ... }
}
```

## Quick Start

### Prerequisites

- Azure CLI authenticated (`az login`)
- Terraform >= 1.7.0
- GitHub PAT for GHCR access (or use managed identity)

### Deployment

```bash
cd deploy/terraform/container-apps

# Authenticate with HCP Terraform
terraform login

# Initialize Terraform
terraform init

# Plan deployment (choose environment)
terraform plan -var-file="dev/terraform.tfvars" -out=tfplan
# or: terraform plan -var-file="prod/terraform.tfvars" -out=tfplan

# Apply
terraform apply tfplan
```

### Via GitHub Actions (La Forge)

The infrastructure pipeline handles deployment via CLI-driven plan/apply:

1. Push changes to `deploy/terraform/**` (or manual dispatch)
2. La Forge calls Data CI + Worf security scans as prerequisites
3. `terraform plan -var-file=<env>/terraform.tfvars` runs automatically
4. `terraform apply` requires manual dispatch with `action=apply`

## Configuration

### Required Variables

| Variable | Description |
|----------|-------------|
| `resource_group_name` | Azure resource group name |
| `app_name` | Container App name |
| `container_image` | Container image (e.g., `ghcr.io/org/app:latest`) |
| `secret_key` | Application secret key (sensitive) |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `location` | `eastus` | Azure region |
| `environment` | `dev` | Environment name |
| `container_port` | `8000` | Container port |
| `container_cpu` | `0.5` | CPU allocation |
| `container_memory` | `1Gi` | Memory allocation |
| `min_replicas` | `1` | Minimum replicas |
| `max_replicas` | `3` | Maximum replicas |
| `revision_mode` | `Single` | `Single` or `Multiple` |
| `log_retention_days` | `30` | Log Analytics retention |

### VNet Integration

Enable VNet integration for private networking:

```hcl
enable_vnet_integration         = true
internal_load_balancer_enabled  = true
vnet_address_space              = ["10.0.0.0/16"]
container_apps_subnet_prefixes  = ["10.0.0.0/23"]
```

### Container Registry Authentication

**Using GHCR with credentials:**
```hcl
container_registry_server   = "ghcr.io"
container_registry_username = "github-username"
container_registry_password = "ghcr-pat-token"
```

**Using managed identity (ACR):**
```hcl
container_registry_server         = "myregistry.azurecr.io"
use_managed_identity_for_registry = true
```

## Environment Files

### dev/terraform.tfvars

```hcl
resource_group_name = "witness-dev-rg"
app_name            = "witness-dev"
environment         = "dev"
container_image     = "ghcr.io/borninthedark/witness:dev"
min_replicas        = 0  # Scale to zero in dev
max_replicas        = 2
log_retention_days  = 7
```

### prod/terraform.tfvars

```hcl
resource_group_name = "witness-prod-rg"
app_name            = "witness"
environment         = "production"
container_image     = "ghcr.io/borninthedark/witness:latest"
min_replicas        = 1
max_replicas        = 5
log_retention_days  = 90
```

## Outputs

| Output | Description |
|--------|-------------|
| `container_app_fqdn` | Application FQDN |
| `container_app_url` | Full HTTPS URL |
| `resource_group_name` | Resource group name |
| `log_analytics_workspace_id` | Log Analytics workspace ID |

## Testing

Run Terraform native tests:

```bash
terraform test
```

Tests validate:
- Required variables
- Container resource limits
- Scaling configuration
- Port ranges
- Environment defaults

## References

- [Azure Container Apps Documentation](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Azure/container-apps/azure Module](https://registry.terraform.io/modules/Azure/container-apps/azure/latest)
- [Container Apps Pricing](https://azure.microsoft.com/en-us/pricing/details/container-apps/)
