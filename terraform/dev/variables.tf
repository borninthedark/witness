# ================================================================
# Dev Environment Variables
# ================================================================

# ================================================================
# Project
# ================================================================

variable "project" {
  description = "Project name"
  type        = string
  default     = "witness"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "tags" {
  description = "Additional resource tags"
  type        = map(string)
  default     = {}
}

# ================================================================
# DNS
# ================================================================

variable "domain_name" {
  description = "Root domain name for custom domain"
  type        = string
  default     = "princetonstrong.com"
}

variable "hosted_zone_id" {
  description = "Route 53 hosted zone ID (from bootstrap domain registration)"
  type        = string
}

# ================================================================
# Networking
# ================================================================

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "azs" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "private_subnets" {
  description = "Private subnet CIDRs"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "public_subnets" {
  description = "Public subnet CIDRs"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
}

# ================================================================
# App Runner
# ================================================================

variable "image_tag" {
  description = "Container image tag"
  type        = string
  default     = "dev"
}

variable "container_port" {
  description = "Port the container listens on"
  type        = number
  default     = 8000
}

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}

variable "secret_key" {
  description = "Application secret key"
  type        = string
  sensitive   = true
}

variable "database_url" {
  description = "Database connection URL"
  type        = string
  default     = "sqlite:////app/data/fitness.db"
}

variable "admin_username" {
  description = "Admin console username"
  type        = string
  default     = "admin"
}

variable "admin_password" {
  description = "Admin console password"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key for AI features"
  type        = string
  sensitive   = true
  default     = ""
}

variable "nasa_api_key" {
  description = "NASA API key (optional)"
  type        = string
  default     = ""
}

variable "instance_cpu" {
  description = "App Runner instance CPU"
  type        = string
  default     = "512"
}

variable "instance_memory" {
  description = "App Runner instance memory"
  type        = string
  default     = "1024"
}

variable "auto_deploy" {
  description = "Auto deploy on ECR push"
  type        = bool
  default     = true
}

variable "min_size" {
  description = "Minimum instances"
  type        = number
  default     = 1
}

variable "max_size" {
  description = "Maximum instances"
  type        = number
  default     = 3
}

variable "max_concurrency" {
  description = "Max concurrent requests per instance"
  type        = number
  default     = 100
}

# ================================================================
# Notifications
# ================================================================

variable "protonmail_verification_code" {
  description = "Proton Mail domain verification code"
  type        = string
  default     = "7853921efffd8daad408bf6a5e01b5390828c2c2"
}

variable "alarm_email" {
  description = "Email for alarm notifications"
  type        = string
  default     = null
}

# ================================================================
# Observability
# ================================================================

variable "log_retention_days" {
  description = "Log retention in days"
  type        = number
  default     = 30
}

# ================================================================
# CodePipeline (optional)
# ================================================================

variable "enable_codepipeline" {
  description = "Enable CodePipeline for TF validation"
  type        = bool
  default     = false
}

variable "repository_id" {
  description = "GitHub repository (owner/repo)"
  type        = string
  default     = ""
}

variable "codestar_connection_arn" {
  description = "CodeStar connection ARN"
  type        = string
  default     = ""
}
