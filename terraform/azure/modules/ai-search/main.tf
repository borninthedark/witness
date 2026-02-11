# ================================================================
# AI Search Module - Azure Cognitive Search
# ================================================================

resource "azurerm_search_service" "main" {
  name                = "${var.project}-${var.environment}-search"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "basic"
  semantic_search_sku = "standard"

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}
