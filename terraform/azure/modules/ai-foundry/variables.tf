# ================================================================
# AI Foundry Module Variables
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

variable "key_expiration_date" {
  description = "Key Vault key expiration date (RFC 3339). Update annually."
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for private endpoints (null to skip)"
  type        = string
  default     = null
}

variable "vault_dns_zone_ids" {
  description = "Private DNS zone IDs for Key Vault private endpoint"
  type        = list(string)
  default     = []
}

variable "blob_dns_zone_ids" {
  description = "Private DNS zone IDs for Storage Blob private endpoint"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
