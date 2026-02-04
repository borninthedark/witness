# ================================================================
# HCP Terraform Backend Configuration
# ================================================================
#
# State is managed by HCP Terraform (Terraform Cloud).
#
# VCS-driven workflow:
#   - Push to deploy/terraform/** triggers auto-plan in HCP TF
#   - La Forge runs Data CI + Worf security scans as quality gate
#   - Manual confirm required in HCP TF before apply
#
# Per-environment variables are set as HCP TF workspace variables
# (sensitive values like secret_key, container_registry_password).
#
# For local development:
#   1. Run `terraform login` to authenticate
#   2. terraform init
#   3. terraform plan
# ================================================================

terraform {
  cloud {
    organization = "DefiantEmissary"

    workspaces {
      name = "witness-container-apps"
    }
  }
}
