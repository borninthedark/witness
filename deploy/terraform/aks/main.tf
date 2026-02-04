# ================================================================
# AKS Terraform Configuration using Official Azure Module
# ================================================================
#
# Module: Azure/aks/azurerm (v11.0.0)
# Source: https://github.com/Azure/terraform-azurerm-aks
# Registry: https://registry.terraform.io/modules/Azure/aks/azurerm
#
# This module provides a production-ready AKS cluster deployment
# with support for autoscaling, monitoring, and security features.
# ================================================================

# ================================================================
# Data Sources
# ================================================================

data "azurerm_client_config" "current" {}

data "azurerm_subscription" "current" {}

# ================================================================
# Resource Group
# ================================================================

resource "azurerm_resource_group" "aks" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

# ================================================================
# Virtual Network (optional - for private clusters)
# ================================================================

resource "azurerm_virtual_network" "aks" {
  count               = var.enable_private_cluster ? 1 : 0
  name                = "${var.aks_cluster_name}-vnet"
  location            = azurerm_resource_group.aks.location
  resource_group_name = azurerm_resource_group.aks.name
  address_space       = var.vnet_address_space
  tags                = var.tags
}

resource "azurerm_subnet" "aks_nodes" {
  count                = var.enable_private_cluster ? 1 : 0
  name                 = "aks-nodes-subnet"
  resource_group_name  = azurerm_resource_group.aks.name
  virtual_network_name = azurerm_virtual_network.aks[0].name
  address_prefixes     = var.aks_subnet_address_prefixes
}

# ================================================================
# AKS Cluster using Official Azure Module
# ================================================================

module "aks" {
  source  = "Azure/aks/azurerm"
  version = "11.0.0"

  # Required parameters
  resource_group_name = azurerm_resource_group.aks.name
  location            = azurerm_resource_group.aks.location
  prefix              = var.aks_cluster_name

  # Kubernetes version
  kubernetes_version   = var.kubernetes_version
  orchestrator_version = var.kubernetes_version

  # SKU tier (Free, Standard, or Premium)
  sku_tier = var.sku_tier

  # Default node pool configuration
  agents_size      = var.node_vm_size
  agents_count     = var.auto_scaling_enabled ? null : var.node_count
  agents_min_count = var.auto_scaling_enabled ? var.min_node_count : null
  agents_max_count = var.auto_scaling_enabled ? var.max_node_count : null
  agents_pool_name = "systempool"
  agents_type      = "VirtualMachineScaleSets"
  os_disk_size_gb  = var.os_disk_size_gb

  # Enable autoscaling
  auto_scaling_enabled = var.auto_scaling_enabled

  # Network configuration
  network_plugin      = var.network_plugin
  network_policy      = var.network_policy
  net_profile_service_cidr   = var.service_cidr
  net_profile_dns_service_ip = var.dns_service_ip
  load_balancer_sku   = "standard"

  # VNet integration (if private cluster)
  vnet_subnet = var.enable_private_cluster ? {
    id = azurerm_subnet.aks_nodes[0].id
  } : null

  # Private cluster settings
  private_cluster_enabled             = var.enable_private_cluster
  private_cluster_public_fqdn_enabled = var.enable_private_cluster ? var.private_cluster_public_fqdn_enabled : false

  # Azure AD RBAC integration
  role_based_access_control_enabled = true
  rbac_aad_azure_rbac_enabled       = var.azure_rbac_enabled
  rbac_aad_tenant_id                = data.azurerm_client_config.current.tenant_id

  # Workload identity and OIDC
  workload_identity_enabled = var.enable_workload_identity
  oidc_issuer_enabled       = var.enable_workload_identity

  # Azure Policy addon
  azure_policy_enabled = var.enable_azure_policy

  # Web App Routing (managed NGINX Ingress)
  web_app_routing = var.enable_nginx_ingress ? {
    dns_zone_ids = []
  } : null

  # Monitoring (Log Analytics and Container Insights)
  log_analytics_workspace_enabled = var.enable_monitoring
  log_retention_in_days           = var.log_analytics_retention_days
  oms_agent_enabled               = var.enable_monitoring

  # Auto-upgrade settings
  automatic_channel_upgrade = var.automatic_upgrade_channel

  # Additional node pools
  node_pools = var.enable_user_node_pool ? {
    userpool = {
      name                 = "userpool"
      vm_size              = var.user_node_pool_vm_size
      node_count           = var.user_node_pool_node_count
      auto_scaling_enabled = true
      min_count            = var.user_node_pool_min_count
      max_count            = var.user_node_pool_max_count
      os_disk_size_gb      = var.os_disk_size_gb
      mode                 = "User"
      os_type              = "Linux"
      node_labels = {
        "workload" = "user"
      }
      node_taints = var.user_node_pool_taints
      vnet_subnet = var.enable_private_cluster ? {
        id = azurerm_subnet.aks_nodes[0].id
      } : null
    }
  } : {}

  # Tags
  tags = var.tags

  depends_on = [azurerm_resource_group.aks]
}
