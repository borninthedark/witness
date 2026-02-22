# ================================================================
# HCP Terraform Backend - Dev Workspace
# ================================================================
# VCS-driven workflow: HCP Terraform watches terraform/aws/dev
# and auto-runs plan/apply when files change.
#
# Sensitive variables (secret_key) are set as workspace
# variables in HCP Terraform.
# ================================================================

terraform {
  cloud {
    organization = "DefiantEmissary"

    workspaces {
      name = "witness-dev"
    }
  }
}
