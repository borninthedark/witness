# ================================================================
# Dev Environment - Azure AI Platform (Light Config)
# ================================================================
# HCP Terraform VCS workflow: workspace "witness-azure-dev"
# Working directory: terraform/azure/dev
# ================================================================
# Cost savings: only ai-services with free tiers.
# Skip ai-foundry and ai-search (not needed for dev).
# ================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.0.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# ================================================================
# Resource Group
# ================================================================

resource "azurerm_resource_group" "main" {
  name     = "${var.project}-${var.environment}-ai"
  location = var.location

  tags = merge(var.tags, {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
    Workspace   = "witness-azure-dev"
  })
}

# ================================================================
# AI Services (OpenAI + free-tier Language, Vision, Doc Intelligence)
# ================================================================

module "ai_services" {
  source = "../modules/ai-services"

  project             = var.project
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name

  language_sku              = "F0"
  vision_sku                = "F0"
  document_intelligence_sku = "F0"

  tags = var.tags
}
