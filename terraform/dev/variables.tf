# ================================================================
# Container Apps Variables (pass-through to module)
# ================================================================

variable "resource_group_name" {
  description = "Name of the Azure resource group"
  type        = string
}

variable "app_name" {
  description = "Name of the Container App"
  type        = string
}

variable "container_image" {
  description = "Container image to deploy (e.g., ghcr.io/org/app:latest)"
  type        = string
}

variable "secret_key" {
  description = "Application secret key"
  type        = string
  sensitive   = true
}

variable "location" {
  description = "Azure region for deployment"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "dev"
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}

variable "container_port" {
  description = "Port the container listens on"
  type        = number
  default     = 8000
}

variable "container_cpu" {
  description = "CPU allocation (e.g., '0.5')"
  type        = string
  default     = "0.5"
}

variable "container_memory" {
  description = "Memory allocation (e.g., '1Gi')"
  type        = string
  default     = "1Gi"
}

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}

variable "database_url" {
  description = "Database connection URL"
  type        = string
  default     = "sqlite:////app/data/fitness.db"
}

variable "min_replicas" {
  description = "Minimum replicas"
  type        = number
  default     = 1
}

variable "max_replicas" {
  description = "Maximum replicas"
  type        = number
  default     = 3
}

variable "revision_mode" {
  description = "Revision mode (Single or Multiple)"
  type        = string
  default     = "Single"
}

variable "revision_suffix" {
  description = "Revision suffix (optional)"
  type        = string
  default     = null
}

variable "ingress_external_enabled" {
  description = "Allow external access"
  type        = bool
  default     = true
}

variable "enable_vnet_integration" {
  description = "Enable VNet integration"
  type        = bool
  default     = false
}

variable "internal_load_balancer_enabled" {
  description = "Use internal load balancer"
  type        = bool
  default     = false
}

variable "vnet_address_space" {
  description = "VNet address space"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "container_apps_subnet_prefixes" {
  description = "Subnet prefixes for Container Apps"
  type        = list(string)
  default     = ["10.0.0.0/23"]
}

variable "container_registry_server" {
  description = "Container registry server (e.g., ghcr.io)"
  type        = string
  default     = null
}

variable "container_registry_username" {
  description = "Container registry username"
  type        = string
  default     = null
}

variable "container_registry_password" {
  description = "Container registry password"
  type        = string
  default     = null
  sensitive   = true
}

variable "use_managed_identity_for_registry" {
  description = "Use managed identity for registry authentication"
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "Log Analytics retention in days"
  type        = number
  default     = 30
}
