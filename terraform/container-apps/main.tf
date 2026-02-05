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
# Azure Container Registry (AVM)
# ================================================================

module "acr" {
  source  = "Azure/avm-res-containerregistry-registry/azurerm"
  version = "0.5.1"

  name                = var.acr_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = var.acr_sku
  admin_enabled       = var.acr_admin_enabled
  enable_telemetry    = false
  tags                = var.tags

  # Basic/Standard SKUs don't support zone redundancy
  zone_redundancy_enabled = var.acr_sku == "Premium" ? true : false

  # Retention policy only supported on Premium SKU
  retention_policy_in_days = var.acr_sku == "Premium" ? 7 : null

  # AcrPull for Container App managed identity
  role_assignments = {
    acr_pull = {
      role_definition_id_or_name       = "AcrPull"
      principal_id                     = module.container_apps.container_app_identities["app"].principal_id
      skip_service_principal_aad_check = true
    }
  }
}

# ================================================================
# ACR Build Task (Terraform-managed, GHA-triggered)
# ================================================================

resource "azurerm_container_registry_task" "build" {
  name                  = "${var.app_name}-build"
  container_registry_id = module.acr.resource_id

  platform {
    os = "Linux"
  }

  docker_step {
    dockerfile_path      = "Containerfile"
    context_path         = var.acr_task_context_url
    context_access_token = var.container_registry_password
    image_names          = ["witness:{{.Run.ID}}", "witness:${var.acr_image_tag}"]
  }
}

# ================================================================
# Azure Key Vault (AVM)
# ================================================================

module "key_vault" {
  source  = "Azure/avm-res-keyvault-vault/azurerm"
  version = "0.10.2"

  name                       = var.key_vault_name
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = var.key_vault_sku
  soft_delete_retention_days = var.key_vault_soft_delete_retention_days
  purge_protection_enabled   = var.key_vault_purge_protection_enabled
  enable_telemetry           = false
  tags                       = var.tags

  # Allow Terraform SP to manage secrets
  network_acls = null

  role_assignments = {
    deployer = {
      role_definition_id_or_name = "Key Vault Administrator"
      principal_id               = data.azurerm_client_config.current.object_id
    }
    container_app_secrets = {
      role_definition_id_or_name       = "Key Vault Secrets User"
      principal_id                     = module.container_apps.container_app_identities["app"].principal_id
      skip_service_principal_aad_check = true
    }
  }

  secrets = {
    secret_key = {
      name = "secret-key"
    }
  }

  secrets_value = {
    secret_key = var.secret_key
  }

  wait_for_rbac_before_secret_operations = {
    create = "60s"
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

      # ACR with managed identity
      registry = [
        {
          server   = module.acr.resource.login_server
          identity = "system"
        }
      ]
    }
  }

  # ================================================================
  # Container App Secrets
  # ================================================================
  container_app_secrets = {
    app = [
      {
        name  = "secret-key"
        value = var.secret_key
      }
    ]
  }

  depends_on = [azurerm_resource_group.main]
}
