# ================================================================
# Data Ingest Module Outputs
# ================================================================

output "dynamodb_table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.data_store.name
}

output "dynamodb_table_arn" {
  description = "DynamoDB table ARN"
  value       = aws_dynamodb_table.data_store.arn
}

output "lambda_function_arns" {
  description = "Map of Lambda function ARNs"
  value       = { for k, fn in aws_lambda_function.ingest : k => fn.arn }
}

output "lambda_function_names" {
  description = "Map of Lambda function names"
  value       = { for k, fn in aws_lambda_function.ingest : k => fn.function_name }
}

output "lambda_exec_role_arn" {
  description = "Lambda execution role ARN"
  value       = aws_iam_role.lambda_exec.arn
}

output "scheduler_group_name" {
  description = "EventBridge Scheduler group name"
  value       = aws_scheduler_schedule_group.ingest.name
}
