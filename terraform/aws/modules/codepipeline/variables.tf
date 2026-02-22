# ================================================================
# CodePipeline Module Variables
# ================================================================

variable "project" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS key ARN for encryption"
  type        = string
}

variable "terraform_version" {
  description = "Terraform version for CodeBuild"
  type        = string
  default     = "1.14.2"
}

variable "repository_id" {
  description = "GitHub repository (owner/repo)"
  type        = string
}

variable "branch_name" {
  description = "Branch to watch"
  type        = string
  default     = "main"
}

variable "codestar_connection_arn" {
  description = "CodeStar connection ARN for GitHub"
  type        = string
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
