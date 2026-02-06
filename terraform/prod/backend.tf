# ================================================================
# HCP Terraform Backend - Prod Workspace
# ================================================================
# VCS-driven workflow: HCP Terraform watches this directory
# and auto-runs plan/apply when files change.
#
# Sensitive variables (secret_key) are set as workspace
# variables in HCP Terraform.
# ================================================================

terraform {
  cloud {
    organization = "DefiantEmissary"

    workspaces {
      name = "witness-prod"
    }
  }
}
