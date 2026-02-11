# ================================================================
# AI Foundry Module Outputs
# ================================================================

output "hub_id" {
  description = "AI Foundry hub ID"
  value       = azurerm_ai_foundry.hub.id
}

output "project_id" {
  description = "AI Foundry project ID"
  value       = azurerm_ai_foundry_project.rag.id
}

output "content_safety_endpoint" {
  description = "Content Safety endpoint"
  value       = azurerm_cognitive_account.content_safety.endpoint
}
