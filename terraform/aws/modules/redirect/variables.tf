# ================================================================
# Redirect Module Variables
# ================================================================

variable "source_domain" {
  description = "Domain to redirect from (e.g. engage.princetonstrong.online)"
  type        = string
}

variable "target_url" {
  description = "Full URL to redirect to (e.g. https://engage.princetonstrong.com)"
  type        = string
}

variable "hosted_zone_id" {
  description = "Route 53 hosted zone ID for the source domain"
  type        = string
}

variable "tags" {
  description = "Additional resource tags"
  type        = map(string)
  default     = {}
}
