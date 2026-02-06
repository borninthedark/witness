# ================================================================
# Bootstrap Outputs
# ================================================================

output "role_arn" {
  description = "IAM role ARN to set as TFC_AWS_RUN_ROLE_ARN in HCP Terraform"
  value       = aws_iam_role.tfc.arn
}

output "oidc_provider_arn" {
  description = "OIDC provider ARN for reference"
  value       = aws_iam_openid_connect_provider.tfc.arn
}

output "workspace_env_vars" {
  description = "Environment variables to set on each HCP Terraform workspace"
  value = {
    TFC_AWS_PROVIDER_AUTH = "true"
    TFC_AWS_RUN_ROLE_ARN  = aws_iam_role.tfc.arn
  }
}
