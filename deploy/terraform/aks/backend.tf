# ================================================================
# Terraform Backend Configuration
# ================================================================
#
# Backend is configured dynamically via CLI arguments in CI/CD:
#   terraform init \
#     -backend-config="resource_group_name=..." \
#     -backend-config="storage_account_name=..." \
#     -backend-config="container_name=..." \
#     -backend-config="key=aks/${ENVIRONMENT}/terraform.tfstate"
#
# For local development, you can:
# 1. Comment out the backend block to use local state
# 2. Or create a backend.conf file with your values
# ================================================================

terraform {
  backend "azurerm" {}
}
