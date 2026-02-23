# ================================================================
# AI Services Module Variables
# ================================================================

variable "project" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "key_vault_key_id" {
  description = "Key Vault key versionless ID for CMK encryption"
  type        = string
}

variable "managed_identity_id" {
  description = "User-assigned managed identity ID for CMK access"
  type        = string
}

variable "managed_identity_client_id" {
  description = "User-assigned managed identity client ID for CMK access"
  type        = string
}

variable "allowed_ip_ranges" {
  description = "IP ranges allowed to access cognitive services (e.g., App Runner NAT Gateway IPs)"
  type        = list(string)
  default     = []
}

variable "language_sku" {
  description = "SKU for AI Language (TextAnalytics)"
  type        = string
  default     = "F0"
}

variable "vision_sku" {
  description = "SKU for AI Vision (ComputerVision)"
  type        = string
  default     = "F0"
}

variable "document_intelligence_sku" {
  description = "SKU for Document Intelligence (FormRecognizer)"
  type        = string
  default     = "F0"
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
