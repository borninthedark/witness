# ================================================================
# Data Ingest Module Variables
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
# DynamoDB
# ================================================================

variable "enable_point_in_time_recovery" {
  description = "Enable DynamoDB point-in-time recovery"
  type        = bool
  default     = true
}

variable "lambda_reserved_concurrency" {
  description = "Reserved concurrent executions per Lambda function"
  type        = number
  default     = 5
}

# ================================================================
# Lambda
# ================================================================

variable "lambda_memory_mb" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 256
}

variable "lambda_architecture" {
  description = "Lambda CPU architecture"
  type        = string
  default     = "arm64"
}

variable "lambda_runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.13"
}

variable "nasa_api_key" {
  description = "NASA API key for ingest functions"
  type        = string
  default     = ""
  sensitive   = true
}

variable "nist_api_key" {
  description = "NIST NVD API key for CVE ingest"
  type        = string
  default     = ""
  sensitive   = true
}

# ================================================================
# Schedules
# ================================================================

variable "nasa_schedule" {
  description = "EventBridge schedule expression for NASA ingest"
  type        = string
  default     = "rate(24 hours)"
}

variable "nist_schedule" {
  description = "EventBridge schedule expression for NIST ingest"
  type        = string
  default     = "rate(24 hours)"
}

variable "space_schedule" {
  description = "EventBridge schedule expression for space data ingest"
  type        = string
  default     = "rate(24 hours)"
}

# ================================================================
# Embedding Pipeline (Azure AI Search)
# ================================================================

variable "enable_embed_sync" {
  description = "Enable DynamoDB Streams → Azure AI Search embedding sync"
  type        = bool
  default     = false
}

variable "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint for embedding"
  type        = string
  default     = ""
}

variable "azure_openai_key" {
  description = "Azure OpenAI API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "azure_search_endpoint" {
  description = "Azure AI Search endpoint"
  type        = string
  default     = ""
}

variable "azure_search_key" {
  description = "Azure AI Search admin key"
  type        = string
  default     = ""
  sensitive   = true
}

# ================================================================
# Observability
# ================================================================

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 365
}

# ================================================================
# Tags
# ================================================================

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
