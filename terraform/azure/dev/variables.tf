# ================================================================
# Dev Environment Variables - Azure AI Platform
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
