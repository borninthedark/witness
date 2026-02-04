# ================================================================
# Dev Environment - Container Apps
# ================================================================
# HCP Terraform VCS workflow: workspace "witness-dev"
# Working directory: terraform/dev
# ================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.85.0, < 4.0.0"
    }
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

module "container_apps" {
  source = "../container-apps"

  resource_group_name               = var.resource_group_name
  app_name                          = var.app_name
  container_image                   = var.container_image
  secret_key                        = var.secret_key
  location                          = var.location
  environment                       = var.environment
  tags                              = var.tags
  container_port                    = var.container_port
  container_cpu                     = var.container_cpu
  container_memory                  = var.container_memory
  log_level                         = var.log_level
  database_url                      = var.database_url
  min_replicas                      = var.min_replicas
  max_replicas                      = var.max_replicas
  revision_mode                     = var.revision_mode
  revision_suffix                   = var.revision_suffix
  ingress_external_enabled          = var.ingress_external_enabled
  enable_vnet_integration           = var.enable_vnet_integration
  internal_load_balancer_enabled    = var.internal_load_balancer_enabled
  vnet_address_space                = var.vnet_address_space
  container_apps_subnet_prefixes    = var.container_apps_subnet_prefixes
  container_registry_server         = var.container_registry_server
  container_registry_username       = var.container_registry_username
  container_registry_password       = var.container_registry_password
  use_managed_identity_for_registry = var.use_managed_identity_for_registry
  log_retention_days                = var.log_retention_days
}

# ================================================================
# Outputs
# ================================================================

output "resource_group_name" {
  description = "Resource group name"
  value       = module.container_apps.resource_group_name
}

output "resource_group_id" {
  description = "Resource group ID"
  value       = module.container_apps.resource_group_id
}

output "container_app_environment_id" {
  description = "Container Apps Environment ID"
  value       = module.container_apps.container_app_environment_id
}

output "container_app_environment_name" {
  description = "Container Apps Environment name"
  value       = module.container_apps.container_app_environment_name
}

output "container_app_fqdn" {
  description = "Container App FQDN"
  value       = module.container_apps.container_app_fqdn
}

output "container_app_url" {
  description = "Container App URL"
  value       = module.container_apps.container_app_url
}

output "container_app_ips" {
  description = "Container App IPs"
  value       = module.container_apps.container_app_ips
}

output "container_app_identities" {
  description = "Container App managed identities"
  value       = module.container_apps.container_app_identities
}

output "log_analytics_workspace_name" {
  description = "Log Analytics Workspace name"
  value       = module.container_apps.log_analytics_workspace_name
}

output "vnet_id" {
  description = "VNet ID (if VNet integration enabled)"
  value       = module.container_apps.vnet_id
}

output "subnet_id" {
  description = "Container Apps subnet ID (if VNet integration enabled)"
  value       = module.container_apps.subnet_id
}
