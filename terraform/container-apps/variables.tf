# ================================================================
# Container Apps Variables
# Azure/container-apps/azure module
# ================================================================

# ================================================================
# Required Variables
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
  description = "Container image to deploy (e.g., myacr.azurecr.io/app:latest)"
  type        = string
}

variable "secret_key" {
  description = "Application secret key"
  type        = string
  sensitive   = true
}

# ================================================================
# Location & Environment
# ================================================================

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

# ================================================================
# Container Configuration
# ================================================================

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

# ================================================================
# Scaling
# ================================================================

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

# ================================================================
# Ingress
# ================================================================

variable "ingress_external_enabled" {
  description = "Allow external access"
  type        = bool
  default     = true
}

# ================================================================
# Networking
# ================================================================

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

# ================================================================
# Azure Container Registry
# ================================================================

variable "acr_name" {
  description = "Globally unique name for the Azure Container Registry (alphanumeric only)"
  type        = string
}

variable "acr_sku" {
  description = "SKU for the Azure Container Registry (Basic, Standard, Premium)"
  type        = string
  default     = "Basic"
}

variable "acr_admin_enabled" {
  description = "Enable admin user for the ACR"
  type        = bool
  default     = false
}

variable "acr_task_context_url" {
  description = "GitHub repo URL for ACR Task context (e.g., https://github.com/borninthedark/witness.git#main)"
  type        = string
}

variable "acr_image_tag" {
  description = "Default tag for ACR Task builds"
  type        = string
  default     = "dev"
}

variable "container_registry_password" {
  description = "GitHub PAT for ACR Build Task to access the source repository"
  type        = string
  sensitive   = true
}

# ================================================================
# Azure Key Vault
# ================================================================

variable "key_vault_name" {
  description = "Name of the Azure Key Vault"
  type        = string
}

variable "key_vault_sku" {
  description = "SKU for the Key Vault (standard or premium)"
  type        = string
  default     = "standard"
}

variable "key_vault_soft_delete_retention_days" {
  description = "Number of days to retain soft-deleted items (7-90)"
  type        = number
  default     = 7
}

variable "key_vault_purge_protection_enabled" {
  description = "Enable purge protection for the Key Vault"
  type        = bool
  default     = false
}

# ================================================================
# Monitoring
# ================================================================

variable "log_retention_days" {
  description = "Log Analytics retention in days"
  type        = number
  default     = 30
}
