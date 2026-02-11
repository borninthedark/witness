# ================================================================
# AI Search Module Outputs
# ================================================================

output "search_service_id" {
  description = "Azure AI Search service ID"
  value       = azurerm_search_service.main.id
}

output "endpoint" {
  description = "Azure AI Search endpoint URL"
  value       = "https://${azurerm_search_service.main.name}.search.windows.net"
}

output "primary_key" {
  description = "Azure AI Search primary admin key"
  value       = azurerm_search_service.main.primary_key
  sensitive   = true
}
