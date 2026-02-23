# ================================================================
# AI Search Module - Azure Cognitive Search
# ================================================================

resource "azurerm_search_service" "main" {
  name                          = "${var.project}-${var.environment}-search"
  resource_group_name           = var.resource_group_name
  location                      = var.location
  sku                           = "basic"
  semantic_search_sku           = "standard"
  replica_count                 = var.replica_count
  local_authentication_enabled  = false
  public_network_access_enabled = false

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}
