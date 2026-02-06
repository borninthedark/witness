# ================================================================
# App Runner Module Variables
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

# ================================================================
# Container Configuration
# ================================================================

variable "image_tag" {
  description = "Container image tag"
  type        = string
  default     = "latest"
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

# ================================================================
# App Runner Instance
# ================================================================

variable "instance_cpu" {
  description = "App Runner instance CPU (256, 512, 1024, 2048, 4096)"
  type        = string
  default     = "512"
}

variable "instance_memory" {
  description = "App Runner instance memory (512, 1024, 2048, 3072, 4096, ...)"
  type        = string
  default     = "1024"
}

variable "auto_deploy" {
  description = "Enable auto deployment on ECR push"
  type        = bool
  default     = true
}

# ================================================================
# Auto Scaling
# ================================================================

variable "min_size" {
  description = "Minimum number of instances"
  type        = number
  default     = 1
}

variable "max_size" {
  description = "Maximum number of instances"
  type        = number
  default     = 3
}

variable "max_concurrency" {
  description = "Maximum concurrent requests per instance"
  type        = number
  default     = 100
}

# ================================================================
# Networking
# ================================================================

variable "vpc_id" {
  description = "VPC ID for VPC connector"
  type        = string
  default     = ""
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for VPC connector"
  type        = list(string)
  default     = []
}

# ================================================================
# Tags
# ================================================================

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
