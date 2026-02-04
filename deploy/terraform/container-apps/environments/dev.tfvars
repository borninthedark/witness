# ================================================================
# Development Environment - Container Apps
# ================================================================

# Core
environment         = "dev"
resource_group_name = "witness-dev-rg"
app_name            = "witness-dev"
location            = "eastus"

# Container
container_image  = "ghcr.io/borninthedark/witness:dev"
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

# Registry (using GHCR with token)
container_registry_server         = "ghcr.io"
use_managed_identity_for_registry = false

# Monitoring
log_retention_days = 30

# Tags
tags = {
  Environment = "dev"
  Project     = "witness"
  ManagedBy   = "terraform"
  CostCenter  = "development"
}
