# ================================================================
# Production Environment - Container Apps
# ================================================================
# HCP Terraform workspace: witness-prod
# Sensitive vars set in HCP Terraform workspace variables:
#   - secret_key
#   - container_registry_password (GitHub PAT for ACR Build Task)
# ================================================================

# Core
environment         = "production"
resource_group_name = "witness-prod-rg"
app_name            = "witness-prod"
location            = "eastus"

# Container
container_image  = "witnessprodacr.azurecr.io/witness:latest"
container_port   = 8000
container_cpu    = "0.5"
container_memory = "1Gi"
log_level        = "INFO"
database_url     = "sqlite:////app/data/fitness.db"

# Scaling (always-on for production)
min_replicas  = 1
max_replicas  = 5
revision_mode = "Multiple" # Blue-green deployments

# Ingress
ingress_external_enabled = true

# Networking (VNet for production security)
enable_vnet_integration        = true
internal_load_balancer_enabled = false
vnet_address_space             = ["10.0.0.0/16"]
container_apps_subnet_prefixes = ["10.0.0.0/23"]

# ACR
acr_name             = "witnessprodacr"
acr_sku              = "Standard"
acr_task_context_url = "https://github.com/borninthedark/witness.git#main"
acr_image_tag        = "latest"

# Key Vault
key_vault_name                       = "witness-prod-kv"
key_vault_soft_delete_retention_days = 90
key_vault_purge_protection_enabled   = true

# Monitoring (longer retention for production)
log_retention_days = 90

# Tags
tags = {
  Environment = "production"
  Project     = "witness"
  ManagedBy   = "terraform"
  CostCenter  = "production"
  Criticality = "high"
}
