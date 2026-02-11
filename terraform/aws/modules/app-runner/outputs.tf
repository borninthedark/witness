# ================================================================
# App Runner Module Outputs
# ================================================================

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = module.ecr.repository_url
}

output "ecr_repository_arn" {
  description = "ECR repository ARN"
  value       = module.ecr.repository_arn
}

output "service_url" {
  description = "App Runner service URL"
  value       = "https://${module.app_runner.service_url}"
}

output "service_arn" {
  description = "App Runner service ARN"
  value       = module.app_runner.service_arn
}

output "service_id" {
  description = "App Runner service ID"
  value       = module.app_runner.service_id
}

output "service_status" {
  description = "App Runner service status"
  value       = module.app_runner.service_status
}

output "secret_arn" {
  description = "Secrets Manager secret ARN"
  value       = aws_secretsmanager_secret.app.arn
}

output "access_role_arn" {
  description = "App Runner access role ARN"
  value       = aws_iam_role.apprunner_access.arn
}

output "instance_role_arn" {
  description = "App Runner instance role ARN"
  value       = aws_iam_role.apprunner_instance.arn
}
