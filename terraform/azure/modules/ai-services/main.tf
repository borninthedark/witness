# ================================================================
# AI Services Module - OpenAI, Language, Vision, Document Intelligence
# ================================================================

# ================================================================
# Azure OpenAI (GPT-4o + text-embedding-3-large)
# ================================================================

resource "azurerm_cognitive_account" "openai" {
  name                               = "${var.project}-${var.environment}-openai"
  location                           = var.location
  resource_group_name                = var.resource_group_name
  kind                               = "OpenAI"
  sku_name                           = "S0"
  custom_subdomain_name              = "${var.project}-${var.environment}-openai"
  local_auth_enabled                 = false
  public_network_access_enabled      = false
  outbound_network_access_restricted = true

  identity {
    type         = "SystemAssigned, UserAssigned"
    identity_ids = [var.managed_identity_id]
  }

  customer_managed_key {
    key_vault_key_id   = var.key_vault_key_id
    identity_client_id = var.managed_identity_client_id
  }

  network_acls {
    default_action = "Deny"
    ip_rules       = var.allowed_ip_ranges
  }

  tags = var.tags
}

resource "azurerm_cognitive_deployment" "gpt4o" {
  name                 = "gpt-4o"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "gpt-4o"
    version = "2024-11-20"
  }

  sku {
    name     = "Standard"
    capacity = 10
  }
}

resource "azurerm_cognitive_deployment" "embedding" {
  name                 = "text-embedding-3-large"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-large"
    version = "1"
  }

  sku {
    name     = "Standard"
    capacity = 10
  }
}

# ================================================================
# Azure AI Language (Text Analytics)
# ================================================================

resource "azurerm_cognitive_account" "language" {
  name                          = "${var.project}-${var.environment}-language"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "TextAnalytics"
  sku_name                      = var.language_sku
  custom_subdomain_name         = "${var.project}-${var.environment}-language"
  local_auth_enabled            = false
  public_network_access_enabled = false

  identity {
    type         = "SystemAssigned, UserAssigned"
    identity_ids = [var.managed_identity_id]
  }

  customer_managed_key {
    key_vault_key_id   = var.key_vault_key_id
    identity_client_id = var.managed_identity_client_id
  }

  network_acls {
    default_action = "Deny"
    ip_rules       = var.allowed_ip_ranges
  }

  tags = var.tags
}

# ================================================================
# Azure AI Vision (Computer Vision)
# ================================================================

resource "azurerm_cognitive_account" "vision" {
  name                          = "${var.project}-${var.environment}-vision"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "ComputerVision"
  sku_name                      = var.vision_sku
  custom_subdomain_name         = "${var.project}-${var.environment}-vision"
  local_auth_enabled            = false
  public_network_access_enabled = false

  identity {
    type         = "SystemAssigned, UserAssigned"
    identity_ids = [var.managed_identity_id]
  }

  customer_managed_key {
    key_vault_key_id   = var.key_vault_key_id
    identity_client_id = var.managed_identity_client_id
  }

  network_acls {
    default_action = "Deny"
    ip_rules       = var.allowed_ip_ranges
  }

  tags = var.tags
}

# ================================================================
# Document Intelligence (Form Recognizer)
# ================================================================

resource "azurerm_cognitive_account" "document_intelligence" {
  name                          = "${var.project}-${var.environment}-docint"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "FormRecognizer"
  sku_name                      = var.document_intelligence_sku
  custom_subdomain_name         = "${var.project}-${var.environment}-docint"
  local_auth_enabled            = false
  public_network_access_enabled = false

  identity {
    type         = "SystemAssigned, UserAssigned"
    identity_ids = [var.managed_identity_id]
  }

  customer_managed_key {
    key_vault_key_id   = var.key_vault_key_id
    identity_client_id = var.managed_identity_client_id
  }

  network_acls {
    default_action = "Deny"
    ip_rules       = var.allowed_ip_ranges
  }

  tags = var.tags
}
