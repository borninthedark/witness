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
  sku_name                   = "premium"
  purge_protection_enabled   = true
  soft_delete_retention_days = 7

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
  }

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
  name            = "${var.project}-${var.environment}-aif-key"
  key_vault_id    = azurerm_key_vault.ai_foundry.id
  key_type        = "RSA-HSM"
  key_size        = 2048
  expiration_date = var.key_expiration_date

  key_opts = [
    "wrapKey",
    "unwrapKey",
  ]
}

# ================================================================
# Storage Account (required by AI Foundry hub)
# ================================================================

resource "azurerm_storage_account" "ai_foundry" {
  #checkov:skip=CKV_AZURE_43:Name resolves to compliant value; Checkov cannot evaluate Terraform expressions
  name                            = "${replace(var.project, "-", "")}${var.environment}aifsa"
  location                        = var.location
  resource_group_name             = var.resource_group_name
  account_tier                    = "Standard"
  account_replication_type        = "GRS"
  min_tls_version                 = "TLS1_2"
  public_network_access_enabled   = false
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.ai_foundry.id]
  }

  customer_managed_key {
    key_vault_key_id          = azurerm_key_vault_key.ai_foundry.versionless_id
    user_assigned_identity_id = azurerm_user_assigned_identity.ai_foundry.id
  }

  blob_properties {
    delete_retention_policy {
      days = 7
    }
    container_delete_retention_policy {
      days = 7
    }
  }

  queue_properties {
    logging {
      delete                = true
      read                  = true
      write                 = true
      version               = "1.0"
      retention_policy_days = 7
    }
  }

  sas_policy {
    expiration_period = "30.00:00:00"
    expiration_action = "Log"
  }

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
  name                          = "${var.project}-${var.environment}-content-safety"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "ContentSafety"
  sku_name                      = "S0"
  custom_subdomain_name         = "${var.project}-${var.environment}-content-safety"
  local_auth_enabled            = false
  public_network_access_enabled = false

  identity {
    type         = "SystemAssigned, UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.ai_foundry.id]
  }

  customer_managed_key {
    key_vault_key_id   = azurerm_key_vault_key.ai_foundry.versionless_id
    identity_client_id = azurerm_user_assigned_identity.ai_foundry.client_id
  }

  network_acls {
    default_action = "Deny"
  }

  tags = var.tags
}

# ================================================================
# Private Endpoints (Key Vault + Storage)
# ================================================================

resource "azurerm_private_endpoint" "key_vault" {
  count               = var.subnet_id != null ? 1 : 0
  name                = "${var.project}-${var.environment}-kv-pe"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_id

  private_service_connection {
    name                           = "${var.project}-${var.environment}-kv-psc"
    private_connection_resource_id = azurerm_key_vault.ai_foundry.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = var.vault_dns_zone_ids
  }

  tags = var.tags
}

resource "azurerm_private_endpoint" "storage" {
  count               = var.subnet_id != null ? 1 : 0
  name                = "${var.project}-${var.environment}-sa-pe"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_id

  private_service_connection {
    name                           = "${var.project}-${var.environment}-sa-psc"
    private_connection_resource_id = azurerm_storage_account.ai_foundry.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = var.blob_dns_zone_ids
  }

  tags = var.tags
}
