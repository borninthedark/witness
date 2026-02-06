# ================================================================
# DNS Module Variables
# ================================================================

variable "domain_name" {
  description = "Root domain name (must match the registered domain)"
  type        = string
}

variable "subdomain" {
  description = "Subdomain prefix (e.g. 'engage' for engage.princetonstrong.com)"
  type        = string
}

variable "hosted_zone_id" {
  description = "Route 53 hosted zone ID for the domain"
  type        = string
}

variable "app_runner_service_arn" {
  description = "ARN of the App Runner service to associate with the custom domain"
  type        = string
}
