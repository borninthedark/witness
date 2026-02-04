# ================================================================
# Terraform Backend Configuration
# ================================================================
#
# Backend is configured dynamically via CLI arguments in CI/CD:
#   terraform init \
#     -backend-config="resource_group_name=..." \
#     -backend-config="storage_account_name=..." \
#     -backend-config="container_name=..." \
#     -backend-config="key=${ENVIRONMENT}/terraform.tfstate"
#
# For local development, you can:
# 1. Comment out the backend block to use local state
# 2. Or copy backend.tf.example and fill in your values
# ================================================================

terraform {
  backend "azurerm" {}
}
