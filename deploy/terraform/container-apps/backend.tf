# ================================================================
# HCP Terraform Backend Configuration
# ================================================================
#
# State is managed by HCP Terraform (Terraform Cloud).
#
# CLI-driven workflow:
#   - La Forge runs Data CI + Worf scans, then plan/apply
#   - terraform plan -var-file=dev/terraform.tfvars
#   - terraform plan -var-file=prod/terraform.tfvars
#   - Sensitive vars (secret_key, container_registry_password)
#     passed via -var from GitHub secrets
#
# For local development:
#   1. Run `terraform login` to authenticate
#   2. terraform init
#   3. terraform plan -var-file=dev/terraform.tfvars
# ================================================================

terraform {
  cloud {
    organization = "DefiantEmissary"

    workspaces {
      name = "witness-container-apps"
    }
  }
}
