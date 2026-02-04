# ================================================================
# Production Environment - Container Apps
# ================================================================

# Core
environment         = "production"
resource_group_name = "witness-prod-rg"
app_name            = "witness-prod"
location            = "eastus"

# Container
container_image  = "ghcr.io/borninthedark/witness:latest"
container_port   = 8000
container_cpu    = "0.5"
container_memory = "1Gi"
log_level        = "INFO"
database_url     = "sqlite:////app/data/fitness.db"

# Scaling (always-on for production)
min_replicas  = 1
max_replicas  = 5
revision_mode = "Multiple"  # Blue-green deployments

# Ingress
ingress_external_enabled = true

# Networking (VNet for production security)
enable_vnet_integration        = true
internal_load_balancer_enabled = false
vnet_address_space             = ["10.0.0.0/16"]
container_apps_subnet_prefixes = ["10.0.0.0/23"]

# Registry (using GHCR with token)
container_registry_server         = "ghcr.io"
use_managed_identity_for_registry = false

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
