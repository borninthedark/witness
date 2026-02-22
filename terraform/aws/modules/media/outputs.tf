# ================================================================
# Media CDN Module Outputs
# ================================================================

output "media_bucket_name" {
  description = "S3 media bucket name"
  value       = module.media_bucket.s3_bucket_id
}

output "media_bucket_arn" {
  description = "S3 media bucket ARN"
  value       = module.media_bucket.s3_bucket_arn
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.main.id
}

output "media_cdn_domain" {
  description = "CDN domain name (e.g. media.princetonstrong.com)"
  value       = "media.${var.domain_name}"
}
