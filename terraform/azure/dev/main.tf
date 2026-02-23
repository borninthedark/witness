# ================================================================
# Dev Environment - Azure AI Platform
# ================================================================
# HCP Terraform VCS workflow: workspace "witness-azure-dev"
# Working directory: terraform/azure/dev
# ================================================================
# Minimal config: ai-services only (no ai-foundry hub, no ai-search).
# KV + identity created locally for CMK compliance.
# ================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.0.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# ================================================================
# Resource Group
# ================================================================

resource "azurerm_resource_group" "main" {
  name     = "${var.project}-${var.environment}-ai"
  location = var.location

  tags = merge(var.tags, {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Workspace   = "witness-azure-dev"
  })
}

# ================================================================
# Key Vault + Identity (CMK for cognitive services)
# ================================================================

data "azurerm_client_config" "current" {}

resource "azurerm_user_assigned_identity" "ai" {
  name                = "${var.project}-${var.environment}-ai-identity"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_key_vault" "ai" {
  name                       = "${var.project}-${var.environment}-ai-kv"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "premium"
  purge_protection_enabled   = true
  soft_delete_retention_days = 7

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
  }

  access_policy {
    tenant_id       = data.azurerm_client_config.current.tenant_id
    object_id       = data.azurerm_client_config.current.object_id
    key_permissions = ["Create", "Get", "Delete", "Purge", "GetRotationPolicy", "WrapKey", "UnwrapKey"]
  }

  access_policy {
    tenant_id       = data.azurerm_client_config.current.tenant_id
    object_id       = azurerm_user_assigned_identity.ai.principal_id
    key_permissions = ["Get", "WrapKey", "UnwrapKey"]
  }

  tags = var.tags
}

resource "azurerm_key_vault_key" "ai" {
  name            = "${var.project}-${var.environment}-ai-key"
  key_vault_id    = azurerm_key_vault.ai.id
  key_type        = "RSA-HSM"
  key_size        = 2048
  expiration_date = var.key_expiration_date

  key_opts = ["wrapKey", "unwrapKey"]
}

# ================================================================
# Networking (minimal VNet for KV private endpoint)
# ================================================================

resource "azurerm_virtual_network" "ai" {
  name                = "${var.project}-${var.environment}-ai-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

resource "azurerm_subnet" "private_endpoints" {
  name                 = "private-endpoints"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.ai.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_network_security_group" "private_endpoints" {
  name                = "${var.project}-${var.environment}-pe-nsg"
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

resource "azurerm_subnet_network_security_group_association" "private_endpoints" {
  subnet_id                 = azurerm_subnet.private_endpoints.id
  network_security_group_id = azurerm_network_security_group.private_endpoints.id
}

resource "azurerm_private_dns_zone" "vault" {
  name                = "privatelink.vaultcore.azure.net"
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "vault" {
  name                  = "vault-link"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.vault.name
  virtual_network_id    = azurerm_virtual_network.ai.id
  tags                  = var.tags
}

resource "azurerm_private_endpoint" "key_vault" {
  name                = "${var.project}-${var.environment}-kv-pe"
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.private_endpoints.id

  private_service_connection {
    name                           = "${var.project}-${var.environment}-kv-psc"
    private_connection_resource_id = azurerm_key_vault.ai.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.vault.id]
  }

  tags = var.tags
}

# ================================================================
# AI Services (OpenAI + Language, Vision, Doc Intelligence)
# ================================================================

module "ai_services" {
  source = "../modules/ai-services"

  project             = var.project
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name

  key_vault_key_id           = azurerm_key_vault_key.ai.versionless_id
  managed_identity_id        = azurerm_user_assigned_identity.ai.id
  managed_identity_client_id = azurerm_user_assigned_identity.ai.client_id

  language_sku              = "S0"
  vision_sku                = "S0"
  document_intelligence_sku = "S0"

  tags = var.tags
}
