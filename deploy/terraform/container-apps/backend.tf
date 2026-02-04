# ================================================================
# HCP Terraform Backend Configuration
# ================================================================
#
# State is managed by HCP Terraform (Terraform Cloud).
#
# Workspaces:
#   witness-container-apps-dev   - Development environment
#   witness-container-apps-prod  - Production environment
#
# Select workspace at runtime:
#   export TF_WORKSPACE="witness-container-apps-dev"
#
# For local development:
#   1. Run `terraform login` to authenticate
#   2. export TF_WORKSPACE="witness-container-apps-dev"
#   3. Or comment out the cloud block to use local state
# ================================================================

terraform {
  cloud {
    organization = "DefiantEmissary"

    workspaces {
      tags = ["witness", "container-apps"]
    }
  }
}
