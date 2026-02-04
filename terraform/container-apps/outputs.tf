# ================================================================
# Container Apps Outputs
# ================================================================

output "resource_group_name" {
  description = "Resource group name"
  value       = azurerm_resource_group.main.name
}

output "resource_group_id" {
  description = "Resource group ID"
  value       = azurerm_resource_group.main.id
}

output "container_app_environment_id" {
  description = "Container Apps Environment ID"
  value       = module.container_apps.container_app_environment_id
}

output "container_app_environment_name" {
  description = "Container Apps Environment name"
  value       = "${var.app_name}-env"
}

output "container_app_fqdn" {
  description = "Container App FQDN"
  value       = try(module.container_apps.container_app_fqdn["app"], null)
}

output "container_app_url" {
  description = "Container App URL"
  value       = try("https://${module.container_apps.container_app_fqdn["app"]}", null)
}

output "container_app_ips" {
  description = "Container App IPs"
  value       = try(module.container_apps.container_app_ips["app"], null)
}

output "container_app_identities" {
  description = "Container App managed identities"
  value       = try(module.container_apps.container_app_identities["app"], null)
}

output "log_analytics_workspace_name" {
  description = "Log Analytics Workspace name"
  value       = "${var.app_name}-law"
}

# VNet outputs (if enabled)
output "vnet_id" {
  description = "VNet ID (if VNet integration enabled)"
  value       = var.enable_vnet_integration ? azurerm_virtual_network.main[0].id : null
}

output "subnet_id" {
  description = "Container Apps subnet ID (if VNet integration enabled)"
  value       = var.enable_vnet_integration ? azurerm_subnet.container_apps[0].id : null
}
