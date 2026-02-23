# ================================================================
# Production Environment - Azure AI Platform
# ================================================================
# HCP Terraform VCS workflow: workspace "witness-azure"
# Working directory: terraform/azure/prod
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
    Workspace   = "witness-azure"
  })
}

# ================================================================
# Networking (VNet + Private Endpoints)
# ================================================================

resource "azurerm_virtual_network" "ai" {
  name                = "${var.project}-${var.environment}-ai-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name

  tags = var.tags
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

# ── Private DNS Zones ────────────────────────────────────────────

resource "azurerm_private_dns_zone" "vault" {
  name                = "privatelink.vaultcore.azure.net"
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

resource "azurerm_private_dns_zone" "blob" {
  name                = "privatelink.blob.core.windows.net"
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

resource "azurerm_private_dns_zone_virtual_network_link" "blob" {
  name                  = "blob-link"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.blob.name
  virtual_network_id    = azurerm_virtual_network.ai.id
  tags                  = var.tags
}

# ================================================================
# AI Foundry (Hub + Project + Content Safety)
# ================================================================

module "ai_foundry" {
  source = "../modules/ai-foundry"

  project             = var.project
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
  key_expiration_date = var.key_expiration_date

  subnet_id          = azurerm_subnet.private_endpoints.id
  vault_dns_zone_ids = [azurerm_private_dns_zone.vault.id]
  blob_dns_zone_ids  = [azurerm_private_dns_zone.blob.id]

  tags = var.tags
}

# ================================================================
# AI Search
# ================================================================

module "ai_search" {
  source = "../modules/ai-search"

  project             = var.project
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name

  tags = var.tags
}

# ================================================================
# AI Services (OpenAI, Language, Vision, Document Intelligence)
# ================================================================

module "ai_services" {
  source = "../modules/ai-services"

  project             = var.project
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name

  key_vault_key_id           = module.ai_foundry.key_vault_key_versionless_id
  managed_identity_id        = module.ai_foundry.managed_identity_id
  managed_identity_client_id = module.ai_foundry.managed_identity_client_id

  tags = var.tags
}
