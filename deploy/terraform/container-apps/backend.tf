# ================================================================
# HCP Terraform Backend Configuration
# ================================================================
#
# State is managed by HCP Terraform (Terraform Cloud).
# Configuration is provided via environment variables in CI/CD:
#
#   TF_CLOUD_ORGANIZATION  - "DefiantEmissary" (set as GitHub variable TF_CLOUD_ORG)
#   TF_WORKSPACE           - Workspace name (e.g., witness-container-apps-dev)
#   TF_TOKEN_app_terraform_io - API token (set as GitHub secret TF_API_TOKEN)
#
# Workspaces:
#   witness-container-apps-dev   - Development environment
#   witness-container-apps-prod  - Production environment
#
# For local development:
#   1. Run `terraform login` to authenticate
#   2. export TF_CLOUD_ORGANIZATION="DefiantEmissary"
#   3. export TF_WORKSPACE="witness-container-apps-dev"
#   4. Or comment out the cloud block to use local state
# ================================================================

terraform {
  cloud {}
}
