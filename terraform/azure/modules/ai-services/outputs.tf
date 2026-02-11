# ================================================================
# AI Services Module Outputs
# ================================================================

# ================================================================
# Azure OpenAI
# ================================================================

output "openai_endpoint" {
  description = "Azure OpenAI endpoint"
  value       = azurerm_cognitive_account.openai.endpoint
}

output "openai_id" {
  description = "Azure OpenAI account ID"
  value       = azurerm_cognitive_account.openai.id
}

output "openai_primary_key" {
  description = "Azure OpenAI primary access key"
  value       = azurerm_cognitive_account.openai.primary_access_key
  sensitive   = true
}

output "gpt4o_deployment_name" {
  description = "GPT-4o deployment name"
  value       = azurerm_cognitive_deployment.gpt4o.name
}

output "embedding_deployment_name" {
  description = "text-embedding-3-large deployment name"
  value       = azurerm_cognitive_deployment.embedding.name
}

# ================================================================
# Azure AI Language
# ================================================================

output "language_endpoint" {
  description = "Azure AI Language endpoint"
  value       = azurerm_cognitive_account.language.endpoint
}

output "language_id" {
  description = "Azure AI Language account ID"
  value       = azurerm_cognitive_account.language.id
}

# ================================================================
# Azure AI Vision
# ================================================================

output "vision_endpoint" {
  description = "Azure AI Vision endpoint"
  value       = azurerm_cognitive_account.vision.endpoint
}

output "vision_id" {
  description = "Azure AI Vision account ID"
  value       = azurerm_cognitive_account.vision.id
}

# ================================================================
# Document Intelligence
# ================================================================

output "document_intelligence_endpoint" {
  description = "Document Intelligence endpoint"
  value       = azurerm_cognitive_account.document_intelligence.endpoint
}

output "document_intelligence_id" {
  description = "Document Intelligence account ID"
  value       = azurerm_cognitive_account.document_intelligence.id
}
