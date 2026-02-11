# ================================================================
# Bootstrap Variables
# ================================================================

variable "project" {
  description = "Project name used for resource naming"
  type        = string
  default     = "witness"
}

variable "aws_region" {
  description = "AWS region for the OIDC provider and IAM resources"
  type        = string
  default     = "us-east-1"
}

variable "tfc_organization" {
  description = "HCP Terraform organization name"
  type        = string
  default     = "DefiantEmissary"
}

variable "tfc_workspace_names" {
  description = "HCP Terraform workspace names that need AWS access"
  type        = list(string)
  default     = ["witness-dev", "witness-prod"]
}

variable "github_repository" {
  description = "GitHub repository (owner/repo) for Actions OIDC trust"
  type        = string
  default     = "borninthedark/witness"
}

variable "domain_name" {
  description = "Domain name to register via Route 53 Domains"
  type        = string
  default     = "princetonstrong.com"
}

# ================================================================
# Domain Registration Contact
# ================================================================

variable "contact_first_name" {
  description = "Domain registrant first name"
  type        = string
}

variable "contact_last_name" {
  description = "Domain registrant last name"
  type        = string
}

variable "contact_email" {
  description = "Domain registrant email"
  type        = string
  sensitive   = true
}

variable "contact_phone" {
  description = "Domain registrant phone (format: +1.5551234567)"
  type        = string
  sensitive   = true
}

variable "contact_address_line_1" {
  description = "Domain registrant street address"
  type        = string
  sensitive   = true
}

variable "contact_city" {
  description = "Domain registrant city"
  type        = string
}

variable "contact_state" {
  description = "Domain registrant state/province"
  type        = string
}

variable "contact_zip_code" {
  description = "Domain registrant zip/postal code"
  type        = string
}

variable "contact_country_code" {
  description = "Domain registrant country code (e.g. US)"
  type        = string
  default     = "US"
}
