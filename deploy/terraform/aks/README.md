# AKS Terraform Deployment

This directory contains Terraform configuration for deploying an Azure Kubernetes Service (AKS) cluster with supporting infrastructure.

## Features

- **AKS Cluster**: Managed Kubernetes cluster with auto-scaling
- **Log Analytics**: Container Insights for monitoring
- **NGINX Ingress**: Managed web app routing addon
- **Azure RBAC**: Azure Active Directory integration with RBAC
- **Auto-upgrade**: Stable channel automatic upgrades

## Structure

```
aks/
├── backend.tf          # State backend configuration
├── main.tf             # Main resources (RG, Log Analytics, AKS)
├── variables.tf        # Input variable definitions
├── outputs.tf          # Output values
├── terraform.tfvars    # Production variable values
├── versions.tf         # Provider version constraints
└── README.md          # This file
```

## Prerequisites

- [Terraform](https://www.terraform.io/downloads.html) >= 1.5.0
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
- Azure subscription with appropriate permissions

## Authentication

Authenticate with Azure using one of these methods:

### Azure CLI (Local Development)
```bash
az login
```

### Service Principal (CI/CD)
```bash
export ARM_CLIENT_ID="<client-id>"
export ARM_CLIENT_SECRET="<client-secret>"
export ARM_SUBSCRIPTION_ID="<subscription-id>"
export ARM_TENANT_ID="<tenant-id>"
```

### Managed Identity or OIDC (GitHub Actions)
GitHub Actions workflow handles this automatically.

## Usage

### Initialize Terraform
```bash
cd deploy/terraform/aks
terraform init
```

### Plan Deployment
```bash
terraform plan
```

### Apply Configuration
```bash
terraform apply
```

### Destroy Infrastructure
```bash
terraform destroy
```

## Variables

Key variables (see `variables.tf` for complete list):

| Variable | Description | Default |
|----------|-------------|---------|
| `resource_group_name` | Resource group name | Required |
| `aks_cluster_name` | AKS cluster name | Required |
| `location` | Azure region | `eastus` |
| `kubernetes_version` | Kubernetes version | `1.29.0` |
| `node_vm_size` | Node VM size | `Standard_D2s_v3` |
| `node_count` | Initial node count | `2` |
| `min_node_count` | Min nodes for autoscaling | `1` |
| `max_node_count` | Max nodes for autoscaling | `5` |
| `enable_nginx_ingress` | Enable NGINX ingress | `true` |

## Outputs

After successful deployment:

```bash
# Get cluster credentials
terraform output -raw get_credentials_command | bash

# View outputs
terraform output
```

## State Management

### Local State (Default)
State is stored locally in `terraform.tfstate`. **Do not commit this file.**

### Remote State (Recommended for Production)
Uncomment and configure `backend.tf` to use Azure Storage:

```bash
# Create storage account for state
az group create --name terraform-state-rg --location eastus
az storage account create --name tfstatexxxxx --resource-group terraform-state-rg --location eastus --sku Standard_LRS
az storage container create --name tfstate --account-name tfstatexxxxx

# Update backend.tf with your values
# Then run:
terraform init -migrate-state
```

## CI/CD Integration

See `/.github/workflows/data.yml` for GitHub Actions integration.

## Maintenance

### Upgrade Kubernetes Version
1. Check available versions: `az aks get-versions --location eastus`
2. Update `kubernetes_version` in `terraform.tfvars`
3. Run `terraform plan` and `terraform apply`

### Scale Nodes
Update `min_node_count`, `max_node_count`, or `node_count` in `terraform.tfvars`.

## Troubleshooting

### Authentication Issues
```bash
# Verify Azure login
az account show

# Set subscription
az account set --subscription "<subscription-id>"
```

### State Lock Issues
```bash
# If state is locked, force unlock (use carefully)
terraform force-unlock <lock-id>
```

## Security Notes

- Never commit `terraform.tfstate` or `terraform.tfvars` with secrets
- Use remote state with encryption enabled
- Enable Azure RBAC on the cluster
- Review and apply network policies
- Regularly update Kubernetes version
