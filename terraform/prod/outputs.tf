# ================================================================
# Production Environment Outputs
# ================================================================

# ================================================================
# Networking
# ================================================================

output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.networking.private_subnet_ids
}

# ================================================================
# App Runner
# ================================================================

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = module.app_runner.ecr_repository_url
}

output "service_url" {
  description = "App Runner service URL"
  value       = module.app_runner.service_url
}

output "service_arn" {
  description = "App Runner service ARN"
  value       = module.app_runner.service_arn
}

# ================================================================
# Security
# ================================================================

output "kms_key_arn" {
  description = "KMS key ARN"
  value       = module.security.kms_key_arn
}

output "cloudtrail_arn" {
  description = "CloudTrail ARN"
  value       = module.security.cloudtrail_arn
}

# ================================================================
# Observability
# ================================================================

output "dashboard_name" {
  description = "CloudWatch dashboard name"
  value       = module.observability.dashboard_name
}

output "log_group_name" {
  description = "CloudWatch log group name"
  value       = module.observability.log_group_name
}
