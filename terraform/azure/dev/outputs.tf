# ================================================================
# Dev Environment Outputs - Azure AI Platform
# ================================================================

# ================================================================
# AI Services
# ================================================================

output "openai_endpoint" {
  description = "Azure OpenAI endpoint"
  value       = module.ai_services.openai_endpoint
}

output "openai_primary_key" {
  description = "Azure OpenAI primary access key"
  value       = module.ai_services.openai_primary_key
  sensitive   = true
}

output "language_endpoint" {
  description = "Azure AI Language endpoint"
  value       = module.ai_services.language_endpoint
}

output "vision_endpoint" {
  description = "Azure AI Vision endpoint"
  value       = module.ai_services.vision_endpoint
}

output "document_intelligence_endpoint" {
  description = "Document Intelligence endpoint"
  value       = module.ai_services.document_intelligence_endpoint
}
