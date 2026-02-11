# ================================================================
# HCP Terraform Backend - Azure Prod Workspace
# ================================================================
# VCS-driven workflow: HCP Terraform watches terraform/azure/prod
# and auto-runs plan/apply when files change.
#
# Sensitive variables (API keys) are set as workspace
# variables in HCP Terraform.
# ================================================================

terraform {
  cloud {
    organization = "DefiantEmissary"

    workspaces {
      name = "witness-azure"
    }
  }
}
