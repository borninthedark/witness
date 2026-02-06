# ================================================================
# CodePipeline Module Outputs
# ================================================================

output "pipeline_arn" {
  description = "CodePipeline ARN"
  value       = aws_codepipeline.main.arn
}

output "pipeline_name" {
  description = "CodePipeline name"
  value       = aws_codepipeline.main.name
}

output "artifact_bucket_id" {
  description = "Artifact S3 bucket ID"
  value       = module.artifact_bucket.s3_bucket_id
}

output "artifact_bucket_arn" {
  description = "Artifact S3 bucket ARN"
  value       = module.artifact_bucket.s3_bucket_arn
}

output "codebuild_validate_name" {
  description = "CodeBuild validate project name"
  value       = aws_codebuild_project.validate.name
}

output "codebuild_plan_name" {
  description = "CodeBuild plan project name"
  value       = aws_codebuild_project.plan.name
}
