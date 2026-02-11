# ================================================================
# AI Foundry Module - Hub + Project + Content Safety
# ================================================================

# ================================================================
# Managed Identity
# ================================================================

resource "azurerm_user_assigned_identity" "ai_foundry" {
  name                = "${var.project}-${var.environment}-ai-foundry"
  resource_group_name = var.resource_group_name
  location            = var.location

  tags = var.tags
}

# ================================================================
# Key Vault (for AI Foundry hub encryption)
# ================================================================

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "ai_foundry" {
  name                       = "${var.project}-${var.environment}-aif-kv"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  purge_protection_enabled   = true
  soft_delete_retention_days = 7

  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id

    key_permissions = [
      "Create",
      "Get",
      "Delete",
      "Purge",
      "GetRotationPolicy",
      "WrapKey",
      "UnwrapKey",
    ]
  }

  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = azurerm_user_assigned_identity.ai_foundry.principal_id

    key_permissions = [
      "Get",
      "WrapKey",
      "UnwrapKey",
    ]
  }

  tags = var.tags
}

resource "azurerm_key_vault_key" "ai_foundry" {
  name         = "${var.project}-${var.environment}-aif-key"
  key_vault_id = azurerm_key_vault.ai_foundry.id
  key_type     = "RSA"
  key_size     = 2048

  key_opts = [
    "wrapKey",
    "unwrapKey",
  ]
}

# ================================================================
# Storage Account (required by AI Foundry hub)
# ================================================================

resource "azurerm_storage_account" "ai_foundry" {
  name                     = "${replace(var.project, "-", "")}${var.environment}aifsa"
  location                 = var.location
  resource_group_name      = var.resource_group_name
  account_tier             = "Standard"
  account_replication_type = "LRS"

  tags = var.tags
}

# ================================================================
# AI Foundry Hub
# ================================================================

resource "azurerm_ai_foundry" "hub" {
  name                = "${var.project}-${var.environment}-ai-hub"
  location            = var.location
  resource_group_name = var.resource_group_name
  storage_account_id  = azurerm_storage_account.ai_foundry.id
  key_vault_id        = azurerm_key_vault.ai_foundry.id

  primary_user_assigned_identity = azurerm_user_assigned_identity.ai_foundry.id

  identity {
    type = "UserAssigned"
    identity_ids = [
      azurerm_user_assigned_identity.ai_foundry.id,
    ]
  }

  encryption {
    key_id                    = azurerm_key_vault_key.ai_foundry.versionless_id
    key_vault_id              = azurerm_key_vault.ai_foundry.id
    user_assigned_identity_id = azurerm_user_assigned_identity.ai_foundry.id
  }

  tags = var.tags
}

# ================================================================
# AI Foundry Project (RAG workspace)
# ================================================================

resource "azurerm_ai_foundry_project" "rag" {
  name               = "${var.project}-${var.environment}-rag"
  location           = azurerm_ai_foundry.hub.location
  ai_services_hub_id = azurerm_ai_foundry.hub.id

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# ================================================================
# Content Safety (Cognitive Account)
# ================================================================

resource "azurerm_cognitive_account" "content_safety" {
  name                = "${var.project}-${var.environment}-content-safety"
  location            = var.location
  resource_group_name = var.resource_group_name
  kind                = "ContentSafety"
  sku_name            = "S0"

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}
