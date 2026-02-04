# ================================================================
# AKS Production Environment Configuration
# Official Azure/aks/azurerm Module (v11.0.0)
# ================================================================

# ================================================================
# Core Settings
# ================================================================

environment         = "production"
resource_group_name = "witness-aks-prod-rg"
aks_cluster_name    = "witness-aks-prod"
location            = "eastus"

# ================================================================
# Kubernetes Configuration
# ================================================================

kubernetes_version        = null  # Use latest stable version
sku_tier                  = "Standard"  # SLA-backed for production
automatic_upgrade_channel = "stable"

# ================================================================
# Default Node Pool (production-ready)
# ================================================================

node_vm_size         = "Standard_D2s_v3"
os_disk_size_gb      = 50
auto_scaling_enabled = true
node_count           = 2
min_node_count       = 2
max_node_count       = 5

# ================================================================
# User Node Pool (enabled for production workloads)
# ================================================================

enable_user_node_pool     = true
user_node_pool_vm_size    = "Standard_D4s_v3"
user_node_pool_node_count = 1
user_node_pool_min_count  = 1
user_node_pool_max_count  = 5
user_node_pool_taints     = []

# ================================================================
# Networking (private cluster for production)
# ================================================================

network_plugin                      = "azure"
network_policy                      = "azure"
service_cidr                        = "10.0.0.0/16"
dns_service_ip                      = "10.0.0.10"
enable_private_cluster              = true
private_cluster_public_fqdn_enabled = true
vnet_address_space                  = ["10.1.0.0/16"]
aks_subnet_address_prefixes         = ["10.1.0.0/22"]

# ================================================================
# Security & Identity
# ================================================================

azure_rbac_enabled       = true
enable_workload_identity = true
enable_azure_policy      = true  # Enforce policies in production

# ================================================================
# Addons
# ================================================================

enable_nginx_ingress         = true
enable_monitoring            = true
log_analytics_retention_days = 90  # Longer retention for production

# ================================================================
# Tags
# ================================================================

tags = {
  Environment  = "production"
  Project      = "witness"
  ManagedBy    = "terraform"
  CostCenter   = "production"
  Criticality  = "high"
  DataClass    = "internal"
  BackupPolicy = "daily"
}
