# ================================================================
# Security Module Outputs
# ================================================================

output "kms_key_arn" {
  description = "KMS key ARN"
  value       = module.kms.key_arn
}

output "kms_key_id" {
  description = "KMS key ID"
  value       = module.kms.key_id
}

output "kms_key_alias" {
  description = "KMS key alias"
  value       = module.kms.aliases
}

output "cloudtrail_arn" {
  description = "CloudTrail ARN"
  value       = aws_cloudtrail.main.arn
}

output "cloudtrail_bucket_id" {
  description = "CloudTrail S3 bucket ID"
  value       = module.cloudtrail_bucket.s3_bucket_id
}

output "cloudtrail_bucket_arn" {
  description = "CloudTrail S3 bucket ARN"
  value       = module.cloudtrail_bucket.s3_bucket_arn
}

output "cloudtrail_log_group_name" {
  description = "CloudTrail CloudWatch log group name"
  value       = aws_cloudwatch_log_group.cloudtrail.name
}

output "sns_topic_arn" {
  description = "SNS topic ARN for alarm notifications"
  value       = aws_sns_topic.alarms.arn
}

output "guardduty_detector_id" {
  description = "GuardDuty detector ID"
  value       = var.enable_guardduty ? aws_guardduty_detector.main[0].id : null
}
