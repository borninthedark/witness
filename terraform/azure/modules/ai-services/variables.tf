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
