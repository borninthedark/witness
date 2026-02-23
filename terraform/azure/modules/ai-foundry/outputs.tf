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

output "key_vault_key_versionless_id" {
  description = "Key Vault key versionless ID (for CMK in other modules)"
  value       = azurerm_key_vault_key.ai_foundry.versionless_id
}

output "managed_identity_id" {
  description = "User-assigned managed identity ID (for CMK in other modules)"
  value       = azurerm_user_assigned_identity.ai_foundry.id
}

output "managed_identity_client_id" {
  description = "User-assigned managed identity client ID (for CMK in other modules)"
  value       = azurerm_user_assigned_identity.ai_foundry.client_id
}
