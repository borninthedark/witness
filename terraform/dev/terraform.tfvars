# ================================================================
# Development Environment - Container Apps
# ================================================================
# HCP Terraform workspace: witness-dev
# Sensitive vars set in HCP Terraform workspace variables:
#   - secret_key
#   - container_registry_password (GitHub PAT for ACR Build Task)
# ================================================================

# Core
environment         = "dev"
resource_group_name = "witness-dev-rg"
app_name            = "witness-dev"
location            = "eastus"

# Container
container_image  = "witnessdevacr.azurecr.io/witness:dev"
container_port   = 8000
container_cpu    = "0.25"
container_memory = "0.5Gi"
log_level        = "DEBUG"
database_url     = "sqlite:////app/data/fitness.db"

# Scaling (scale to zero for dev)
min_replicas  = 0
max_replicas  = 2
revision_mode = "Single"

# Ingress
ingress_external_enabled = true

# Networking (no VNet for dev - cost savings)
enable_vnet_integration        = false
internal_load_balancer_enabled = false

# ACR
acr_name             = "witnessdevacr"
acr_sku              = "Basic"
acr_task_context_url = "https://github.com/borninthedark/witness.git#main"
acr_image_tag        = "dev"

# Key Vault
key_vault_name = "witness-dev-kv"

# Monitoring
log_retention_days = 30

# Tags
tags = {
  Environment = "dev"
  Project     = "witness"
  ManagedBy   = "terraform"
  CostCenter  = "development"
}
