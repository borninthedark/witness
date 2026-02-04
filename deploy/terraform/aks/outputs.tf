# ================================================================
# AKS Terraform Outputs
# Official Azure/aks/azurerm Module (v11.0.0)
# ================================================================

output "resource_group_name" {
  description = "Resource group name"
  value       = azurerm_resource_group.aks.name
}

output "resource_group_id" {
  description = "Resource group ID"
  value       = azurerm_resource_group.aks.id
}

output "aks_cluster_name" {
  description = "AKS cluster name"
  value       = module.aks.aks_name
}

output "aks_cluster_id" {
  description = "AKS cluster resource ID"
  value       = module.aks.aks_id
}

output "aks_cluster_fqdn" {
  description = "AKS cluster FQDN"
  value       = module.aks.cluster_fqdn
}

output "aks_cluster_private_fqdn" {
  description = "AKS cluster private FQDN (if private cluster)"
  value       = module.aks.cluster_private_fqdn
}

output "aks_cluster_portal_fqdn" {
  description = "AKS cluster portal FQDN"
  value       = module.aks.cluster_portal_fqdn
}

output "node_resource_group" {
  description = "Node resource group"
  value       = module.aks.node_resource_group
}

output "node_resource_group_id" {
  description = "Node resource group ID"
  value       = module.aks.node_resource_group_id
}

output "kubelet_identity" {
  description = "Kubelet managed identity"
  value       = module.aks.kubelet_identity
}

output "cluster_identity" {
  description = "Cluster managed identity"
  value       = module.aks.cluster_identity
}

output "oidc_issuer_url" {
  description = "OIDC issuer URL for workload identity"
  value       = module.aks.oidc_issuer_url
}

output "log_analytics_workspace_id" {
  description = "Log Analytics Workspace ID"
  value       = module.aks.azurerm_log_analytics_workspace_id
}

output "log_analytics_workspace_name" {
  description = "Log Analytics Workspace name"
  value       = module.aks.azurerm_log_analytics_workspace_name
}

output "get_credentials_command" {
  description = "Command to get AKS credentials"
  value       = "az aks get-credentials --resource-group ${azurerm_resource_group.aks.name} --name ${module.aks.aks_name}"
}

output "kube_config_raw" {
  description = "Kubernetes configuration (raw)"
  value       = module.aks.kube_config_raw
  sensitive   = true
}

output "kube_admin_config_raw" {
  description = "Kubernetes admin configuration (raw)"
  value       = module.aks.kube_admin_config_raw
  sensitive   = true
}

output "host" {
  description = "Kubernetes cluster server host"
  value       = module.aks.host
  sensitive   = true
}

output "client_certificate" {
  description = "Client certificate for authentication"
  value       = module.aks.client_certificate
  sensitive   = true
}

output "client_key" {
  description = "Client key for authentication"
  value       = module.aks.client_key
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "Cluster CA certificate"
  value       = module.aks.cluster_ca_certificate
  sensitive   = true
}

# VNet outputs (if private cluster)
output "vnet_id" {
  description = "VNet ID (if private cluster)"
  value       = var.enable_private_cluster ? azurerm_virtual_network.aks[0].id : null
}

output "vnet_name" {
  description = "VNet name (if private cluster)"
  value       = var.enable_private_cluster ? azurerm_virtual_network.aks[0].name : null
}

output "subnet_id" {
  description = "AKS subnet ID (if private cluster)"
  value       = var.enable_private_cluster ? azurerm_subnet.aks_nodes[0].id : null
}

# Feature status outputs
output "azure_policy_enabled" {
  description = "Whether Azure Policy is enabled"
  value       = module.aks.azure_policy_enabled
}

output "oms_agent_enabled" {
  description = "Whether OMS Agent (Container Insights) is enabled"
  value       = module.aks.oms_agent_enabled
}

output "network_profile" {
  description = "AKS network profile configuration"
  value       = module.aks.network_profile
}

output "web_app_routing_identity" {
  description = "Web App Routing managed identity"
  value       = module.aks.web_app_routing_identity
}
