# ================================================================
# Production Environment - Azure AI Platform
# ================================================================
# HCP Terraform VCS workflow: workspace "witness-azure"
# Working directory: terraform/azure/prod
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
    Workspace   = "witness-azure"
  })
}

# ================================================================
# AI Foundry (Hub + Project + Content Safety)
# ================================================================

module "ai_foundry" {
  source = "../modules/ai-foundry"

  project             = var.project
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name

  tags = var.tags
}

# ================================================================
# AI Search
# ================================================================

module "ai_search" {
  source = "../modules/ai-search"

  project             = var.project
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name

  tags = var.tags
}

# ================================================================
# AI Services (OpenAI, Language, Vision, Document Intelligence)
# ================================================================

module "ai_services" {
  source = "../modules/ai-services"

  project             = var.project
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name

  tags = var.tags
}
