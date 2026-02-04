# ================================================================
# AKS Terraform Variables
# Official Azure/aks/azurerm Module (v11.0.0)
# ================================================================

# ================================================================
# Required Variables
# ================================================================

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
}

variable "aks_cluster_name" {
  description = "AKS cluster name (used as prefix)"
  type        = string
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

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}

# ================================================================
# Kubernetes Configuration
# ================================================================

variable "kubernetes_version" {
  description = "Kubernetes version (null for latest)"
  type        = string
  default     = null
}

variable "sku_tier" {
  description = "SKU tier (Free, Standard, or Premium)"
  type        = string
  default     = "Free"

  validation {
    condition     = contains(["Free", "Standard", "Premium"], var.sku_tier)
    error_message = "SKU tier must be Free, Standard, or Premium."
  }
}

variable "automatic_upgrade_channel" {
  description = "Auto-upgrade channel (null, patch, rapid, stable, node-image)"
  type        = string
  default     = "stable"

  validation {
    condition     = var.automatic_upgrade_channel == null || contains(["patch", "rapid", "stable", "node-image"], var.automatic_upgrade_channel)
    error_message = "Upgrade channel must be null, patch, rapid, stable, or node-image."
  }
}

# ================================================================
# Default Node Pool
# ================================================================

variable "node_vm_size" {
  description = "Node pool VM size"
  type        = string
  default     = "Standard_D2s_v3"
}

variable "os_disk_size_gb" {
  description = "OS disk size in GB"
  type        = number
  default     = 50
}

variable "node_count" {
  description = "Number of nodes (used when autoscaling disabled)"
  type        = number
  default     = 2

  validation {
    condition     = var.node_count >= 1 && var.node_count <= 100
    error_message = "Node count must be between 1 and 100."
  }
}

variable "auto_scaling_enabled" {
  description = "Enable node pool autoscaling"
  type        = bool
  default     = true
}

variable "min_node_count" {
  description = "Minimum number of nodes for autoscaling"
  type        = number
  default     = 1

  validation {
    condition     = var.min_node_count >= 1
    error_message = "Minimum node count must be at least 1."
  }
}

variable "max_node_count" {
  description = "Maximum number of nodes for autoscaling"
  type        = number
  default     = 5

  validation {
    condition     = var.max_node_count >= 1
    error_message = "Maximum node count must be at least 1."
  }
}

# ================================================================
# User Node Pool (optional)
# ================================================================

variable "enable_user_node_pool" {
  description = "Enable additional user node pool"
  type        = bool
  default     = false
}

variable "user_node_pool_vm_size" {
  description = "VM size for user node pool"
  type        = string
  default     = "Standard_D4s_v3"
}

variable "user_node_pool_node_count" {
  description = "Initial node count for user node pool"
  type        = number
  default     = 1
}

variable "user_node_pool_min_count" {
  description = "Minimum nodes for user node pool autoscaling"
  type        = number
  default     = 1
}

variable "user_node_pool_max_count" {
  description = "Maximum nodes for user node pool autoscaling"
  type        = number
  default     = 5
}

variable "user_node_pool_taints" {
  description = "Node taints for user node pool"
  type        = list(string)
  default     = []
}

# ================================================================
# Networking
# ================================================================

variable "network_plugin" {
  description = "Network plugin (azure or kubenet)"
  type        = string
  default     = "azure"

  validation {
    condition     = contains(["azure", "kubenet"], var.network_plugin)
    error_message = "Network plugin must be azure or kubenet."
  }
}

variable "network_policy" {
  description = "Network policy (azure, calico, or null)"
  type        = string
  default     = "azure"
}

variable "service_cidr" {
  description = "Kubernetes service CIDR"
  type        = string
  default     = "10.0.0.0/16"
}

variable "dns_service_ip" {
  description = "DNS service IP address"
  type        = string
  default     = "10.0.0.10"
}

variable "enable_private_cluster" {
  description = "Enable private cluster"
  type        = bool
  default     = false
}

variable "private_cluster_public_fqdn_enabled" {
  description = "Enable public FQDN for private cluster"
  type        = bool
  default     = true
}

variable "vnet_address_space" {
  description = "VNet address space for private cluster"
  type        = list(string)
  default     = ["10.1.0.0/16"]
}

variable "aks_subnet_address_prefixes" {
  description = "AKS subnet address prefixes"
  type        = list(string)
  default     = ["10.1.0.0/22"]
}

# ================================================================
# Security & Identity
# ================================================================

variable "azure_rbac_enabled" {
  description = "Enable Azure RBAC for Kubernetes"
  type        = bool
  default     = true
}

variable "enable_workload_identity" {
  description = "Enable workload identity"
  type        = bool
  default     = true
}

variable "enable_azure_policy" {
  description = "Enable Azure Policy addon"
  type        = bool
  default     = false
}

# ================================================================
# Addons
# ================================================================

variable "enable_nginx_ingress" {
  description = "Enable NGINX ingress controller addon (Web App Routing)"
  type        = bool
  default     = true
}

variable "enable_monitoring" {
  description = "Enable Container Insights monitoring"
  type        = bool
  default     = true
}

variable "log_analytics_retention_days" {
  description = "Log Analytics workspace retention in days"
  type        = number
  default     = 30
}
