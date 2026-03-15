# ================================================================
# Redirect Module Outputs
# ================================================================

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for the redirect"
  value       = aws_cloudfront_distribution.redirect.id
}

output "cloudfront_domain_name" {
  description = "CloudFront domain name"
  value       = aws_cloudfront_distribution.redirect.domain_name
}

output "s3_bucket_name" {
  description = "S3 redirect bucket name"
  value       = aws_s3_bucket.redirect.id
}
