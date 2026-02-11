# ================================================================
# Security Module Variables
# ================================================================

variable "project" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
}

variable "kms_deletion_window" {
  description = "KMS key deletion window in days"
  type        = number
  default     = 7
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "enable_config" {
  description = "Enable AWS Config recorder"
  type        = bool
  default     = false
}

variable "enable_guardduty" {
  description = "Enable GuardDuty threat detection"
  type        = bool
  default     = true
}

variable "enable_security_hub" {
  description = "Enable Security Hub compliance dashboard"
  type        = bool
  default     = false
}

variable "alarm_email" {
  description = "Email address for alarm notifications (null to skip)"
  type        = string
  default     = null
}

variable "monthly_budget_limit" {
  description = "Monthly budget limit in USD (0 to disable)"
  type        = number
  default     = 0
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
