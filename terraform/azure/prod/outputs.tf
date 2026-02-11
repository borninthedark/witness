# ================================================================
# Production Environment Outputs - Azure AI Platform
# ================================================================

# ================================================================
# AI Foundry
# ================================================================

output "ai_foundry_hub_id" {
  description = "AI Foundry hub ID"
  value       = module.ai_foundry.hub_id
}

output "ai_foundry_project_id" {
  description = "AI Foundry project ID"
  value       = module.ai_foundry.project_id
}

output "content_safety_endpoint" {
  description = "Content Safety endpoint"
  value       = module.ai_foundry.content_safety_endpoint
}

# ================================================================
# AI Search
# ================================================================

output "search_service_id" {
  description = "Azure AI Search service ID"
  value       = module.ai_search.search_service_id
}

output "search_endpoint" {
  description = "Azure AI Search endpoint"
  value       = module.ai_search.endpoint
}

output "search_primary_key" {
  description = "Azure AI Search primary admin key"
  value       = module.ai_search.primary_key
  sensitive   = true
}

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
