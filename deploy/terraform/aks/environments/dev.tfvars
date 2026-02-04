# ================================================================
# AKS Development Environment Configuration
# Official Azure/aks/azurerm Module (v11.0.0)
# ================================================================

# ================================================================
# Core Settings
# ================================================================

environment         = "dev"
resource_group_name = "witness-aks-dev-rg"
aks_cluster_name    = "witness-aks-dev"
location            = "eastus"

# ================================================================
# Kubernetes Configuration
# ================================================================

kubernetes_version        = null  # Use latest stable version
sku_tier                  = "Free"
automatic_upgrade_channel = "stable"

# ================================================================
# Default Node Pool (minimal for dev)
# ================================================================

node_vm_size         = "Standard_B2s"  # Burstable, cost-effective for dev
os_disk_size_gb      = 30
auto_scaling_enabled = true
node_count           = 1
min_node_count       = 1
max_node_count       = 3

# ================================================================
# User Node Pool (disabled for dev)
# ================================================================

enable_user_node_pool = false

# ================================================================
# Networking (public cluster for dev)
# ================================================================

network_plugin         = "azure"
network_policy         = "azure"
service_cidr           = "10.0.0.0/16"
dns_service_ip         = "10.0.0.10"
enable_private_cluster = false

# ================================================================
# Security & Identity
# ================================================================

azure_rbac_enabled       = true
enable_workload_identity = true
enable_azure_policy      = false

# ================================================================
# Addons
# ================================================================

enable_nginx_ingress         = true
enable_monitoring            = true
log_analytics_retention_days = 30

# ================================================================
# Tags
# ================================================================

tags = {
  Environment = "dev"
  Project     = "witness"
  ManagedBy   = "terraform"
  CostCenter  = "development"
}
