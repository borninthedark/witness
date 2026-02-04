# ================================================================
# HCP Terraform Backend - Dev Workspace
# ================================================================
# VCS-driven workflow: HCP Terraform watches this directory
# and auto-runs plan/apply when files change.
#
# Sensitive variables (secret_key, container_registry_password)
# are set as workspace variables in HCP Terraform.
# ================================================================

terraform {
  cloud {
    organization = "DefiantEmissary"

    workspaces {
      name = "witness-dev"
    }
  }
}
