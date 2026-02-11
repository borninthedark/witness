# ================================================================
# Observability Module Outputs
# ================================================================

output "log_group_name" {
  description = "CloudWatch log group name"
  value       = module.app_log_group.cloudwatch_log_group_name
}

output "log_group_arn" {
  description = "CloudWatch log group ARN"
  value       = module.app_log_group.cloudwatch_log_group_arn
}

output "dashboard_name" {
  description = "CloudWatch dashboard name"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}

output "error_alarm_arn" {
  description = "5xx error alarm ARN"
  value       = module.app_runner_alarms.cloudwatch_metric_alarm_arn
}

output "latency_alarm_arn" {
  description = "Latency alarm ARN"
  value       = module.app_runner_latency_alarm.cloudwatch_metric_alarm_arn
}
