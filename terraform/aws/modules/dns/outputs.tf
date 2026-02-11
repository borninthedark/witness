# ================================================================
# DNS Module Outputs
# ================================================================

output "custom_domain_url" {
  description = "Full custom domain URL"
  value       = "https://${var.subdomain}.${var.domain_name}"
}

output "dns_target" {
  description = "App Runner DNS target for the custom domain"
  value       = aws_apprunner_custom_domain_association.this.dns_target
}
