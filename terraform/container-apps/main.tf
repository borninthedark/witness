# ================================================================
# Azure Container Apps Infrastructure
# Using Official Azure Terraform Module
# ================================================================
#
# Module: Azure/container-apps/azure (v0.4.0)
# Source: https://github.com/Azure/terraform-azure-container-apps
# AVM Index: https://azure.github.io/Azure-Verified-Modules/indexes/terraform/tf-resource-modules/
#
# Deploys Container Apps using compose-style configuration in Terraform
# ================================================================

# ================================================================
# Data Sources
# ================================================================

data "azurerm_client_config" "current" {}

# ================================================================
# Resource Group
# ================================================================

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

# ================================================================
# Virtual Network (optional - for VNet integration)
# ================================================================

resource "azurerm_virtual_network" "main" {
  count               = var.enable_vnet_integration ? 1 : 0
  name                = "${var.app_name}-vnet"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = var.vnet_address_space
  tags                = var.tags
}

resource "azurerm_subnet" "container_apps" {
  count                = var.enable_vnet_integration ? 1 : 0
  name                 = "container-apps-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main[0].name
  address_prefixes     = var.container_apps_subnet_prefixes

  delegation {
    name = "container-apps-delegation"
    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

# ================================================================
# Container Apps using Official Azure Module (Compose-style)
# ================================================================

module "container_apps" {
  source  = "Azure/container-apps/azure"
  version = "0.4.0"

  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  # Container Apps Environment
  container_app_environment_name = "${var.app_name}-env"
  container_app_environment_tags = var.tags

  # VNet integration (optional)
  container_app_environment_infrastructure_subnet_id       = var.enable_vnet_integration ? azurerm_subnet.container_apps[0].id : null
  container_app_environment_internal_load_balancer_enabled = var.enable_vnet_integration ? var.internal_load_balancer_enabled : null

  # Log Analytics Workspace
  log_analytics_workspace_name              = "${var.app_name}-law"
  log_analytics_workspace_sku               = "PerGB2018"
  log_analytics_workspace_retention_in_days = var.log_retention_days
  log_analytics_workspace_tags              = var.tags

  # ================================================================
  # Container Apps (Compose-style multi-container deployment)
  # ================================================================
  container_apps = {
    # Main application container
    app = {
      name          = var.app_name
      revision_mode = var.revision_mode
      tags          = var.tags

      template = {
        min_replicas    = var.min_replicas
        max_replicas    = var.max_replicas
        revision_suffix = var.revision_suffix

        containers = [
          {
            name   = "witness"
            image  = var.container_image
            cpu    = var.container_cpu
            memory = var.container_memory

            env = [
              { name = "ENVIRONMENT", value = var.environment },
              { name = "LOG_LEVEL", value = var.log_level },
              { name = "DATABASE_URL", value = var.database_url },
              { name = "SECRET_KEY", secret_name = "secret-key" },
              { name = "PYTHONUNBUFFERED", value = "1" },
            ]

            liveness_probe = {
              port             = var.container_port
              transport        = "HTTP"
              path             = "/healthz"
              initial_delay    = 15
              interval_seconds = 30
              timeout          = 5
            }

            readiness_probe = {
              port             = var.container_port
              transport        = "HTTP"
              path             = "/readyz"
              initial_delay    = 10
              interval_seconds = 10
              timeout          = 5
            }
          }
        ]
      }

      ingress = {
        external_enabled           = var.ingress_external_enabled
        target_port                = var.container_port
        transport                  = "auto"
        allow_insecure_connections = false
        traffic_weight = {
          latest_revision = "true"
          percentage      = 100
        }
      }

      identity = {
        type = "SystemAssigned"
      }

      # Container registry configuration
      registry = var.container_registry_server != null ? [
        {
          server               = var.container_registry_server
          identity             = var.use_managed_identity_for_registry ? "system" : null
          username             = var.use_managed_identity_for_registry ? null : var.container_registry_username
          password_secret_name = var.use_managed_identity_for_registry ? null : "registry-password"
        }
      ] : null
    }
  }

  # ================================================================
  # Container App Secrets
  # ================================================================
  container_app_secrets = {
    app = concat(
      [
        {
          name  = "secret-key"
          value = var.secret_key
        }
      ],
      var.container_registry_password != null && !var.use_managed_identity_for_registry ? [
        {
          name  = "registry-password"
          value = var.container_registry_password
        }
      ] : []
    )
  }

  depends_on = [azurerm_resource_group.main]
}
