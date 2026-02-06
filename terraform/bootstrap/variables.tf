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

variable "domain_name" {
  description = "Root domain name for Route 53 hosted zone"
  type        = string
  default     = "princetonstrong.online"
}
