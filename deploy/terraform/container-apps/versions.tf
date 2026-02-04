# ================================================================
# Terraform and Provider Versions
# ================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.85.0, < 4.0.0"  # Module requires >= 3.85, < 4.0
    }
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }

  # Use OIDC authentication in CI/CD
  use_oidc = true
}
