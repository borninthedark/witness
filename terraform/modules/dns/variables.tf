# ================================================================
# DNS Module Variables
# ================================================================

variable "domain_name" {
  description = "Root domain name (must match the Route 53 hosted zone)"
  type        = string
}

variable "subdomain" {
  description = "Subdomain prefix (e.g. 'engage' for engage.princetonstrong.online)"
  type        = string
}

variable "app_runner_service_arn" {
  description = "ARN of the App Runner service to associate with the custom domain"
  type        = string
}
