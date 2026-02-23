# ================================================================
# Production Environment Variables - Azure AI Platform
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
  default     = "prod"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

variable "tags" {
  description = "Additional resource tags"
  type        = map(string)
  default     = {}
}

# ================================================================
# Security
# ================================================================

variable "key_expiration_date" {
  description = "Key Vault key expiration date (RFC 3339). Update annually."
  type        = string
  default     = "2027-02-22T00:00:00Z"
}
